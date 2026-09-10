"""Çıkarım döngüsünün aşama kırılımı — tek birim, tek pencere, kapanış kontrollü.

⭐ NEDEN BU BETİK VAR
--------------------
P-66'daki kırılım tablosu **elle** üretilmişti ve tekrar üretilemiyordu.
10.09'da K3'ün gerilediği görülünce (p50 172→378 ms) "hangi aşama
yavaşladı" sorusu soruldu ve tabloyu üreten bir araç olmadığı fark
edildi.

> ⭐⭐ Bir ölçümün tekrar edilemiyor olması, o ölçümü bir kanıt değil
> bir ANI yapar. P-60 ve P-62'nin dersi buydu: düzeltme (ve ölçüm)
> taşınmazsa yapılmamıştır.

⚠ BU BETİĞİN KAÇINDIĞI ÜÇ HATA — üçü de bu projede yapıldı:

  1. **Kümülatif histogramı doğrudan okumak** (P-60). Prometheus
     histogramı süreç başından beri sayar; pencere farkı alınmazsa
     ölçülen şey worker'ın TÜM ÖMRÜdür. → `_fark()` kullanılıyor.

  2. **Aynı metrikte iki farklı birim toplamak** (P-66). Aşamaların
     hepsi `observe(sure / len(batch))` ile KARE BAŞINA yazıyor;
     birini parti başına sanmak tabloyu tümüyle bozuyordu.
     → Kod okunarak doğrulandı, betik tek birim varsayıyor ve
       kapanış kontrolüyle bunu SINIYOR.

  3. **Parçaları ölçüp toplamı ölçmemek.** Kalanı ölçmemek "kalan
     sıfırdır" demektir. → `parti_TOPLAM` bağımsız ölçülüyor ve
     aşamaların toplamıyla karşılaştırılıyor (kapanış kontrolü).

⚠ `bekleme_IS_DEGIL` tabloya KATILMAZ: o süre CPU harcamıyor, kare
gelmesini bekliyor. Ayrı raporlanıyor, çünkü büyümesi darboğazın
çıkarımda DEĞİL yukarı akışta olduğunu söyler.

Kullanım:
    uv run python scripts/asama_kirilimi.py --pencere 120
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
PORT = 9110
METRIK = "sentinel_inference_duration_seconds"

# Toplama KATILMAYAN aşama: CPU değil, bekleme.
BEKLEME = "bekleme_IS_DEGIL"
TOPLAM = "parti_TOPLAM"


def _kazi(port: int) -> str:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/metrics", timeout=5.0,
    ) as yanit:
        return yanit.read().decode("utf-8", errors="replace")


def _oku(metin: str) -> dict[str, tuple[float, float]]:
    """stage → (sum_saniye, count). Kümülatif değerler."""
    sonuc: dict[str, list[float]] = {}
    for satir in metin.splitlines():
        if satir.startswith("#") or not satir.startswith(METRIK):
            continue
        try:
            sol, deger = satir.rsplit(" ", 1)
            v = float(deger)
        except ValueError:
            continue
        if "{" not in sol:
            continue
        ad, kalan = sol.split("{", 1)
        if not (ad.endswith("_sum") or ad.endswith("_count")):
            continue
        etiket = ""
        for parca in kalan.rstrip("}").split(","):
            if parca.strip().startswith("stage="):
                etiket = parca.split("=", 1)[1].strip().strip('"')
        if not etiket:
            continue
        kayit = sonuc.setdefault(etiket, [0.0, 0.0])
        kayit[0 if ad.endswith("_sum") else 1] = v
    return {k: (v[0], v[1]) for k, v in sonuc.items()}


def _fark(
    son: dict[str, tuple[float, float]], ilk: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Pencere farkı — kümülatif sayaçtan pencereye inmenin TEK doğru yolu."""
    cikti = {}
    for stage, (s_sum, s_cnt) in son.items():
        i_sum, i_cnt = ilk.get(stage, (0.0, 0.0))
        cikti[stage] = (s_sum - i_sum, s_cnt - i_cnt)
    return cikti


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pencere", type=int, default=120, help="ölçüm penceresi (sn)")
    args = ap.parse_args()

    try:
        ilk = _oku(_kazi(PORT))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"❌ Çıkarım worker'ının metrik ucu okunamadı (:{PORT}): {exc}")
        print("   Boru hattı ayakta mı? (start_all.ps1)")
        return 1

    print(f"⏳ {args.pencere} sn pencere ölçülüyor — sisteme DOKUNMA (P-36)…")
    time.sleep(args.pencere)
    son = _oku(_kazi(PORT))

    d = _fark(son, ilk)
    parti_sayisi = d.get(TOPLAM, (0.0, 0.0))[1]
    if parti_sayisi < 10:
        print(f"❌ Pencerede yalnızca {parti_sayisi:.0f} parti işlendi — çok az.")
        return 1

    # Aşamalar: bekleme ve toplam hariç.
    asamalar = {
        k: v for k, v in d.items() if k not in (BEKLEME, TOPLAM) and v[1] > 0
    }
    # Her gözlem ZATEN kare başına bir değer (observe(sure/len(batch))).
    ms = {k: (s / c) * 1000.0 for k, (s, c) in asamalar.items()}
    toplam_olculen = sum(ms.values())

    t_sum, t_cnt = d[TOPLAM]
    parti_toplam_ms = (t_sum / t_cnt) * 1000.0
    acik = parti_toplam_ms - toplam_olculen

    b_sum, b_cnt = d.get(BEKLEME, (0.0, 0.0))
    bekleme_ms = (b_sum / b_cnt) * 1000.0 if b_cnt else 0.0

    print(f"\n{'═' * 62}")
    print(f"ÇIKARIM AŞAMA KIRILIMI — pencere {args.pencere} sn · {parti_sayisi:.0f} parti")
    print(f"{'═' * 62}")
    print(f"{'aşama':<18}{'ms/kare':>10}{'payı':>9}")
    print("-" * 62)
    for ad, deger in sorted(ms.items(), key=lambda x: -x[1]):
        pay = deger / parti_toplam_ms * 100 if parti_toplam_ms else 0.0
        print(f"{ad:<18}{deger:>10.2f}{pay:>8.0f}%")
    print("-" * 62)
    print(f"{'ölçülen toplam':<18}{toplam_olculen:>10.2f}")
    print(f"{'PARTİ TOPLAMI':<18}{parti_toplam_ms:>10.2f}   ⬅ bağımsız ölçüm")
    kapandi = abs(acik) < max(0.5, parti_toplam_ms * 0.05)
    isaret = "✅ hesap KAPANIYOR" if kapandi else "⚠ AÇIK VAR — tablo eksik"
    print(f"{'açıklanamayan':<18}{acik:>10.2f}   {isaret}")
    print(f"\n{BEKLEME:<18}{bekleme_ms:>10.2f}   ⬅ CPU DEĞİL; toplama katılmaz")
    print("   (büyükse darboğaz çıkarımda değil, YUKARI AKIŞTA)")

    kayit = {
        "olculdu": datetime.now(UTC).isoformat(),
        "pencere_s": args.pencere,
        "parti": parti_sayisi,
        "asamalar_ms_kare": {k: round(v, 3) for k, v in ms.items()},
        "olculen_toplam_ms": round(toplam_olculen, 3),
        "parti_toplam_ms": round(parti_toplam_ms, 3),
        "aciklanamayan_ms": round(acik, 3),
        "kapanis_kontrolu": kapandi,
        "bekleme_ms": round(bekleme_ms, 3),
        "not": (
            "Her gözlem kare başına bir değerdir (observe(sure/len(batch))). "
            "bekleme_IS_DEGIL toplama KATILMAZ — CPU değil, bekleme."
        ),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    yol = BENCHMARKS / f"asama_kirilimi_{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    yol.write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {yol.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
