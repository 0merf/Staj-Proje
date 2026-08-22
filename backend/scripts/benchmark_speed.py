"""Gerçek hız dağılımı — koşma eşiği kalibrasyonu.

Neden bu ölçüm
--------------
Koşma eşiği (1.5 gövde/sn) FİZİKTEN türetilmişti:

    yürüme ~1.4 m/s ÷ ortalama boy 1.7 m ≈ 0.8 gövde/sn
    koşu   ~3.0 m/s ÷ 1.7 m              ≈ 1.8 gövde/sn

Makul bir akıl yürütme ama **gerçek verimizle doğrulanmadı.** Kullanıcı
panelde şunu fark etti: cam-09'da (Oxford Town Centre, yoğun cadde)
YÜRÜYEN insanlar 1.58-2.21 gövde/sn çıkıyor ve eşiği aşıyor.

Bu, projede tekrar eden hata deseninin bir örneği daha: doğru görünen
bir hesap, ölçülmeden kullanılırsa yanlış olabiliyor (P-14 en-boy oranı,
P-15 batch boyutu, P-27 match_thresh).

Eşik fizikten değil, **kendi verimizin dağılımından** türetilmeli.

Ne ölçüyor
----------
Canlı `inference.results` akışını dinler, özellik motorunu besler ve
kamera başına `govde_hizi` dağılımını çıkarır. Çıktı: hangi persentilin
hangi hıza denk geldiği.

⚠ Yer gerçeği YOK. Bu ölçüm "koşan kim" demiyor; "bu kameralarda hızlar
nasıl dağılıyor" diyor. Eşiği persentile bağlamak, mutlak bir sayıya
bağlamaktan daha savunulabilir — ama mükemmel değil ve raporda böyle
yazılacak.

Kullanım
--------
    uv run python scripts/benchmark_speed.py --duration 90
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from sentinel.analytics.features import skeleton as sk  # noqa: E402
from sentinel.analytics.features.person import cikar  # noqa: E402
from sentinel.analytics.features.window import Ornek, PencereDeposu  # noqa: E402
from sentinel.bus.streams import connect  # noqa: E402
from sentinel.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Hız dağılımı ölçümü")
    ap.add_argument("--duration", type=float, default=90.0)
    ap.add_argument("--min-tamlik", type=float, default=0.25)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    client = connect()
    depo = PencereDeposu()
    hizlar: dict[str, list[float]] = defaultdict(list)

    print("HIZ DAĞILIMI — koşma eşiği kalibrasyonu")
    print("=" * 62)
    print(f"{args.duration:.0f} saniye dinleniyor (canlı sistem çalışıyor olmalı)...\n")

    son_id = "$"
    bitis = time.monotonic() + args.duration
    while time.monotonic() < bitis:
        yanit = client.xread({settings.stream_results: son_id}, count=64, block=500)
        if not yanit:
            continue
        for _akis, girdiler in yanit:  # type: ignore[union-attr]
            for mid, alanlar in girdiler:
                son_id = mid
                camera = alanlar.get("cam", "")
                ts = float(alanlar.get("ts", 0.0)) or time.time()
                veri = json.loads(alanlar.get("data", "{}"))
                for d in veri.get("detections", []):
                    tid = d.get("id")
                    if tid is None:
                        continue
                    bbox = tuple(float(v) for v in d["bbox"])
                    kp = d.get("kp")
                    kp_dizi = np.asarray(kp, dtype=np.float64) if kp else None
                    pencere = depo.ekle(
                        camera,
                        int(tid),
                        Ornek(
                            ts=ts,
                            bbox=bbox,  # type: ignore[arg-type]
                            kp=kp_dizi,
                            olcek=(
                                sk.govde_boyu(kp_dizi, bbox)  # type: ignore[arg-type]
                                if kp_dizi is not None
                                else None
                            ),
                            ayak=sk.ayak_noktasi(bbox),  # type: ignore[arg-type]
                        ),
                    )
                    o = cikar(pencere)
                    if o.govde_hizi is not None and o.tamlik >= args.min_tamlik:
                        hizlar[camera].append(o.govde_hizi)

    client.close()

    if not hizlar:
        print("HATA: hiç örnek toplanamadı — sistem çalışıyor mu?", file=sys.stderr)
        return 1

    def p(veri: list[float], q: float) -> float:
        s = sorted(veri)
        return s[min(len(s) - 1, int(len(s) * q))]

    tumu = [h for v in hizlar.values() for h in v]

    print(f"{'KAMERA':<10}{'örnek':>7}{'p50':>8}{'p90':>8}{'p95':>8}{'p99':>8}{'azami':>8}")
    print("-" * 62)
    for cam in sorted(hizlar):
        v = hizlar[cam]
        if len(v) < 20:
            continue
        print(
            f"{cam:<10}{len(v):>7}{p(v, 0.50):>8.2f}{p(v, 0.90):>8.2f}"
            f"{p(v, 0.95):>8.2f}{p(v, 0.99):>8.2f}{max(v):>8.2f}"
        )

    print("-" * 62)
    print(
        f"{'TÜMÜ':<10}{len(tumu):>7}{p(tumu, 0.50):>8.2f}{p(tumu, 0.90):>8.2f}"
        f"{p(tumu, 0.95):>8.2f}{p(tumu, 0.99):>8.2f}{max(tumu):>8.2f}"
    )

    mevcut_esik = 1.5
    asan = sum(1 for h in tumu if h >= mevcut_esik)
    print()
    print(f"  Mevcut eşik {mevcut_esik}: örneklerin %{asan / len(tumu) * 100:.1f}'i aşıyor")
    print(f"  p95 = {p(tumu, 0.95):.2f}  ·  p99 = {p(tumu, 0.99):.2f}")
    print()
    print("  ⚠ Yer gerçeği YOK: bu tablo 'koşan kim' demiyor, hızların")
    print("    nasıl dağıldığını gösteriyor. Eşiği persentile bağlamak")
    print("    mutlak sayıya bağlamaktan savunulabilir ama mükemmel değil.")

    rapor = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "Faz 1 / Gün 15",
        "description": "govde_hizi dağılımı — koşma eşiği kalibrasyonu",
        "duration_s": args.duration,
        "min_tamlik": args.min_tamlik,
        "birim": "gövde boyu / saniye",
        "mevcut_esik": mevcut_esik,
        "mevcut_esigi_asan_yuzde": round(asan / len(tumu) * 100, 1),
        "genel": {
            "ornek": len(tumu),
            "p50": round(p(tumu, 0.50), 3),
            "p90": round(p(tumu, 0.90), 3),
            "p95": round(p(tumu, 0.95), 3),
            "p99": round(p(tumu, 0.99), 3),
            "azami": round(max(tumu), 3),
            "ortalama": round(statistics.fmean(tumu), 3),
        },
        "kamera_bazinda": {
            cam: {
                "ornek": len(v),
                "p50": round(p(v, 0.50), 3),
                "p95": round(p(v, 0.95), 3),
                "p99": round(p(v, 0.99), 3),
            }
            for cam, v in sorted(hizlar.items())
            if len(v) >= 20
        },
    }
    cikti = (
        args.out or PROJECT_ROOT / "benchmarks" / f"speed_{datetime.now():%Y%m%d}.json"
    ).resolve()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKaydedildi: {cikti.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
