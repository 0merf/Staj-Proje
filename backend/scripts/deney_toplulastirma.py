"""TOPLULAŞTIRMA DENEYİ — `azami` gürültüyü mü ölçüyor?

Bulgu zinciri (buraya nasıl geldik)
------------------------------------
1. `evaluate_kaskad.py` : kural kapısı kavgaların %52'sini eliyor
2. `diagnose_iskelet.py`: poz ÇALIŞIYOR (%89.6) — sorun poz değil
3. `kalibre_rwf.py`     : kavga ve normal dağılımları NEREDEYSE AYNI

        NORMAL              KAVGA
     p50    p90    p99   p50    p90    p99
    0.807  3.011  11.36  1.199  2.890  11.31    ← bilek_hizi_azami

⭐ İki gözlem
   · **p99 her iki sınıfta da 11.3** — saniyede 11 gövde boyu bilek
     hareketi fiziksel olarak imkânsız. Bunlar eklem tahmini HATASI.
   · **p50 farkı gerçek** (0.807 → 1.199, %49) ama p90/p99'da kayboluyor.

Hipotez
-------
**H · `azami` (max) toplulaştırması gürültüyü ölçüyor.**

`person.py` pencere içindeki bilek hızlarının AZAMİSİNİ alıyor:

    ozellik.bilek_hizi_azami = max(bilek)

Gerekçesi kodda yazılı ve makul görünüyordu:

    # AZAMİ, ortalama değil: vuruş anlık bir olaydır ve
    # ortalama onu 3 saniyeye yayıp söndürür.

⚠ Ama `max` aynı zamanda **en gürültülü** istatistiktir: tek bir bozuk
eklem tüm pencereyi ele geçirir. Vuruşu korumak isterken eklem
hatasını yükseltmiş olabiliriz.

Bu betik ne yapıyor
-------------------
Aynı ham hız serisinden **beş farklı toplulaştırma** üretip her birinin
kavga/normal ayırt etme gücünü (ROC-AUC) ölçüyor:

    azami   — mevcut üretim davranışı
    p90     — üst uç ama tek nokta değil
    p75     — daha da dayanıklı
    medyan  — tamamen dayanıklı, ama vuruşu söndürebilir
    ort     — karşılaştırma için

⚠ HANGİSİNİN KAZANACAĞINI TAHMİN ETMİYORUZ. `max` kazanırsa hipotez
çürür ve gerekçesi zaten kodda yazılı olan tasarım doğrulanmış olur —
bu da bir sonuçtur.

⚠ TEK BAŞINA AUC YETMEZ, bu yüzden gürültü göstergesi de basılıyor:
p99/p50 oranı. Yüksek oran = uzun kuyruk = eklem hatası baskın.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI (GPU paylaşılmamalı).

Kullanım
--------
    uv run python scripts/deney_toplulastirma.py --klip 100
"""

from __future__ import annotations

import argparse
import bisect
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
RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000" / "train"

TOHUM = 42


def _yuzdelik(sirali: list[float], oran: float) -> float:
    if not sirali:
        return 0.0
    return sirali[min(len(sirali) - 1, int(len(sirali) * oran))]


TOPLULASTIRMALAR: dict[str, Any] = {
    "azami (üretim)": lambda d: d[-1] if d else 0.0,
    "p90": lambda d: _yuzdelik(d, 0.90),
    "p75": lambda d: _yuzdelik(d, 0.75),
    "medyan": lambda d: statistics.median(d) if d else 0.0,
    "ortalama": lambda d: statistics.fmean(d) if d else 0.0,
}


def _auc(poz: list[float], neg: list[float]) -> float:
    if not poz or not neg:
        return float("nan")
    n = sorted(neg)
    t = 0.0
    for p in poz:
        k = bisect.bisect_left(n, p)
        e = bisect.bisect_right(n, p) - k
        t += k + 0.5 * e
    return t / (len(poz) * len(neg))


def _klip_hizlari(
    yol: Path, *, dedektor: Any, poz: Any, ornek_fps: float, imgsz: int
) -> dict[str, list[float]]:
    """Bir klipteki TÜM ham hız örneklerini toplar (toplulaştırmadan).

    ⚠ `person.py · cikar()` çağrılmıyor — o zaten `max` uyguluyor.
    Toplulaştırmayı karşılaştırabilmek için ondan ÖNCEKİ seriye
    ihtiyaç var. (Aynı ilke: `kalibre_rwf.py` bantlamadan öncesine
    bakıyordu.)
    """
    import cv2
    import numpy as np

    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    adim = max(1, round(kaynak_fps / ornek_fps))
    takipci = BotSortTracker(frame_rate=int(max(1, ornek_fps)))
    depo = PencereDeposu()

    bilek: list[float] = []
    tum_eklem: list[float] = []
    kare_no = 0
    kamera = yol.stem
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps
        izler = takipci.update(kamera, dedektor.detect([hazir])[0], ts)
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                d = iz.detection
                bbox = (d.x1, d.y1, d.x2, d.y2)
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera, iz.track_id,
                    Ornek(
                        ts=ts, bbox=bbox, kp=kp,
                        olcek=sk.govde_boyu(kp, bbox) if kp is not None else None,
                        ayak=sk.ayak_noktasi(bbox),
                    ),
                )
            for iz in izler:
                pencere = depo.al(kamera, iz.track_id)
                if pencere is None:
                    continue
                olcek = pencere.olcek()
                if olcek is None or olcek <= 1e-6:
                    continue
                for onceki, sonraki in pencere.gecerli_ciftler():
                    if onceki.kp is None or sonraki.kp is None:
                        continue
                    dt = sonraki.ts - onceki.ts
                    for indeks in sk.BILEKLER:
                        a = sk.nokta(onceki.kp, indeks)
                        b = sk.nokta(sonraki.kp, indeks)
                        if a is None or b is None:
                            continue
                        bilek.append(float(np.linalg.norm(b - a) / dt / olcek))
                    n = min(len(onceki.kp), len(sonraki.kp))
                    for i in range(n):
                        a = sk.nokta(onceki.kp, i)
                        b = sk.nokta(sonraki.kp, i)
                        if a is None or b is None:
                            continue
                        tum_eklem.append(float(np.linalg.norm(b - a) / dt / olcek))
        kare_no += 1

    cap.release()
    return {"bilek": bilek, "tum_eklem": tum_eklem}


def main() -> int:
    ap = argparse.ArgumentParser(description="Toplulaştırma karşılaştırması")
    ap.add_argument("--klip", type=int, default=100, help="sınıf başına klip")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    # klip → {"bilek": [...], "tum_eklem": [...]}
    veriler: dict[str, list[dict[str, list[float]]]] = {"fight": [], "nonfight": []}
    t0 = time.time()
    for sinif in ("fight", "nonfight"):
        klipler = sorted((RWF / sinif).glob("*.avi"))
        random.Random(TOHUM).shuffle(klipler)  # noqa: S311 — kripto değil
        klipler = klipler[: args.klip]
        for i, yol in enumerate(klipler, 1):
            veriler[sinif].append(
                _klip_hizlari(yol, dedektor=dedektor, poz=poz,
                              ornek_fps=args.fps, imgsz=args.imgsz)
            )
            print(f"\r  {sinif} {i}/{len(klipler)} ({time.time() - t0:.0f} sn)",
                  end="", flush=True)
        print()

    sonuclar: list[dict[str, Any]] = []
    print(f"\n{'BÜYÜKLÜK':<12} {'TOPLULAŞTIRMA':<16} {'AUC':>7} "
          f"{'kavga p50':>10} {'normal p50':>11} {'p99/p50':>8}")
    for buyukluk in ("bilek", "tum_eklem"):
        for ad, fn in TOPLULASTIRMALAR.items():
            poz_d = [fn(sorted(k[buyukluk])) for k in veriler["fight"] if k[buyukluk]]
            neg_d = [fn(sorted(k[buyukluk])) for k in veriler["nonfight"] if k[buyukluk]]
            if not poz_d or not neg_d:
                continue
            auc = _auc(poz_d, neg_d)
            # ⚠ GÜRÜLTÜ GÖSTERGESİ: uzun kuyruk = eklem hatası baskın.
            # AUC tek başına hangi toplulaştırmanın SAĞLAM olduğunu
            # söylemiyor; bu oran söylüyor.
            hepsi = sorted(poz_d + neg_d)
            p99p50 = _yuzdelik(hepsi, 0.99) / max(statistics.median(hepsi), 1e-9)
            sonuclar.append({
                "buyukluk": buyukluk, "toplulastirma": ad,
                "auc": round(auc, 4),
                "kavga_p50": round(statistics.median(poz_d), 3),
                "normal_p50": round(statistics.median(neg_d), 3),
                "p99_p50_orani": round(p99p50, 2),
            })
            print(f"{buyukluk:<12} {ad:<16} {auc:>7.3f} "
                  f"{statistics.median(poz_d):>10.3f} "
                  f"{statistics.median(neg_d):>11.3f} {p99p50:>8.1f}")
        print()

    en_iyi = max(sonuclar, key=lambda s: s["auc"])
    uretim = next(
        (s for s in sonuclar
         if s["buyukluk"] == "bilek" and s["toplulastirma"] == "azami (üretim)"),
        None,
    )
    print("⭐ SONUÇ")
    print(f"  En iyi: {en_iyi['buyukluk']} · {en_iyi['toplulastirma']} "
          f"→ AUC {en_iyi['auc']:.3f}")
    if uretim:
        fark = en_iyi["auc"] - uretim["auc"]
        print(f"  Üretim (bilek · azami)      → AUC {uretim['auc']:.3f}")
        print(f"  Fark: {fark:+.3f}")
        if fark > 0.03:
            print("\n  ✅ HİPOTEZ DOĞRULANDI: `azami` gürültüyü ölçüyor.")
            print("     Dayanıklı toplulaştırma ayırt etme gücünü artırıyor.")
            print("     → `person.py` düzeltilmeli.")
        elif fark < 0.01:
            print("\n  ⚠ HİPOTEZ ÇÜRÜDÜ: `azami` en iyisi ya da farksız.")
            print("     Kodda yazılı gerekçe ('vuruş anlık bir olaydır')")
            print("     doğrulanmış oldu. Sorun başka yerde.")
        else:
            print("\n  ⚠ SONUÇSUZ: fark gürültü mertebesinde.")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "deney": "toplulaştırma karşılaştırması (azami vs dayanıklı)",
        "hipotez": "`azami` toplulaştırması eklem gürültüsünü ölçüyor",
        "veri_seti": "RWF-2000 train",
        "klip_sinif_basina": args.klip,
        "ornekleme_fps": args.fps,
        "sonuclar": sonuclar,
        "en_iyi": en_iyi,
        "uretim": uretim,
        "sure_s": round(time.time() - t0, 1),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"toplulastirma_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
