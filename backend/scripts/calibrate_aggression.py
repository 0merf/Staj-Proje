"""Tırmanma eşiklerini AYNI veri üzerinde yan yana kıyaslar.

Neden bu betik
--------------
Saldırganlık eşiklerini değiştirmenin tek yolu "değiştir–çalıştır–bak"tı.
Bunun iki kusuru var:

1. **Ölçüm zemini ortak değil.** İki ayarı arka arkaya denemek, aradaki
   farkı ayara mı yoksa o sırada kameralarda olan biten farklı sahneye
   mi borçlu olduğunu bilinmez kılar. Gün 8'de tam bu yüzden bir kazanç
   %-34 ölçülüp sonra %+43 çıkmıştı (`problems.md` P-17).
2. **Tek yönlü bakış.** Eşiği yükseltmek yanlış alarmı her zaman
   düşürür — bu bir keşif değil, aritmetik. Asıl soru gerçek olayların
   kaçının hayatta kaldığıdır.

Bu betik tek bir canlı akıştan besleyip **N ayarı aynı anda** skorluyor.
Aynı kareler, aynı izler, aynı pencereler → fark yalnızca ayardan.

⚠ BU BETİK NEYİ ÖLÇMEZ
----------------------
**Duyarlılığı ölçmez.** Kamera çiftliğindeki görüntülerin çoğu normal;
cam-17'nin bile yalnızca %10'u kavga ve döngü fazını bilmediğimiz için
canlı zamanı klip zamanına eşleyemiyoruz.

Yani buradan çıkan tek meşru sonuç şudur: *"bu ayar, kavganın OLMADIĞI
görüntüde ne kadar susuyor."* Kavgayı yakalayıp yakalamadığı ayrı bir
ölçümün konusu (RWF-2000 çevrimdışı değerlendirmesi, K5).

İkisi birlikte yapılmadan eşik değiştirilmemeli: yanlış alarmı sıfıra
indirmenin en kolay yolu modülü tamamen sağır etmektir.

Kullanım
--------
    uv run python scripts/calibrate_aggression.py --sure 300
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# ⚠ NORMAL OLDUĞU BİLİNEN KAMERALAR
# Yanlış alarm ancak burada anlamlı sayılır. cam-18 en güçlüsü: CUHK
# Avenue'nun EĞİTİM bölümü, tanımı gereği yalnızca normal davranış
# içeriyor ve cam-19 ile aynı sahne/açı — kontrol grubu.
NORMAL_KAMERALAR = (
    "cam-01",
    "cam-02",
    "cam-03",
    "cam-04",
    "cam-05",
    "cam-06",
    "cam-07",
    "cam-08",
    "cam-18",
)


def _ayarlar() -> dict[str, object]:
    """Kıyaslanacak eşik setleri.

    ESKI  : 26.08 öncesi davranış — ölü bölge yok, çarpımsal kapı yok.
            Kıyas tabanı; ne kadar iyileştiğimizi ancak buna göre
            söyleyebiliriz.
    BANT  : yalnızca ölü bölge (taban = ölçülen normal p90).
    KAPI  : yalnızca etkileşim kapısı.
    IKISI : ikisi birlikte — mevcut varsayılan.
    """
    from sentinel.analytics.aggression import VARSAYILAN

    eski = replace(
        VARSAYILAN,
        taban_bilek_hiz=0.0,
        taban_bilek_sarsinti=0.0,
        taban_enerji=0.0,
        taban_yaklasma=0.0,
        doyum_bilek_hiz=3.0,
        doyum_bilek_sarsinti=2.0,
        doyum_enerji=1.5,
        doyum_yaklasma=1.0,
        etkilesim_kapisi=False,
    )
    return {
        "ESKI": eski,
        "BANT": replace(
            eski,
            taban_bilek_hiz=VARSAYILAN.taban_bilek_hiz,
            taban_bilek_sarsinti=VARSAYILAN.taban_bilek_sarsinti,
            taban_enerji=VARSAYILAN.taban_enerji,
            taban_yaklasma=VARSAYILAN.taban_yaklasma,
            doyum_bilek_hiz=VARSAYILAN.doyum_bilek_hiz,
            doyum_bilek_sarsinti=VARSAYILAN.doyum_bilek_sarsinti,
            doyum_enerji=VARSAYILAN.doyum_enerji,
            doyum_yaklasma=VARSAYILAN.doyum_yaklasma,
        ),
        "KAPI": replace(eski, etkilesim_kapisi=True),
        "IKISI": VARSAYILAN,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="tırmanma eşiği kalibrasyonu")
    ap.add_argument("--sure", type=float, default=300.0)
    args = ap.parse_args()

    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.bus.streams import connect

    ayarlar = _ayarlar()
    skorlayicilar = {ad: TirmanmaSkorlayici(e) for ad, e in ayarlar.items()}  # type: ignore[arg-type]

    r = connect()
    depo = PencereDeposu()

    # ayar → kamera → seviye → adet
    sayac: dict[str, dict[str, dict[str, int]]] = {
        ad: defaultdict(lambda: defaultdict(int)) for ad in ayarlar
    }
    # ayar → skor listesi (normal kameralarda)
    normal_skor: dict[str, list[float]] = {ad: [] for ad in ayarlar}
    degerlendirme = 0

    son = "$"
    t0 = time.time()
    bitis = t0 + args.sure
    print(f"{args.sure:.0f} sn · {len(ayarlar)} ayar yan yana: {', '.join(ayarlar)}", flush=True)

    while time.time() < bitis:
        for _, kayitlar in r.xread({"inference.results": son}, block=2000, count=500) or []:
            for eid, alan in kayitlar:
                son = eid
                camera = alan.get("cam", "")
                if not camera:
                    continue
                ts = float(alan.get("ts", 0.0)) or time.time()

                kisiler = []
                for d in json.loads(alan.get("data", "{}")).get("detections", []):
                    track_id = d.get("id")
                    if track_id is None:
                        continue
                    bbox = tuple(float(v) for v in d["bbox"])
                    kp = d.get("kp")
                    kp_dizi = np.asarray(kp, dtype=np.float64) if kp else None
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
                    kisiler.append(cikar(pencere))

                if not kisiler:
                    continue
                # ⚠ Çift özellikleri BİR KEZ hesaplanıp tüm ayarlara
                # veriliyor: girdi ortak, fark yalnızca skorlamada.
                ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(camera))
                degerlendirme += 1
                for ad, skorlayici in skorlayicilar.items():
                    for s in skorlayici.degerlendir(camera, kisiler, ciftler, ts):
                        sayac[ad][camera][s.seviye] += 1
                        if camera in NORMAL_KAMERALAR:
                            normal_skor[ad].append(s.skor)
        depo.buda(time.time())
        for skorlayici in skorlayicilar.values():
            skorlayici.buda(time.time())

    sure = time.time() - t0
    print(f"\n{degerlendirme} kamera-anı · {sure:.0f} sn\n")

    # ─── Sonuç tablosu ───
    print("NORMAL OLDUĞU BİLİNEN KAMERALARDA (yani hepsi yanlış pozitif)")
    print(
        f"{'AYAR':<7} {'değerlend.':>10} {'dikkat':>8} {'uyarı':>8} {'alarm':>8} {'skor p50':>9} {'p99':>7}"
    )
    ozet: dict[str, object] = {}
    for ad in ayarlar:
        n_dikkat = sum(sayac[ad][k].get("dikkat", 0) for k in NORMAL_KAMERALAR)
        n_uyari = sum(sayac[ad][k].get("uyari", 0) for k in NORMAL_KAMERALAR)
        n_alarm = sum(sayac[ad][k].get("alarm", 0) for k in NORMAL_KAMERALAR)
        skorlar = sorted(normal_skor[ad])
        p50 = skorlar[len(skorlar) // 2] if skorlar else 0.0
        p99 = skorlar[min(len(skorlar) - 1, int(len(skorlar) * 0.99))] if skorlar else 0.0
        print(
            f"{ad:<7} {len(skorlar):>10} {n_dikkat:>8} {n_uyari:>8} {n_alarm:>8} "
            f"{p50:>9.3f} {p99:>7.3f}"
        )
        ozet[ad] = {
            "degerlendirme": len(skorlar),
            "dikkat": n_dikkat,
            "uyari": n_uyari,
            "alarm": n_alarm,
            "skor_p50": round(p50, 4),
            "skor_p99": round(p99, 4),
            "uyari_ustu_oran": round((n_uyari + n_alarm) / max(len(skorlar), 1), 5),
        }

    # ─── Kavga İÇEREN kameralar — sağırlaşma kontrolü ───
    # ⚠ Bu bölüm duyarlılık ölçümü DEĞİL (modül başlığı). Yalnızca
    # "ayar her yerde susturmuş mu" sorusuna bakar: cam-17 (RWF, %10
    # kavga) hâlâ cam-18'den (kontrol) daha fazla uyarı üretiyor mu?
    print("\nSAĞIRLAŞMA KONTROLÜ — cam-17 (kavga içeriyor) vs cam-18 (kontrol)")
    print(f"{'AYAR':<7} {'cam-17 uyarı+':>13} {'cam-18 uyarı+':>13} {'ayrım':>8}")
    for ad in ayarlar:
        a = sayac[ad]["cam-17"].get("uyari", 0) + sayac[ad]["cam-17"].get("alarm", 0)
        b = sayac[ad]["cam-18"].get("uyari", 0) + sayac[ad]["cam-18"].get("alarm", 0)
        ayrim = a / max(b, 1)
        print(f"{ad:<7} {a:>13} {b:>13} {ayrim:>8.2f}×")
        ozet[ad]["cam17_uyari_ustu"] = a  # type: ignore[index]
        ozet[ad]["cam18_uyari_ustu"] = b  # type: ignore[index]

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "sure_s": round(sure, 1),
        "kamera_ani": degerlendirme,
        "normal_kameralar": list(NORMAL_KAMERALAR),
        "ayarlar": {ad: {k: getattr(e, k) for k in e.__slots__} for ad, e in ayarlar.items()},  # type: ignore[attr-defined]
        "sonuc": ozet,
        "kamera_bazli": {ad: {k: dict(v) for k, v in sayac[ad].items()} for ad in ayarlar},
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"aggression_calib_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
