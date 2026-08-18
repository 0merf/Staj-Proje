"""Çıkarım worker'ının YALNIZ BAŞINA kapasitesi.

Cevaplanan soru
---------------
Boru hattında çıkarım ~2 kare/sn işliyor. İzole ölçümde poz 2.77 ms/kare
çıkmıştı — 15-100 kat fark. İki hipotez var ve ayrılmaları şart:

    A) Tüketici GERÇEKTEN yavaş  →  optimizasyon çıkarımda
    B) ÇEKİŞME yavaşlatıyor      →  optimizasyon alımda / süreç ayrımında

Bu betik B'yi ortadan kaldırıyor: **alım katmanı çalışmazken** aynı
modeller, aynı kod yolu, aynı kameraların kareleriyle ölçüyor. Çıkan
sayı "bu makinede çıkarımın tavanı" oluyor.

Ölçmeden optimizasyon aramak bugün üçüncü kez aynı hata olurdu
(GPU örtüştürme ve GPU kırpıntı hipotezleri; ikisi de makuldü, ikisi de
ölçümle çürüdü).

⚠ TEMSİLİ ÖRNEKLEM
Kareler **20 kameranın hepsinden** ve gerçek çiftlik oranında alınıyor.
Yalnızca kalabalık kameralardan örneklemek poz maliyetini 3 katına
çıkarıyordu (P-15'in tekrarı, bugün bir kez daha yaşandı).

Kullanım
--------
    uv run python scripts/benchmark_consumer.py
    uv run python scripts/benchmark_consumer.py --frames 120 --batch 8
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import av
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from sentinel.config import settings  # noqa: E402
from sentinel.core.preprocess import letterbox  # noqa: E402
from sentinel.inference.tracker.botsort import BotSortTracker  # noqa: E402
from sentinel.inference.worker import build_detector, build_pose_estimator  # noqa: E402


def kareler_yukle(kamera_sayisi: int, kamera_basina: int) -> list[tuple[str, np.ndarray]]:
    """Her kameradan eşit sayıda kare — gerçek çiftlik karışımı."""
    cikti: list[tuple[str, np.ndarray]] = []
    for n in range(1, kamera_sayisi + 1):
        kamera = f"cam-{n:02d}"
        yol = PROJECT_ROOT / "data" / "videos" / f"{kamera}.mp4"
        if not yol.is_file():
            continue
        kap = av.open(str(yol))
        akis = kap.streams.video[0]
        alinan = 0
        for i, kare in enumerate(kap.decode(akis)):
            if alinan >= kamera_basina:
                break
            if i % 23:  # dağıtık örnekleme — hep aynı sahneyi almayalım
                continue
            cikti.append((kamera, letterbox(kare.to_ndarray(format="bgr24"))[0]))
            alinan += 1
        kap.close()
    return cikti


def main() -> int:
    ap = argparse.ArgumentParser(description="Çıkarım kapasitesi (alım YOK)")
    ap.add_argument("--cameras", type=int, default=20)
    ap.add_argument("--per-camera", type=int, default=6)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    print("ÇIKARIM KAPASİTESİ — alım katmanı ÇALIŞMIYOR")
    print("=" * 60)
    print("Kareler yükleniyor (20 kameradan eşit)...")
    kareler = kareler_yukle(args.cameras, args.per_camera)
    if not kareler:
        print("HATA: kare yok", file=sys.stderr)
        return 1
    kamera_sayisi = len({k for k, _ in kareler})
    print(f"  {len(kareler)} kare · {kamera_sayisi} kamera\n")

    dedektor = build_detector(
        str(settings.detector_weights),
        backend=settings.detector_backend,
        device="cuda:0",
        half=True,
        imgsz=640,
        conf=settings.detector_conf_threshold,
    )
    poz = build_pose_estimator(str(settings.pose_weights), device="cuda:0", half=True)
    takipci = BotSortTracker(frame_rate=int(settings.target_fps))
    dedektor.warmup(args.batch)
    poz.warmup(settings.pose_crop_batch)

    asamalar: dict[str, list[float]] = {"tespit": [], "poz": [], "takip": []}
    kisi_toplam = 0
    kare_toplam = 0
    t_basla = time.perf_counter()

    for _tur in range(args.rounds):
        for i in range(0, len(kareler), args.batch):
            grup = kareler[i : i + args.batch]
            adlar = [k for k, _ in grup]
            goruntuler = [g for _, g in grup]

            t0 = time.perf_counter()
            tespitler = dedektor.detect(goruntuler)
            asamalar["tespit"].append((time.perf_counter() - t0) / len(grup) * 1000)
            kisi_toplam += sum(len(d) for d in tespitler)

            t0 = time.perf_counter()
            poz.estimate(goruntuler, tespitler)
            asamalar["poz"].append((time.perf_counter() - t0) / len(grup) * 1000)

            t0 = time.perf_counter()
            for ad, d in zip(adlar, tespitler, strict=True):
                takipci.update(ad, d, time.time())
            asamalar["takip"].append((time.perf_counter() - t0) / len(grup) * 1000)
            kare_toplam += len(grup)

    gecen = time.perf_counter() - t_basla
    poz.close()
    dedektor.close()

    def p50(ad: str) -> float:
        return round(statistics.median(asamalar[ad]), 2)

    toplam_ms = p50("tespit") + p50("poz") + p50("takip")
    rapor = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "Faz 1 / Gün 15",
        "description": "Çıkarım worker'ının alım çekişmesi OLMADAN kapasitesi",
        "kare_sayisi": kare_toplam,
        "kamera_sayisi": kamera_sayisi,
        "batch": args.batch,
        "kare_basina_kisi": round(kisi_toplam / kare_toplam, 2),
        "asamalar_ms_p50": {ad: p50(ad) for ad in asamalar},
        "kare_basina_toplam_ms": round(toplam_ms, 2),
        "kapasite_fps": round(kare_toplam / gecen, 1),
        "teorik_tavan_fps": round(1000.0 / toplam_ms, 1) if toplam_ms else 0.0,
    }

    print(f"  kare başına {rapor['kare_basina_kisi']} kişi\n")
    for ad in ("tespit", "poz", "takip"):
        print(f"    {ad:8} {p50(ad):7.2f} ms/kare")
    print(f"    {'TOPLAM':8} {toplam_ms:7.2f} ms/kare")
    print()
    print(f"  ÇIKARIM KAPASİTESİ (alım yokken): {rapor['kapasite_fps']} kare/sn")
    print("  20 kamera için gereken           : 80 kare/sn")
    print(f"  kamera başına düşen              : {rapor['kapasite_fps'] / 20:.2f} FPS")

    cikti = (
        args.out or PROJECT_ROOT / "benchmarks" / f"consumer_{datetime.now():%Y%m%d}.json"
    ).resolve()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKaydedildi: {cikti.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
