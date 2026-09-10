"""Alarmları DÖNGÜDEKİ KONUMA göre tekilleştirip kesinliği yeniden hesaplar.

⚠⚠ NEDEN GEREKLİ — HAM ALARM SAYISI SİSTEMİ ÖLÇMÜYOR (P-77 / P-79)
-------------------------------------------------------------------
Kaynak videolar sonsuz döngüde yayınlanıyor. cam-16'nın videosu **5
saniye**: içindeki TEK düşme olayı saatte ~720 kez yeniden alarm
üretiyor. Yani ham alarm sayısı sistemin davranışını değil, **test
videolarının uzunluk dağılımını** ölçüyor.

Tekilleştirme ölçütü: `(kamera, tür, döngüdeki konum)`. Konum
`video_pts % video_süresi` ile bulunuyor — `video_pts` yayın başından
beri BİRİKİMLİ olduğu için doğrudan dosya içi konum değildir (P-77).
Birbirine `TOLERANS` saniyeden yakın olanlar aynı olay sayılıyor.

⚠ GÜVEN ARALIĞI WILSON YÖNTEMİYLE
n küçük (≈19) ve oran uçta (≈0.9) olduğunda normal yaklaşım **1'i
aşan** bir üst sınır verir — yani imkânsız bir değer raporlanır.
Wilson skor aralığı bu aralıkta sınırların içinde kalır.

Kullanım:
    uv run python scripts/alarm_tekillestir.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VARSAYILAN_CSV = PROJECT_ROOT / "data" / "annotations" / "alarm_etiketleri_20260910.csv"
SURELER = PROJECT_ROOT / "benchmarks" / "kamera_video_sureleri.json"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# Klip penceresi ±3 sn; bu kadar yakın iki alarm aynı olayın
# tekrarıdır. Daha geniş bir tolerans farklı olayları birleştirir,
# daha dar olanı aynı olayı ikiye böler.
TOLERANS_S = 6.0


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson skor aralığı — küçük n ve uç oranlarda doğru davranır."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yari = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / payda
    return (max(0.0, merkez - yari), min(1.0, merkez + yari))


def _sure_al(sureler: dict[str, Any], kamera: str) -> float | None:
    v = sureler.get(kamera)
    if v is None:
        return None
    if isinstance(v, dict):
        for anahtar in ("sure_sn", "sure_s", "sure", "duration"):
            if anahtar in v:
                return float(v[anahtar])
        return None
    return float(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=VARSAYILAN_CSV)
    args = ap.parse_args()

    if not args.csv.is_file():
        print(f"❌ Etiket dosyası yok: {args.csv}")
        return 1

    sureler = json.loads(SURELER.read_text(encoding="utf-8"))
    with args.csv.open(encoding="utf-8") as f:
        satirlar = [s for s in csv.DictReader(f) if (s.get("dogru") or "").strip()]

    if not satirlar:
        print("❌ Etiketlenmiş satır yok.")
        return 1

    # ⚠ Süresi bilinmeyen kamera tekilleştirilemez ve bunu SESSİZCE
    # geçmek, ham sayıyı "bağımsız" diye raporlamak olurdu.
    sure_yok: set[str] = set()
    bagimsiz: list[tuple[str, str, float, int]] = []
    for s in sorted(satirlar, key=lambda x: (x["kamera"], x["tur"], float(x["video_pts"]))):
        kam, tur = s["kamera"], s["tur"]
        sure = _sure_al(sureler, kam)
        if not sure:
            sure_yok.add(kam)
            continue
        konum = float(s["video_pts"]) % sure
        yeni = True
        for k2, t2, p2, _d in bagimsiz:
            if k2 != kam or t2 != tur:
                continue
            fark = abs(konum - p2)
            # Döngüsel yakınlık: 0. saniye ile (süre−1). saniye komşudur.
            fark = min(fark, sure - fark)
            if fark <= TOLERANS_S:
                yeni = False
                break
        if yeni:
            bagimsiz.append((kam, tur, konum, int(s["dogru"])))

    ham_n, ham_d = len(satirlar), sum(1 for s in satirlar if s["dogru"] == "1")
    bag_n, bag_d = len(bagimsiz), sum(1 for *_x, d in bagimsiz if d == 1)
    ham_ga, bag_ga = _wilson(ham_d, ham_n), _wilson(bag_d, bag_n)

    print("═" * 64)
    print("ALARM KESİNLİĞİ — ham ve TEKİLLEŞTİRİLMİŞ")
    print("═" * 64)
    print(f"ham etiketli alarm : {ham_n:3d} · doğru {ham_d:3d} → {ham_d / ham_n:.3f}"
          f"  [{ham_ga[0]:.3f}, {ham_ga[1]:.3f}]")
    print(f"BAĞIMSIZ olay      : {bag_n:3d} · doğru {bag_d:3d} → {bag_d / bag_n:.3f}"
          f"  [{bag_ga[0]:.3f}, {bag_ga[1]:.3f}]   ⬅ RAPORLANACAK")
    print("\ntür bazında (bağımsız):")
    turler: dict[str, list[int]] = {}
    for _k, t, _p, d in bagimsiz:
        turler.setdefault(t, []).append(d)
    tur_ozet = {}
    for t, ds in sorted(turler.items()):
        ga = _wilson(sum(ds), len(ds))
        tur_ozet[t] = {"n": len(ds), "dogru": sum(ds), "ga95": [round(ga[0], 4), round(ga[1], 4)]}
        print(f"  {t:10s} {sum(ds):2d}/{len(ds):<2d} = {sum(ds) / len(ds):.2f}"
              f"  [{ga[0]:.2f}, {ga[1]:.2f}]")
    if sure_yok:
        print(f"\n⚠ süresi bilinmeyen, ANALİZ DIŞI kamera: {sorted(sure_yok)}")

    kayit = {
        "olculdu": "2026-09-10",
        "kaynak": str(args.csv.relative_to(PROJECT_ROOT)),
        "tolerans_s": TOLERANS_S,
        "ham_alarm": ham_n,
        "ham_dogru": ham_d,
        "ham_kesinlik": round(ham_d / ham_n, 4),
        "ham_ga95": [round(ham_ga[0], 4), round(ham_ga[1], 4)],
        "bagimsiz_olay": bag_n,
        "bagimsiz_dogru": bag_d,
        "bagimsiz_kesinlik": round(bag_d / bag_n, 4),
        "bagimsiz_ga95": [round(bag_ga[0], 4), round(bag_ga[1], 4)],
        "tur_bazinda": tur_ozet,
        "yontem_ga": "Wilson skor aralığı",
        "not": (
            "KESİNLİK ölçüsüdür, duyarlılık DEĞİL: yalnızca sistemin ürettiği "
            "alarmlara bakıldı, kaçırılan olaylar ölçülmedi. Kaynak videolar "
            "döngüde olduğu için ham sayı şişkindir; raporlanacak değer "
            "bağımsız olay sayısı üzerinden hesaplanandır."
        ),
    }
    yol = BENCHMARKS / "alarm_kesinlik_20260910.json"
    yol.write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {yol.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
