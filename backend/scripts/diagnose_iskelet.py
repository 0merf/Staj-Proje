"""İSKELET TEŞHİSİ — bilek sinyali neden sıfır?

Sorun
-----
Kaskad deneyi (`evaluate_kaskad.py`) şunu gösterdi: RWF-2000 kavga
kliplerinin **%52'sinde `bilek` özelliği tam SIFIR** — oysa aynı
kliplerde `yakinlik` normal (0.411 vs 0.442).

    yakinlik, durus  → KUTUDAN türüyor      → çalışıyor
    bilek, enerji    → İSKELETTEN türüyor   → ölü

Yani kural kapısı "kavga var mı" diye değil, farkında olmadan
**"poz tahmini başarılı oldu mu"** diye soruyor.

⚠ BU BİR BULGU DEĞİL, BİR ARIZA — ve teşhis edilmeden çözülemez.

Dört hipotez, dört farklı çözüm
-------------------------------
**H1 · ÖRNEKLEME SEYREKLİĞİ**
4 FPS'te örnekliyoruz; 5 saniyelik klipten ~20 kare alıyoruz, videoda
~150 kare var. **Karelerin %87'sini hiç görmüyoruz.** Bilek hızı hızlı
bir büyüklük; iki örnek arası 250 ms iken bir yumruk tamamen araya
düşebilir.
→ Çözüm: örnekleme hızını artır (gerçek zamanlı hatta pahalı, tek
  kamera modunda bedava).

**H2 · POZ MODELİ TIKANMADA BAŞARISIZ**
Kavga sırasında bedenler iç içe geçiyor; YOLO26-pose kırpıntı tabanlı
çalışıyor ve kırpıntının içinde iki kişi varsa eklemleri karıştırıyor
ya da hiç bulmuyor.
→ Çözüm: daha büyük poz modeli, daha büyük kırpıntı çözünürlüğü,
  ya da güven eşiğini düşürmek.

**H3 · KIRPINTI ÇÖZÜNÜRLÜĞÜ DÜŞÜK**
Kırpıntılar 192 px'e ölçekleniyor (`pose_crop_size`). Uzaktaki küçük
bir kişinin kırpıntısı zaten 40 px ise, 192'ye büyütmek bilgi
üretmiyor — bulanık piksel üretiyor.
→ Çözüm: kırpıntı boyutunu artır (VRAM bol: 415 MB / 8 GB kullanılıyor).

**H4 · GÜVEN EŞİĞİ FAZLA SIKI**
`pose_conf_threshold = 0.25`. Hareket bulanıklığı olan bir bilek
0.20 güvenle bulunmuş olabilir ve eleniyor.
→ Çözüm: eşiği düşür — ama gürültü artar, ölçmek şart.

Bu betik ne yapıyor
-------------------
Aynı klipleri farklı yapılandırmalarla geçirip **poz başarı oranını**
ve **bilek sinyalinin sıfır olma oranını** ölçüyor. Hangi hipotezin
doğru olduğunu tahmin etmiyor — ayrıştırıyor.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI (GPU paylaşılmamalı).

Kullanım
--------
    uv run python scripts/diagnose_iskelet.py --klip 40
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000" / "val"

TOHUM = 42

# ⚠ COCO-17 iskeletinde bilek indeksleri. `analytics/features/skeleton.py`
# ile AYNI olmak zorunda — ayrışırsa yanlış eklem ölçülür ve hata
# SESSİZ olur (sayı üretilir, sadece başka bir eklemin sayısı).
SOL_BILEK, SAG_BILEK = 9, 10

# Denenecek yapılandırmalar. Her biri BİR hipotezi sınıyor.
YAPILANDIRMALAR: tuple[dict[str, Any], ...] = (
    {"ad": "TABAN (üretim)", "fps": 4.0, "kirpinti": 192, "conf": 0.25},
    {"ad": "H1 · sık örnekleme", "fps": 15.0, "kirpinti": 192, "conf": 0.25},
    {"ad": "H3 · büyük kırpıntı", "fps": 4.0, "kirpinti": 320, "conf": 0.25},
    {"ad": "H4 · gevşek güven", "fps": 4.0, "kirpinti": 192, "conf": 0.10},
    {"ad": "H1+H3+H4 birlikte", "fps": 15.0, "kirpinti": 320, "conf": 0.10},
)


def _klip_olc(
    yol: Path, *, dedektor: Any, poz: Any, ornek_fps: float, imgsz: int
) -> dict[str, float]:
    """Bir klipte poz ve bilek istatistiklerini ölçer."""
    import cv2
    import numpy as np

    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    adim = max(1, round(kaynak_fps / ornek_fps))
    takipci = BotSortTracker(frame_rate=int(max(1, ornek_fps)))

    kare_no = 0
    kamera = yol.stem
    ornek = tespit = iskelet_var = bilek_gorunur = 0
    bilek_hizlari: list[float] = []
    onceki_bilek: dict[int, tuple[float, float, float]] = {}

    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        ornek += 1
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps

        izler = takipci.update(kamera, dedektor.detect([hazir])[0], ts)
        tespit += len(izler)
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                if p is None or not p.found or p.keypoints is None:
                    continue
                iskelet_var += 1
                kp = p.keypoints
                # ⚠ Bileğin GÖRÜNÜR olması ayrı bir koşul: iskelet
                # bulunmuş olabilir ama bilek eklemi düşük güvenle
                # gelmiş ve kullanılamaz olabilir. `bilek` özelliğinin
                # sıfır olmasının iki ayrı sebebi var ve bu betik
                # onları ayırıyor.
                for idx in (SOL_BILEK, SAG_BILEK):
                    if idx < len(kp) and float(kp[idx][2]) > 0.0:
                        bilek_gorunur += 1
                        x, y = float(kp[idx][0]), float(kp[idx][1])
                        onc = onceki_bilek.get(iz.track_id * 10 + idx)
                        if onc is not None and ts > onc[0]:
                            dt = ts - onc[0]
                            mesafe = float(np.hypot(x - onc[1], y - onc[2]))
                            bilek_hizlari.append(mesafe / dt)
                        onceki_bilek[iz.track_id * 10 + idx] = (ts, x, y)
        kare_no += 1

    cap.release()
    return {
        "ornek_kare": float(ornek),
        "tespit": float(tespit),
        "iskelet_var": float(iskelet_var),
        "bilek_gorunur": float(bilek_gorunur),
        "bilek_hizi_azami": max(bilek_hizlari) if bilek_hizlari else 0.0,
        "bilek_hizi_medyan": statistics.median(bilek_hizlari) if bilek_hizlari else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="İskelet teşhisi")
    ap.add_argument("--klip", type=int, default=40, help="sınıf başına klip")
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    dedektor.warmup(1)

    # ⚠ Kavga VE normal klipler birlikte ölçülüyor. Yalnızca kavgaya
    # bakmak, "poz zaten her yerde başarısız" ihtimalini gizlerdi —
    # asıl soru poz başarısının kavgada NORMALDEN düşük olup olmadığı.
    kumeler: dict[str, list[Path]] = {}
    for sinif in ("fight", "nonfight"):
        k = sorted((RWF / sinif).glob("*.avi"))
        random.Random(TOHUM).shuffle(k)  # noqa: S311 — kripto değil
        kumeler[sinif] = k[: args.klip]

    sonuclar: list[dict[str, Any]] = []
    t0 = time.time()
    for yap in YAPILANDIRMALAR:
        poz = YoloPoseEstimator(
            PROJECT_ROOT / "models" / "yolo26s-pose.pt",
            crop_size=int(yap["kirpinti"]),
            conf_threshold=float(yap["conf"]),
        )
        poz.warmup(8)

        satir: dict[str, Any] = {"yapilandirma": yap["ad"], **yap}
        for sinif, klipler in kumeler.items():
            top = dict.fromkeys(("ornek_kare", "tespit", "iskelet_var", "bilek_gorunur"), 0.0)
            hizlar: list[float] = []
            bilek_sifir = 0
            for i, yol in enumerate(klipler, 1):
                m = _klip_olc(yol, dedektor=dedektor, poz=poz,
                              ornek_fps=float(yap["fps"]), imgsz=args.imgsz)
                for k in top:
                    top[k] += m[k]
                if m["bilek_hizi_azami"] > 0:
                    hizlar.append(m["bilek_hizi_azami"])
                else:
                    bilek_sifir += 1
                print(f"\r  {yap['ad']:<22} {sinif:<9} {i}/{len(klipler)} "
                      f"({time.time() - t0:.0f} sn)", end="", flush=True)
            n = len(klipler)
            satir[sinif] = {
                "klip": n,
                # ⚠ İSKELET ORANI = iskelet çıkan tespit / toplam tespit.
                # Payda TESPİT, kare değil: bir karede 3 kişi varsa 3
                # poz denemesi yapılıyor ve her biri ayrı başarılı ya da
                # başarısız oluyor.
                "iskelet_orani": round(top["iskelet_var"] / max(top["tespit"], 1), 4),
                "bilek_gorunur_orani": round(
                    top["bilek_gorunur"] / max(2 * top["iskelet_var"], 1), 4
                ),
                "bilek_sifir_klip_orani": round(bilek_sifir / max(n, 1), 4),
                "bilek_hizi_medyan": round(statistics.median(hizlar), 2) if hizlar else 0.0,
                "tespit_kare_basina": round(top["tespit"] / max(top["ornek_kare"], 1), 2),
            }
        print()
        sonuclar.append(satir)

    # ─── Rapor ───
    print("\n" + "═" * 78)
    print(f"{'YAPILANDIRMA':<22} {'sınıf':<9} {'iskelet%':>9} {'bilek gör%':>11} "
          f"{'bilek=0 klip%':>14}")
    for s in sonuclar:
        for sinif in ("fight", "nonfight"):
            d = s[sinif]
            print(f"{s['yapilandirma']:<22} {sinif:<9} "
                  f"{d['iskelet_orani']:>8.1%} {d['bilek_gorunur_orani']:>10.1%} "
                  f"{d['bilek_sifir_klip_orani']:>13.1%}")
        print()

    taban = sonuclar[0]
    print("⭐ YORUM")
    tf = taban["fight"]["bilek_sifir_klip_orani"]
    tn = taban["nonfight"]["bilek_sifir_klip_orani"]
    if tf > tn + 0.1:
        print(f"  ⚠ Poz, KAVGADA normalden BELİRGİN daha çok başarısız "
              f"(%{tf:.0%} vs %{tn:.0%}).")
        print("    Sebep muhtemelen tıkanma + hareket bulanıklığı: bedenler")
        print("    iç içe geçiyor ve sinyal en çok gerektiği anda kayboluyor.")
    else:
        print(f"  Poz başarısızlığı sınıfa bağlı DEĞİL (%{tf:.0%} vs %{tn:.0%}) —")
        print("    yani genel bir poz/örnekleme sınırı, kavgaya özgü değil.")

    en_iyi = min(sonuclar, key=lambda s: s["fight"]["bilek_sifir_klip_orani"])
    print(f"\n  En iyi yapılandırma: {en_iyi['yapilandirma']}")
    print(f"    kavgada bilek=0 klip oranı: %{tf:.0%} → "
          f"%{en_iyi['fight']['bilek_sifir_klip_orani']:.0%}")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "deney": "iskelet teşhisi — bilek sinyali neden sıfır",
        "veri_seti": "RWF-2000 val",
        "klip_sinif_basina": args.klip,
        "hipotezler": {
            "H1": "örnekleme seyrek (4 FPS) — hızlı hareket araya düşüyor",
            "H3": "kırpıntı çözünürlüğü düşük (192 px)",
            "H4": "poz güven eşiği sıkı (0.25)",
        },
        "sonuclar": sonuclar,
        "sure_s": round(time.time() - t0, 1),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"iskelet_teshis_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
