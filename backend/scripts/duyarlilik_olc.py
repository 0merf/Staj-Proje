"""Kaçırılan olay oranı: sistemin ürettiği alarmlar ile yer gerçeğinin karşılaştırılması.

Neden bu betik
--------------
Alarm doğruluğu şimdiye kadar yalnızca **kesinlik** olarak ölçülebiliyordu:
üretilen alarmların ne kadarı haklı. Bu ölçüm, ters yöndeki soruyu
yanıtlamıyor — sistem kaç olayı hiç bildirmedi? Duyarlılığı ölçmek için
olayların nerede olduğunun önceden bilinmesi gerekiyor.

cam-15 bunu mümkün kılan tek kamera: kaynağı UBI-Fights ve şiddet
aralıkları veri setiyle birlikte kare düzeyinde geliyor
(`data/annotations/cam-15.truth.json`, elle üretilmedi).

Yöntem
------
Kaynak video sonsuz döngüde yayınlandığı için her döngü aynı olayları
yeniden üretiyor. Bir alarmın kaynak videodaki konumu `video_pts`
alanında taşınıyor (P-68); döngü içindeki konum bu değerin video
süresine bölümünden kalan.

  · Fırsat  : ölçüm penceresinde tamamlanan her döngü × olay sayısı
  · Yakalama: bir olay penceresinde en az bir alarm üretilmesi
  · Duyarlılık = yakalanan fırsat / toplam fırsat

Tolerans neden tek bir sayı değil
---------------------------------
Tolerans, olay penceresinin sonuna eklenen süredir. Sistemin tepkisi
tasarımı gereği gecikmelidir: özellikler üç saniyelik bir pencerede
toplanıyor, karar histerezisle veriliyor ve aynı türden alarmlar
soğuma süresiyle seyreltiliyor. Dolayısıyla olayın son karesinde
başlayan bir tepki, dar bir pencerenin dışına düşer.

Tek bir tolerans seçmek, sonucu o seçime bağlar. Ölçümü gördükten
sonra tolerans seçmek ise bu projede daha önce bir kez yapılan hatanın
aynısı olur: ölçütü, gördüğünü haklı çıkaracak biçimde tanımlamak.
Bu yüzden duyarlılık, tolerans taraması olarak raporlanıyor — okuyucu
tepki gecikmesinin sonucu nasıl değiştirdiğini görebiliyor.

Kullanım
--------
    uv run python scripts/duyarlilik_olc.py --saat 3
    uv run python scripts/duyarlilik_olc.py --saat 3 --turler aggression risk
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parents[2]
TRUTH = KOK / "data" / "annotations" / "cam-15.truth.json"
CIKTI_DIZIN = KOK / "benchmarks"


async def _olaylar(kamera: str, saat: float, bitis: datetime | None) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from sentinel.db.engine import motor

    # Geçmiş bir koşuyu yeniden ölçebilmek için pencerenin sonu dışarıdan
    # verilebiliyor; verilmezse şimdiki zaman kullanılıyor.
    sorgu = text(
        """
        SELECT ts, tur, skor, kanit
        FROM olaylar
        WHERE camera = :kam
          AND ts <= COALESCE(CAST(:bitis AS timestamptz), now())
          AND ts > COALESCE(CAST(:bitis AS timestamptz), now())
                   - make_interval(secs => :sn)
        ORDER BY ts
        """
    )
    async with motor().connect() as baglanti:
        sonuc = await baglanti.execute(
            sorgu, {"kam": kamera, "sn": saat * 3600.0, "bitis": bitis}
        )
        return [
            {"ts": r.ts, "tur": r.tur, "skor": float(r.skor), "kanit": r.kanit}
            for r in sonuc
        ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kamera", default="cam-15")
    ap.add_argument("--saat", type=float, default=3.0, help="geriye dönük pencere")
    ap.add_argument(
        "--tolerans",
        type=float,
        nargs="*",
        default=[0.0, 5.0, 10.0, 20.0, 30.0],
        help="olay sonuna eklenen saniye (birden çok değer: tarama)",
    )
    ap.add_argument(
        "--turler",
        nargs="*",
        default=None,
        help="yalnızca bu alarm türleri sayılsın (varsayılan: hepsi)",
    )
    ap.add_argument(
        "--bitis",
        default="",
        help="pencerenin sonu (ISO zaman damgası); geçmiş bir koşuyu ölçmek için",
    )
    ap.add_argument("--etiket", default="")
    args = ap.parse_args()

    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    sure = float(truth["sure_s"])
    olaylar_gt = [(float(s["start_s"]), float(s["end_s"])) for s in truth["segments"]]

    bitis = datetime.fromisoformat(args.bitis) if args.bitis else None
    kayitlar = asyncio.run(_olaylar(args.kamera, args.saat, bitis))
    if not kayitlar:
        print("bu pencerede kayıt yok")
        return 1

    # video_pts taşımayan alarmlar eşleştirilemez; sayıları ayrıca bildiriliyor
    ptsli = [k for k in kayitlar if k["kanit"] and k["kanit"].get("video_pts") is not None]
    ptssiz = len(kayitlar) - len(ptsli)
    if args.turler:
        ptsli = [k for k in ptsli if k["tur"] in args.turler]

    ilk, son = kayitlar[0]["ts"], kayitlar[-1]["ts"]
    pencere_s = (son - ilk).total_seconds()

    # Yayıncı yeniden başladığında pts sıfırlanıyor. Bu yüzden pts tek başına
    # döngüyü adreslemiyor: iki ayrı oturumun aynı numaralı döngüsü aynı anahtara
    # düşüyor ve farklı yakalamalar tek yakalama sayılıyor. Anahtar, pts'nin
    # küçüldüğü yerde artan bir oturum numarasıyla birlikte kuruluyor.
    oturum: list[int] = []
    o, onceki = 0, None
    for k in ptsli:
        pts = float(k["kanit"]["video_pts"])
        if onceki is not None and pts < onceki:
            o += 1
        oturum.append(o)
        onceki = pts

    # Akış gerçek zamanlı yayınlandığı için döngü sayısının fiziksel karşılığı
    # duvar saatiyle geçen süredir. pts açıklığından türetilen değer, sıfırlama
    # varsa bunun altında kalıyor; ikisi birden bildiriliyor.
    ptsler = [float(k["kanit"]["video_pts"]) for k in ptsli]
    dongu_sayisi = int(pencere_s // sure)
    dongu_pts_acikligi = int((max(ptsler) - min(ptsler)) // sure) if ptsler else 0
    yayinci_yeniden_baslama = o
    firsat = dongu_sayisi * len(olaylar_gt)

    def tara(tolerans: float) -> dict[str, Any]:
        """Bir tolerans değeri için yakalama sayısı ve olay kırılımı."""
        dongu_olay: set[tuple[int, int, int]] = set()
        pencere_disi = 0
        for k, oturum_no in zip(ptsli, oturum, strict=True):
            pts = float(k["kanit"]["video_pts"])
            konum = pts % sure
            eslesen = next(
                (i for i, (bas, bit) in enumerate(olaylar_gt) if bas <= konum <= bit + tolerans),
                None,
            )
            if eslesen is None:
                pencere_disi += 1
            else:
                dongu_olay.add((oturum_no, int(pts // sure), eslesen))
        olay_basina = [
            sum(1 for _, _, i in dongu_olay if i == idx) for idx in range(len(olaylar_gt))
        ]
        return {
            "tolerans_s": tolerans,
            "yakalanan": len(dongu_olay),
            "duyarlilik": round(len(dongu_olay) / firsat, 4) if firsat else 0.0,
            "olay_penceresi_disi_alarm": pencere_disi,
            "olay_basina_yakalama": olay_basina,
        }

    tarama = [tara(t) for t in args.tolerans]

    print(f"\nkamera {args.kamera} · pencere {pencere_s / 60:.1f} dk · alarm {len(kayitlar)}")
    print(f"video süresi {sure:.1f} sn · yer gerçeği olayı {len(olaylar_gt)} · tamamlanan döngü {dongu_sayisi}")
    print(f"her döngüde {len(olaylar_gt)} olay → toplam fırsat {firsat}")
    print(
        f"yayıncı yeniden başlaması {yayinci_yeniden_baslama} · "
        f"pts açıklığından döngü {dongu_pts_acikligi}"
    )
    if ptssiz:
        print(f"video konumu taşımayan alarm: {ptssiz} (eşleştirilemedi)")
    if args.turler:
        print(f"sayılan türler: {', '.join(args.turler)}")

    print("\nyer gerçeği olayları:")
    for i, (bas, bit) in enumerate(olaylar_gt, 1):
        print(f"  olay {i}: {bas:.0f}-{bit:.0f} sn")

    print("\ntolerans   duyarlılık   yakalanan/fırsat   olay başına   pencere dışı alarm")
    for s in tarama:
        olay = " / ".join(f"{n}/{dongu_sayisi}" for n in s["olay_basina_yakalama"])
        print(
            f"  {s['tolerans_s']:5.0f} sn      {s['duyarlilik']:.3f}        "
            f"{s['yakalanan']:3d}/{firsat:<3d}        {olay:<16} {s['olay_penceresi_disi_alarm']:3d}"
        )

    tur_dagilimi: dict[str, int] = {}
    for k in ptsli:
        tur_dagilimi[k["tur"]] = tur_dagilimi.get(k["tur"], 0) + 1
    print("\ntür dağılımı:", tur_dagilimi)

    ad = f"duyarlilik_{datetime.now(UTC):%Y%m%d-%H%M%S}"
    if args.etiket:
        ad += f"-{args.etiket}"
    yol = CIKTI_DIZIN / f"{ad}.json"
    yol.write_text(
        json.dumps(
            {
                "olculdu": datetime.now(UTC).isoformat(),
                "kamera": args.kamera,
                "yer_gercegi": str(TRUTH.relative_to(KOK)),
                "yer_gercegi_turu": truth.get("etiket_turu"),
                "video_sure_s": sure,
                "olay_sayisi_dongu_basina": len(olaylar_gt),
                "olay_araliklari_s": olaylar_gt,
                "sayilan_turler": args.turler or "hepsi",
                "pencere_dk": round(pencere_s / 60, 1),
                "pencere_ilk_alarm": ilk.isoformat(),
                "pencere_son_alarm": son.isoformat(),
                "alarm_toplam": len(kayitlar),
                "alarm_pts_siz": ptssiz,
                "dongu_sayisi": dongu_sayisi,
                "dongu_sayisi_kaynagi": "duvar saati penceresi / video süresi",
                "dongu_pts_acikligindan": dongu_pts_acikligi,
                "yayinci_yeniden_baslama": yayinci_yeniden_baslama,
                "firsat": firsat,
                "tolerans_taramasi": tarama,
                "tur_dagilimi": tur_dagilimi,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nyazıldı: {yol.relative_to(KOK)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
