"""Model maliyeti — canlıdaki gecikme artışının sebebi bu mu? (P-57)

⚠⚠ NEDEN
--------
Model üretime alındıktan sonra canlı ölçüm şunu gösterdi:

    ölçüt              model YOKKEN   model VARKEN     fark
    gecikme p50 (ms)         205            450       +245
    gecikme p95 (ms)         463            739       +276
    analiz FPS/kamera       2.75           1.66      −1.09

⭐ Ve bu, daha önce yazdığım bir sayıyla ÇELİŞİYOR. Kaskad analizinde
şöyle demiştim:

    "LightGBM çıkarımı kare başına 0.0004 ms; toplam 11.10 ms'nin
     %0.004'ü. Modeli kapılamak yanlış aşamayı kapılamaktır."

O sayı **doğruydu ama eksikti**: yalnızca `booster.predict()` çağrısını
ölçüyordu. Üretimde asıl iş `predict` değil:

    1. her karede her kişinin ham özelliklerini toplamak
    2. 5 saniyelik pencereyi budamak
    3. ⭐ pencereyi ÖZETLEMEK — 10 ham alan × (azami/p75/medyan)
       + 10 alan × (aykırılık azami/p75/medyan + sahne medyanı)
       = her çağrıda ~70 sıralama/medyan işlemi
    4. sonra predict

⚠ Ve bu, kamera başına HER KAREDE yapılıyor: 20 kamera × ~2.75 FPS
= saniyede 55 kez.

> ⭐ Bir bileşenin maliyetini ölçerken "hangi çağrı" değil "hangi İŞ"
> sorulmalı. `predict` ucuz; onu beslemek pahalı.

BU BETİK NE YAPIYOR
-------------------
Gerçekçi pencereler kurup üç aşamayı AYRI AYRI ölçüyor:

    besle()        — kare verisini pencereye ekleme
    pencere_ozeti()— özet çıkarma (şüpheli asıl maliyet)
    predict()      — LightGBM çıkarımı

Sonra 20 kamera × canlı FPS'e çevirip bütçe içindeki payını veriyor.

⚠ Ölçüm CPU'da; boru hattı koşarken çalıştırılırsa CPU paylaşılır ve
sayılar şişer. Boru hattı KAPALIYKEN koşturulmalı.

Kullanım:
    uv run python scripts/benchmark_model_maliyeti.py
    uv run python scripts/benchmark_model_maliyeti.py --kisi 8 --tekrar 2000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"

KAMERA_SAYISI = 20
CANLI_FPS = 2.75
# Boru hattının kare başına toplam maliyeti (ölçülmüş).
KARE_BUTCESI_MS = 11.10


def _sahte_kisi(i: int, kisi: int) -> Any:
    """`KisiOzellikleri` yerine geçen asgari nesne."""
    from sentinel.analytics.features.person import KisiOzellikleri

    return KisiOzellikleri(
        track_id=kisi,
        bilek_hizi_p75=0.4 + 0.05 * kisi + 0.01 * i,
        bilek_sarsintisi_p75=0.3 + 0.04 * kisi,
        bilek_hizi_azami=0.9 + 0.1 * kisi,
        hareket_enerjisi=0.5 + 0.03 * kisi,
        govde_hizi=0.2 + 0.02 * kisi,
        kol_yuksekligi_azami=0.3,
        govde_egimi=10.0 + kisi,
        govde_egimi_degisimi=2.0,
        durus_genisligi=0.4,
        en_boy_orani=0.45,
        tamlik=0.9,
        ornek_sayisi=8,
    )


class _SahteSkor:
    def __init__(self, kisi: int) -> None:
        from sentinel.analytics.model import BILESENLER

        self.track_id = kisi
        self.skor = 0.1 + 0.05 * kisi
        self.egim = 0.01
        self.bilesenler = {b: 0.1 * (j + 1) for j, b in enumerate(BILESENLER)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Model maliyeti (P-57)")
    ap.add_argument("--kisi", type=int, default=4, help="kare başına kişi")
    ap.add_argument("--tekrar", type=int, default=1000)
    args = ap.parse_args()

    from sentinel.analytics.model import (
        PENCERE_S,
        SaldirganlikModeli,
        pencere_ozeti,
    )
    from sentinel.config import settings

    kayitlar = sorted((PROJECT_ROOT / "benchmarks").glob("saldirganlik_model_*.json"))
    model = SaldirganlikModeli(
        settings.aggression_model_weights, kayitlar[-1] if kayitlar else None,
    )
    if not model.etkin:
        print("❌ Model yüklenemedi.", file=sys.stderr)
        return 1

    # Gerçekçi bir pencere doldur: 5 sn × 2.75 FPS ≈ 14 kare.
    kare_sayisi = max(2, round(PENCERE_S * CANLI_FPS))
    kamera = "bench"
    for i in range(kare_sayisi):
        ts = i / CANLI_FPS
        kisiler = [_sahte_kisi(i, k) for k in range(args.kisi)]
        skorlar = [_SahteSkor(k) for k in range(args.kisi)]
        model.besle(kamera, kisiler, skorlar, ts)

    print(f"pencere: {kare_sayisi} kare × {args.kisi} kişi "
          f"({PENCERE_S:.0f} sn @ {CANLI_FPS} FPS)")
    print(f"tekrar : {args.tekrar}\n")

    # ─── 1. besle() ───
    # ⚠⚠ İLK SÜRÜM BURADA KENDİ ÖLÇÜMÜNÜ BOZDU (P-57)
    #
    # `besle()` 800 kez çağrılıyordu ve zaman damgaları 1 µs aralıklıydı
    # — yani `_buda()` hiçbir şeyi atmıyordu ve pencere 14 kareden
    # **814 kareye** şişiyordu. Sonraki adım `pencere_ozeti`yi o şişmiş
    # pencerede ölçüyordu ve 24.8 ms veriyordu.
    #
    # ⭐ Yani "modelin maliyeti" diye raporlanan sayı, gerçek üretim
    # koşulunun 58 KATI bir pencerede ölçülmüştü. Ölçüm aracının kendi
    # yan etkisiyle ölçtüğü şeyi bozması — bu projede beşinci kez.
    #
    # Düzeltme: zaman damgası gerçek kare aralığıyla ilerliyor, böylece
    # `_buda()` pencereyi 5 sn'de tutuyor.
    kisiler = [_sahte_kisi(0, k) for k in range(args.kisi)]
    skorlar = [_SahteSkor(k) for k in range(args.kisi)]
    ts = kare_sayisi / CANLI_FPS
    t0 = time.perf_counter()
    for n in range(args.tekrar):
        model.besle(kamera, kisiler, skorlar, ts + (n + 1) / CANLI_FPS)
    besle_ms = (time.perf_counter() - t0) / args.tekrar * 1000

    gercek_kare = len(model._bilesen[kamera])
    if abs(gercek_kare - kare_sayisi) > 2:
        print(f"⚠ Pencere beklenenden farklı: {gercek_kare} kare "
              f"(beklenen ~{kare_sayisi}) — ölçüm şüpheli.")
    print(f"besleme sonrası pencere: {gercek_kare} kare "
          f"(budama çalışıyor mu kontrolü)\n")

    # ─── 2. pencere_ozeti() — şüpheli asıl maliyet ───
    bilesen = [s for _t, s in model._bilesen[kamera]]
    ham = [k for _t, k in model._ham[kamera]]
    t0 = time.perf_counter()
    for _ in range(args.tekrar):
        pencere_ozeti(bilesen, ham)
    ozet_ms = (time.perf_counter() - t0) / args.tekrar * 1000

    # ─── 3. degerlendir() = özet + predict ───
    t0 = time.perf_counter()
    for _ in range(args.tekrar):
        model.degerlendir(kamera)
    degerlendir_ms = (time.perf_counter() - t0) / args.tekrar * 1000
    predict_ms = max(degerlendir_ms - ozet_ms, 0.0)

    print("═══ AŞAMA MALİYETİ (kare başına, ms) ═══")
    print(f"{'aşama':<26} {'ms':>9} {'pay':>8}")
    toplam = besle_ms + degerlendir_ms
    for ad, v in (
        ("besle() — pencereye ekle", besle_ms),
        ("pencere_ozeti() — ÖZET", ozet_ms),
        ("booster.predict()", predict_ms),
    ):
        print(f"{ad:<26} {v:>9.4f} {v / max(toplam, 1e-9):>7.0%}")
    print(f"{'TOPLAM':<26} {toplam:>9.4f}")

    # ─── 20 kameraya çevir ───
    saniyede = KAMERA_SAYISI * CANLI_FPS
    ek_ms_sn = toplam * saniyede
    print(f"\n═══ 20 KAMERA × {CANLI_FPS} FPS = {saniyede:.0f} kare/sn ═══")
    print(f"  modelin ek maliyeti : {ek_ms_sn:.1f} ms/saniye "
          f"(tek çekirdeğin %{ek_ms_sn / 10:.1f}'i)")
    print(f"  kare bütçesine payı : %{toplam / KARE_BUTCESI_MS * 100:.1f} "
          f"({KARE_BUTCESI_MS} ms/kare üzerinden)")

    print("\n═══ ÖNCEKİ İDDİAYLA KARŞILAŞTIRMA ═══")
    print("  Kaskad analizinde yazılmıştı:")
    print("    'LightGBM çıkarımı kare başına 0.0004 ms; %0.004'")
    print(f"  Ölçülen predict()          : {predict_ms:.4f} ms")
    print(f"  Ölçülen TOPLAM model işi   : {toplam:.4f} ms")
    if toplam > 0.05:
        kat = toplam / 0.0004
        print(f"\n  ⭐ Gerçek maliyet, o sayının {kat:.0f} KATI.")
        print("  O sayı yalnızca `predict` çağrısını ölçüyordu; üretimde")
        print("  asıl iş pencereyi ÖZETLEMEK ve o her karede yapılıyor.")
    else:
        print("\n  ⚠ Model maliyeti küçük — gecikme artışının sebebi")
        print("  BAŞKA yerde. Aramaya devam edilmeli.")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"model_maliyeti_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "pencere_kare": kare_sayisi, "kisi": args.kisi, "tekrar": args.tekrar,
        "besle_ms": round(besle_ms, 5),
        "ozet_ms": round(ozet_ms, 5),
        "predict_ms": round(predict_ms, 5),
        "toplam_ms": round(toplam, 5),
        "yirmi_kamera_ms_sn": round(ek_ms_sn, 1),
        "kare_butcesi_payi_yuzde": round(toplam / KARE_BUTCESI_MS * 100, 2),
        "eski_iddia_ms": 0.0004,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
