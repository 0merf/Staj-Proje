"""Aynı etiketleyicinin iki turunu karşılaştırır — tekrar testi.

Neden gerekiyor
---------------
K8 ölçümünün yer gerçeği elle üretildi ve tek kişi tarafından
etiketlendi. Bu, raporda bilinen bir sınır olarak yazılı. Ama sınırı
yazmak, büyüklüğünü söylemiyor: "tek etiketleyici" cümlesi, etiketin
±0,2 saniye mi yoksa ±3 saniye mi oynadığını bildirmiyor.

Bağımsız ikinci bir etiketleyici bulunamadığı için ölçülebilecek olan
şu: aynı kişi aynı klipleri ikinci kez etiketlediğinde ne kadar
sapıyor. Bu, değerlendiriciler arası uyumun yerini tutmaz —
**içi** uyumu ölçer ve gerçek belirsizliğin ALT sınırını verir.
İki farklı kişi arasındaki fark, bir kişinin kendisiyle olan
farkından küçük olamaz.

Kullanım
--------
    uv run python scripts/etiketle_k8.py \
        --tekrar data/annotations/rwf_k8.json \
        --cikti  data/annotations/rwf_k8_tekrar.json --adet 10

    uv run python scripts/etiket_tekrar_karsilastir.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

KOK = Path(__file__).resolve().parents[2]
BIRINCI = KOK / "data" / "annotations" / "rwf_k8.json"
IKINCI = KOK / "data" / "annotations" / "rwf_k8_tekrar.json"
CIKTI_DIZIN = KOK / "benchmarks"


def _etiketler(yol: Path) -> dict[str, float]:
    if not yol.is_file():
        print(f"dosya yok: {yol}", file=sys.stderr)
        return {}
    veri: dict[str, Any] = json.loads(yol.read_text(encoding="utf-8"))
    return {
        ad: float(k["baslangic_s"])
        for ad, k in veri.get("etiketler", {}).items()
        if k.get("baslangic_s") is not None
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--birinci", default=str(BIRINCI))
    ap.add_argument("--ikinci", default=str(IKINCI))
    args = ap.parse_args()

    a = _etiketler(Path(args.birinci))
    b = _etiketler(Path(args.ikinci))
    ortak = sorted(set(a) & set(b))
    if not ortak:
        print("iki turda da etiketlenmiş ortak klip yok")
        return 1

    farklar = [b[ad] - a[ad] for ad in ortak]
    mutlak = [abs(f) for f in farklar]

    print(f"\nortak klip: {len(ortak)}")
    print(f"{'klip':<34} {'1. tur':>8} {'2. tur':>8} {'fark':>8}")
    for ad in ortak:
        print(f"{ad:<34} {a[ad]:8.2f} {b[ad]:8.2f} {b[ad] - a[ad]:+8.2f}")

    # Yanlılık (ortalama işaretli fark) ile tutarsızlık (ortalama mutlak
    # fark) ayrı raporlanıyor: ikinci turda sistematik olarak erken ya da
    # geç işaretlemek, rastgele oynamaktan farklı bir sorundur.
    ozet = {
        "ortak_klip": len(ortak),
        "ortalama_isaretli_fark_s": round(statistics.fmean(farklar), 3),
        "ortalama_mutlak_fark_s": round(statistics.fmean(mutlak), 3),
        "medyan_mutlak_fark_s": round(statistics.median(mutlak), 3),
        "en_buyuk_mutlak_fark_s": round(max(mutlak), 3),
        "bir_saniyenin_altinda": sum(1 for m in mutlak if m < 1.0),
    }
    if len(ortak) > 1:
        ozet["mutlak_fark_std_s"] = round(statistics.stdev(mutlak), 3)

    print("\nözet")
    for k, v in ozet.items():
        print(f"  {k:<28} {v}")

    yol = CIKTI_DIZIN / f"etiket_tekrar_{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(
        json.dumps(
            {
                "olculdu": datetime.now(UTC).isoformat(),
                "yontem": (
                    "aynı etiketleyici, aynı klipler, ikinci tur; birinci turun "
                    "etiketleri görülmeden"
                ),
                "bilinen_sinir": (
                    "değerlendirici içi uyum — değerlendiriciler arası uyumun "
                    "yerini tutmaz, gerçek belirsizliğin alt sınırını verir"
                ),
                "birinci_tur": str(Path(args.birinci).name),
                "ikinci_tur": str(Path(args.ikinci).name),
                "klip_basina": {
                    ad: {"birinci_s": a[ad], "ikinci_s": b[ad],
                         "fark_s": round(b[ad] - a[ad], 3)}
                    for ad in ortak
                },
                **ozet,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nyazıldı: {yol.relative_to(KOK)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
