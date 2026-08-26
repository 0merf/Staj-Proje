"""RWF-2000 çevrimdışı değerlendirmesi — K5 ve eşik kalibrasyonunun ikinci yarısı.

Neden bu betik
--------------
`calibrate_aggression.py` "bu ayar normal görüntüde ne kadar susuyor"
sorusunu cevaplıyor. Tek başına yanıltıcıdır: yanlış alarmı sıfıra
indirmenin en kolay yolu modülü tamamen sağır etmektir.

Bu betik ikinci yarıyı ölçer: **kavga klipleri hâlâ yakalanıyor mu.**

Ne yapar
--------
RWF-2000'in `val` bölümünden N kavga + N normal klip alır ve her birini
canlı boru hattının aynısından geçirir:

    kare örnekleme → YOLO26 tespit → BoT-SORT takip → YOLO26-pose
      → kişi/çift özellikleri → TirmanmaSkorlayici

Her klip için ulaşılan **azami skor** kaydedilir, sonra kavga ve normal
dağılımları karşılaştırılır: ROC-AUC, en iyi eşik, o eşikte F1.

⚠ NEDEN `val` BÖLÜMÜ
`train` bölümü sahte kamera cam-17'yi beslemek için kullanılıyor.
Eşiği aynı kliplerle hem ayarlayıp hem değerlendirmek, ezberi başarı
sanmaktır. Ölçüm ancak görülmemiş veride anlamlıdır.

⚠ NE ÖLÇMEZ — ERKEN UYARI AVANSI (K8)
RWF etiketi klip seviyesindedir: "bu 5 saniyede kavga var". Kavganın
kaçıncı saniyede başladığı etiketli değil. Avans ölçümü için elle
etiketlenmiş bir alt küme gerekiyor (PLAN §6.5.5 adım 5) — ayrı iş.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI olmalı, GPU'yu paylaşmasın.

Kullanım
--------
    uv run python scripts/evaluate_rwf.py --klip 40
    uv run python scripts/evaluate_rwf.py --klip 100 --fps 4
"""

from __future__ import annotations

import argparse
import json
import random
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


def _roc_auc(pozitif: list[float], negatif: list[float]) -> float:
    """ROC eğrisi altındaki alan — Mann-Whitney U ile.

    ⚠ EŞİKTEN BAĞIMSIZ olduğu için burada doğru metrik bu. Doğruluk
    veya F1, seçilen eşiğe bağlıdır; AUC "rastgele bir kavga klibi,
    rastgele bir normal klipten yüksek skor alma olasılığı"nı verir.
    0.5 = yazı tura, 1.0 = kusursuz ayrım.
    """
    if not pozitif or not negatif:
        return float("nan")
    kazanc = 0.0
    for p in pozitif:
        for n in negatif:
            kazanc += 1.0 if p > n else (0.5 if p == n else 0.0)
    return kazanc / (len(pozitif) * len(negatif))


def _en_iyi_esik(pozitif: list[float], negatif: list[float]) -> tuple[float, float, float, float]:
    """F1'i en yükseğe çıkaran eşiği arar. → (esik, f1, duyarlilik, kesinlik)"""
    adaylar = sorted({round(v, 3) for v in [*pozitif, *negatif]})
    en_iyi = (0.0, 0.0, 0.0, 0.0)
    for esik in adaylar:
        tp = sum(1 for v in pozitif if v >= esik)
        fp = sum(1 for v in negatif if v >= esik)
        fn = len(pozitif) - tp
        if tp == 0:
            continue
        kesinlik = tp / (tp + fp)
        duyarlilik = tp / (tp + fn)
        f1 = 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
        if f1 > en_iyi[1]:
            en_iyi = (esik, f1, duyarlilik, kesinlik)
    return en_iyi


def _klip_skorla(
    yol: Path,
    *,
    dedektor: Any,
    poz: Any,
    ayarlar: dict[str, Any],
    ornek_fps: float,
    imgsz: int,
) -> dict[str, float]:
    """Bir klibi boru hattından geçirir, ayar başına azami skoru döndürür."""
    import cv2

    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    adim = max(1, round(kaynak_fps / ornek_fps))

    # ⚠ Klip başına TAZE takipçi ve pencere: klipler birbirinden
    # bağımsız, önceki klibin izleri sonrakine sızmamalı.
    takipci = BotSortTracker(frame_rate=int(ornek_fps))
    depo = PencereDeposu()
    skorlayicilar = {ad: TirmanmaSkorlayici(e) for ad, e in ayarlar.items()}
    azami = dict.fromkeys(ayarlar, 0.0)

    kare_no = 0
    kamera = yol.stem
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        # ⚠ Canlı boru hattıyla AYNI ön işleme: model uzayında letterbox.
        # Farklı ön işleme = farklı tespitler = kıyaslanamaz ölçüm.
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps

        tespitler = dedektor.detect([hazir])[0]
        izler = takipci.update(kamera, tespitler, ts)
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                d = iz.detection
                bbox = (d.x1, d.y1, d.x2, d.y2)
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera,
                    iz.track_id,
                    Ornek(
                        ts=ts,
                        bbox=bbox,
                        kp=kp,
                        olcek=sk.govde_boyu(kp, bbox) if kp is not None else None,
                        ayak=sk.ayak_noktasi(bbox),
                    ),
                )
            kisiler = [cikar(depo.al(kamera, t.track_id)) for t in izler]  # type: ignore[arg-type]
            ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(kamera))
            for ad, s in skorlayicilar.items():
                for sonuc in s.degerlendir(kamera, kisiler, ciftler, ts):
                    azami[ad] = max(azami[ad], sonuc.skor)
        kare_no += 1

    cap.release()
    return azami


def main() -> int:
    ap = argparse.ArgumentParser(description="RWF-2000 çevrimdışı değerlendirme")
    ap.add_argument("--klip", type=int, default=40, help="her sınıftan kaç klip")
    ap.add_argument("--fps", type=float, default=4.0, help="örnekleme hızı (canlıyla aynı)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--tohum", type=int, default=42)
    args = ap.parse_args()

    if not RWF.is_dir():
        print(f"RWF val bölümü yok: {RWF}", file=sys.stderr)
        return 1

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from calibrate_aggression import _ayarlar

    ayarlar = _ayarlar()

    # Klip seçimi tohumlu: ölçüm tekrar üretilebilir olmalı.
    rng = random.Random(args.tohum)  # noqa: S311 — kriptografi değil, örnekleme
    kavga = sorted((RWF / "fight").glob("*.avi"))
    normal = sorted((RWF / "nonfight").glob("*.avi"))
    rng.shuffle(kavga)
    rng.shuffle(normal)
    kavga, normal = kavga[: args.klip], normal[: args.klip]
    print(f"{len(kavga)} kavga + {len(normal)} normal klip · örnekleme {args.fps} FPS")

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt", imgsz=args.imgsz, half=True
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "backend" / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    sonuclar: dict[str, dict[str, list[float]]] = {
        ad: {"kavga": [], "normal": []} for ad in ayarlar
    }
    t0 = time.time()
    for etiket, klipler in (("kavga", kavga), ("normal", normal)):
        for i, yol in enumerate(klipler, 1):
            azami = _klip_skorla(
                yol,
                dedektor=dedektor,
                poz=poz,
                ayarlar=ayarlar,
                ornek_fps=args.fps,
                imgsz=args.imgsz,
            )
            for ad, v in azami.items():
                sonuclar[ad][etiket].append(v)
            print(f"\r  {etiket} {i}/{len(klipler)}", end="", flush=True)
        print()
    sure = time.time() - t0
    print(f"\n{2 * args.klip} klip · {sure:.0f} sn ({sure / (2 * args.klip):.1f} sn/klip)\n")

    print(
        f"{'AYAR':<7} {'kavga p50':>10} {'normal p50':>11} {'AUC':>7} "
        f"{'en iyi eşik':>12} {'F1':>6} {'duyarlılık':>11} {'kesinlik':>9}"
    )
    ozet: dict[str, object] = {}
    for ad in ayarlar:
        k, n = sonuclar[ad]["kavga"], sonuclar[ad]["normal"]
        auc = _roc_auc(k, n)
        esik, f1, duy, kes = _en_iyi_esik(k, n)
        kp50 = sorted(k)[len(k) // 2]
        np50 = sorted(n)[len(n) // 2]
        print(
            f"{ad:<7} {kp50:>10.3f} {np50:>11.3f} {auc:>7.3f} "
            f"{esik:>12.3f} {f1:>6.3f} {duy:>11.3f} {kes:>9.3f}"
        )
        ozet[ad] = {
            "kavga_p50": round(kp50, 4),
            "normal_p50": round(np50, 4),
            "auc": round(auc, 4),
            "en_iyi_esik": esik,
            "f1": round(f1, 4),
            "duyarlilik": round(duy, 4),
            "kesinlik": round(kes, 4),
            "kavga_skorlari": [round(v, 4) for v in k],
            "normal_skorlari": [round(v, 4) for v in n],
        }

    print("\n⚠ AUC eşikten bağımsızdır — asıl kıyas ölçüsü budur.")
    print("  K5 hedefi: F1 ≥ 0.85 (PLAN §1.4)")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "klip_sayisi_sinif_basina": args.klip,
        "bolum": "val",
        "ornekleme_fps": args.fps,
        "imgsz": args.imgsz,
        "tohum": args.tohum,
        "sure_s": round(sure, 1),
        "sonuc": ozet,
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"rwf_eval_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
