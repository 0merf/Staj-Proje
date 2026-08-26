"""Özellik dağılımlarını canlı akıştan ölçer — yanlış alarmın kaynağını bulur.

Neden bu betik
--------------
K7 kriteri "kamera-saat başına ≤3 yanlış alarm" diyor. Ölçülen: **26**.
Kırılıma bakınca en büyük kalem saldırganlık uyarıları ve bunlar VIRAT
otoparkında, PETS meydanında çıkıyor — kavganın olmadığı yerlerde.

Eşikleri körlemesine indirmek yanlış yol olurdu: eşiği düşürmek modülü
susturur ama gerçek kavgayı da kaçırtır, üstelik SEBEBİ öğrenmemiş
oluruz. Önce girdiye bakmak gerekiyor: saldırganlık skorunu şişiren
özellik hangisi ve o özellik gerçekten hareketi mi ölçüyor, yoksa
keypoint gürültüsünü mü?

Ne yapar
--------
Canlı `inference.results` akışını **okur** (tüketmez — `XREAD`, tüketici
grubu değil; analytics worker'ın işini bölmez), analytics worker'ın
kullandığı pencere deposunun aynısını besler ve her özellik için
dağılım çıkarır: p50 / p90 / p99 / azami.

Asıl aranan şey `bilek_hizi_azami`'nin dağılımı. Bu özellik pencere
içindeki **azami** değeri alıyor; azami, gürültüye en açık istatistiktir.
Dağılımın kuyruğu gövdesinden kopuksa (p99 ≫ p90), ölçtüğümüz şey
hareket değil sıçrayan bir keypoint'tir.

Kullanım
--------
    uv run python scripts/benchmark_features.py --sure 180
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# Bu üçü doğrudan tırmanma skoruna giriyor (aggression.py · DOYUM_*).
IZLENEN = (
    "bilek_hizi_azami",
    "bilek_sarsintisi",
    "hareket_enerjisi",
    "govde_hizi",
    "kol_yuksekligi_azami",
    "govde_egimi",
    "govde_egimi_degisimi",
    "en_boy_orani",
    "tamlik",
)


def _dagilim(degerler: list[float]) -> dict[str, float] | None:
    if not degerler:
        return None
    d = sorted(degerler)
    return {
        "n": len(d),
        "p50": round(statistics.median(d), 3),
        "p90": round(d[int(len(d) * 0.90)], 3),
        "p99": round(d[min(len(d) - 1, int(len(d) * 0.99))], 3),
        "azami": round(d[-1], 3),
        # ⚠ Kuyruk oranı: p99/p90. 1'e yakınsa dağılım düzgün,
        # büyükse birkaç aykırı örnek dağılımı domine ediyor demektir.
        "kuyruk_orani": round(
            d[min(len(d) - 1, int(len(d) * 0.99))] / max(d[int(len(d) * 0.90)], 1e-6), 2
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="canlı özellik dağılımı")
    ap.add_argument("--sure", type=float, default=180.0, help="saniye")
    ap.add_argument("--kamera", default=None, help="tek kamera filtrele")
    args = ap.parse_args()

    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.bus.streams import connect

    r = connect()
    depo = PencereDeposu()

    # özellik adı → değer listesi · ayrıca kamera bazlı
    genel: dict[str, list[float]] = defaultdict(list)
    kamera_bazli: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    # Düşük güvenli keypoint oranı — gürültü hipotezinin doğrudan sınavı
    kp_toplam = kp_dusuk = 0
    kare = 0

    son = "$"
    t0 = time.time()
    bitis = t0 + args.sure
    print(f"{args.sure:.0f} sn dinleniyor... (analytics worker'ın işi bölünmüyor)", flush=True)

    while time.time() < bitis:
        for _, kayitlar in r.xread({"inference.results": son}, block=2000, count=500) or []:
            for eid, alan in kayitlar:
                son = eid
                camera = alan.get("cam", "")
                if not camera or (args.kamera and camera != args.kamera):
                    continue
                ts = float(alan.get("ts", 0.0)) or time.time()
                kare += 1
                for d in json.loads(alan.get("data", "{}")).get("detections", []):
                    track_id = d.get("id")
                    if track_id is None:
                        continue
                    bbox = tuple(float(v) for v in d["bbox"])
                    kp = d.get("kp")
                    kp_dizi = np.asarray(kp, dtype=np.float64) if kp else None
                    if kp_dizi is not None:
                        kp_toplam += len(kp_dizi)
                        kp_dusuk += int((kp_dizi[:, 2] < sk.KP_MIN_CONF).sum())
                    pencere = depo.ekle(
                        camera,
                        int(track_id),
                        Ornek(
                            ts=ts,
                            bbox=bbox,  # type: ignore[arg-type]
                            kp=kp_dizi,
                            olcek=sk.govde_boyu(kp_dizi, bbox) if kp_dizi is not None else None,  # type: ignore[arg-type]
                            ayak=sk.ayak_noktasi(bbox),  # type: ignore[arg-type]
                        ),
                    )
                    oz = cikar(pencere)
                    for ad in IZLENEN:
                        deger = getattr(oz, ad)
                        if deger is not None:
                            genel[ad].append(float(deger))
                            kamera_bazli[camera][ad].append(float(deger))
        depo.buda(time.time())

    sure = time.time() - t0
    print(f"\n{kare} kare · {sure:.0f} sn · {len(kamera_bazli)} kamera")
    if kp_toplam:
        print(
            f"keypoint: {kp_toplam} adet, %{kp_dusuk / kp_toplam * 100:.1f}'i güven < {sk.KP_MIN_CONF}"
        )

    print(
        f"\n{'ÖZELLİK':<24} {'n':>7} {'p50':>8} {'p90':>8} {'p99':>8} {'azami':>9} {'p99/p90':>8}"
    )
    ozet: dict[str, object] = {}
    for ad in IZLENEN:
        d = _dagilim(genel[ad])
        if d is None:
            print(f"{ad:<24} {'—':>7}")
            continue
        ozet[ad] = d
        print(
            f"{ad:<24} {d['n']:>7} {d['p50']:>8.3f} {d['p90']:>8.3f} "
            f"{d['p99']:>8.3f} {d['azami']:>9.3f} {d['kuyruk_orani']:>8.2f}"
        )

    # ─── Doyum eşikleriyle karşılaştır ───
    # aggression.py bu değerlerde bileşeni 1.0'a sabitliyor. p90 doyumun
    # üstündeyse "her zaman doygun" demektir: özellik bilgi taşımıyor,
    # sabit 1.0 üretiyor ve skor sahte biçimde yükseliyor.
    from sentinel.analytics import aggression as agg

    print("\nDOYUM DENETİMİ — p90 doyumun üstündeyse özellik bilgi taşımıyor")
    for ad, doyum in (
        ("bilek_hizi_azami", agg.DOYUM_BILEK_HIZ),
        ("bilek_sarsintisi", agg.DOYUM_BILEK_SARSINTI),
        ("hareket_enerjisi", agg.DOYUM_ENERJI),
    ):
        d = _dagilim(genel[ad])
        if d is None:
            continue
        oran = d["p90"] / doyum
        durum = "⚠ DOYGUN" if oran >= 1.0 else ("⚠ sınırda" if oran >= 0.7 else "sağlıklı")
        print(f"  {ad:<22} p90={d['p90']:.2f}  doyum={doyum:.2f}  p90/doyum={oran:.2f}  {durum}")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "sure_s": round(sure, 1),
        "kare": kare,
        "kamera_sayisi": len(kamera_bazli),
        "kp_toplam": kp_toplam,
        "kp_dusuk_guven_orani": round(kp_dusuk / kp_toplam, 4) if kp_toplam else None,
        "genel": ozet,
        "kamera_bazli": {
            k: {a: _dagilim(v[a]) for a in IZLENEN if v[a]} for k, v in sorted(kamera_bazli.items())
        },
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"features_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
