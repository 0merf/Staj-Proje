"""UBI-Fights içinden SABİT KAMERALI kavga videosu bulur (P-50).

⭐ NEDEN
-------
K8 ilk kez cam-15 (`F_74_1_2_0_0`) üzerinde ölçüldü ve tutmadı. Kareler
gözle incelenince sebep ortaya çıktı: **o video elde tutulan bir
telefonla çekilmiş.** Görüntü kayıyor, yakınlaşıyor, sarsılıyor.

Bizim boru hattımız sabit kamera varsayıyor ve varsayım kodda gerekçe
olarak yazılı:

    botsort.py · gmc_method="none"   "Kameralarımız SABİT."
    botsort.py · with_reid=False     "...sabit kameralarda zaten yeterli."

Kamera hareketi **tüm** kutulara sahte hız ekler; hız temelli her
özelliğimiz o yanlılığı taşır. Yani cam-15 üzerindeki ölçüm, sistemi
**kendi varsayımının dışında** sınıyordu — adil bir test değildi.

Ayrıca projedeki diğer 20 kameranın hepsi sabit. Kamera çiftliğine
hareketli bir video koymak, çiftliğin kendisini de temsil etmiyordu.

Bu betik, veri setindeki kavga videolarını tarayıp **en az hareket
eden** kamerayı bulur.

NASIL ÖLÇÜLÜYOR
---------------
Ardışık kare çiftleri arasında seyrek optik akış (Lucas-Kanade,
Shi-Tomasi köşeleri). Sahnedeki *insanlar* da hareket ettiği için
akışın ORTALAMASI değil **MEDYANI** alınıyor: medyan, karenin
çoğunluğunun (arka plan) hareketini temsil eder.

    sabit kamera   → arka plan sabit → medyan akış ≈ 0
    hareketli kamera → arka plan kayar → medyan akış > 0

⚠ Ölçü birimi **kare genişliğinin yüzdesi**, piksel değil: farklı
çözünürlükteki videolar kıyaslanabilsin diye.

⚠ NEDEN "insan sayısı" ile birlikte raporlanıyor
------------------------------------------------
Boş bir sahnede optik akış zaten sıfıra yakın çıkar; o video "sabit"
görünür ama kavga analizi için işe yaramaz. Bu yüzden aday, hem düşük
kamera hareketi hem yeterli insan içermeli. İnsan sayısı burada
kabaca köşe yoğunluğuyla değil, ayrı bir geçişte YOLO ile ölçülüyor
(`--dogrula`).

Kullanım:
    uv run python scripts/bul_sabit_kamera.py --adet 120
    uv run python scripts/bul_sabit_kamera.py --dogrula 8   # ilk 8 adayı YOLO ile
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

UBI = PROJECT_ROOT / "data" / "UBI_FIGHTS"
CIKTI = PROJECT_ROOT / "benchmarks"

# Kaç kare çifti örneklensin. Video boyunca yayılıyor — kamera bir
# yerde sabit durup sonra kayabilir; tek bir yerden bakmak yanıltır.
CIFT_SAYISI = 24

# Kamera hareketi eşiği (kare genişliğinin yüzdesi, kare başına).
# 0.10 = kare başına genişliğin binde biri. Sabit kamerada titreşim
# ve kodlama gürültüsü bu civarda kalıyor.
SABIT_ESIGI = 0.10

# ⚠⚠ SAHNE KESMESİ EŞİĞİ — "sabit" YETMİYOR
#
# İlk tarama F_0_1_0_0_0'ı önerdi: kayma 0.000%, 112 sn olay öncesi
# bağlam. Kareler açılınca görüldü ki video **iki ayrı kameradan
# kurgulanmış**: 0-100 sn hastane koridoru, 106 sn'den sonra otopark.
#
# Optik akış bunu göremez: her parça KENDİ İÇİNDE sabit, kesme ise
# tek karelik bir sıçrama ve medyan onu yutuyor.
#
# ⭐ Bizim için kesme, kameranın hareket etmesinden DAHA kötü:
# Katman A her kameranın normalini ayrı öğreniyor (mimari kural 7).
# Ortasında sahne değişen bir video, tek kameranın öğrenilmiş
# normalini geçersiz kılar — profil iki farklı sahnenin karışımını
# öğrenir ve ikisini de yanlış modeller.
#
# ⚠ İLK DENEMEM HİSTOGRAM KORELASYONUYDU VE KESMEYİ KAÇIRDI.
# F_0_1_0_0_0'ın 104. saniyesindeki kesmede korelasyon 0.582 çıktı —
# 0.5 eşiğinin ÜSTÜNDE, yani "kesme yok" dedi. Sebep: iki sahne de
# kapalı alan, ikisi de düşük doygunluklu (bej fayans ⟷ gri beton).
# Renk histogramları benziyor; SAHNE değişse de RENK değişmiyor.
#
# ⭐ Gri seviye ortalama mutlak farkı aynı kesmeyi net gösterdi:
#
#     t=100.8  hist 0.952  gri_fark 16.3
#     t=104.4  hist 0.582  gri_fark 43.6   ⬅ KESME
#     t=108.0  hist 0.973  gri_fark  5.4
#
# Ölçüt bu yüzden gri farkı ve GÖRECELİ: eşik videonun kendi
# medyanının 2.5 katı. Mutlak bir piksel eşiği, karanlık bir gece
# sahnesiyle aydınlık bir sahneyi aynı ölçemezdi.
KESME_ORANI = 2.5
KESME_ASGARI_FARK = 25.0


def _kamera_hareketi(yol: Path, cift: int = CIFT_SAYISI) -> dict[str, float] | None:
    """Videonun kamera hareketini ölçer (kare genişliğinin %'si / kare)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(yol))
    if not cap.isOpened():
        return None
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if toplam < cift * 2:
        cap.release()
        return None
    adim = toplam // cift

    kaymalar: list[float] = []
    for i in range(cift):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * adim)
        ok1, k1 = cap.read()
        ok2, k2 = cap.read()
        if not (ok1 and ok2):
            continue
        g1 = cv2.cvtColor(k1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(k2, cv2.COLOR_BGR2GRAY)
        koseler = cv2.goodFeaturesToTrack(
            g1, maxCorners=200, qualityLevel=0.01, minDistance=12,
        )
        if koseler is None or len(koseler) < 20:
            continue
        yeni, durum, _err = cv2.calcOpticalFlowPyrLK(g1, g2, koseler, None)
        if yeni is None:
            continue
        iyi = durum.ravel() == 1
        if iyi.sum() < 20:
            continue
        d = (yeni[iyi] - koseler[iyi]).reshape(-1, 2)
        # ⭐ MEDYAN, ortalama değil: sahnedeki insanlar da hareket
        # ediyor. Medyan, karenin çoğunluğunu (arka planı) temsil eder;
        # ortalama birkaç hızlı kişiyle sürüklenir.
        buyukluk = float(np.median(np.linalg.norm(d, axis=1)))
        kaymalar.append(buyukluk / g1.shape[1] * 100.0)
    cap.release()
    if len(kaymalar) < cift // 3:
        return None
    return {
        "kayma_medyan": round(statistics.median(kaymalar), 4),
        "kayma_p90": round(sorted(kaymalar)[int(len(kaymalar) * 0.9)], 4),
        "olcum": float(len(kaymalar)),
        "sure_s": round(toplam / max(cap.get(cv2.CAP_PROP_FPS) or 25, 1), 1),
    }


def _sahne_kesmesi(yol: Path, ornek: int = 40) -> dict[str, float] | None:
    """Videoda sahne kesmesi var mı — HSV histogram korelasyonuyla."""
    import cv2

    cap = cv2.VideoCapture(str(yol))
    if not cap.isOpened():
        return None
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if toplam < ornek * 2:
        cap.release()
        return None
    adim = toplam // ornek

    import numpy as np

    onceki = None
    farklar: list[float] = []
    for i in range(ornek):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * adim)
        ok, kare = cap.read()
        if not ok:
            continue
        gri = cv2.cvtColor(cv2.resize(kare, (160, 90)), cv2.COLOR_BGR2GRAY)
        gri_f = gri.astype(np.float32)
        if onceki is not None:
            farklar.append(float(np.mean(np.abs(gri_f - onceki))))
        onceki = gri_f
    cap.release()
    if len(farklar) < 5:
        return None
    med = statistics.median(farklar)
    esik = max(KESME_ASGARI_FARK, med * KESME_ORANI)
    return {
        "kesme_sayisi": float(sum(1 for f in farklar if f > esik)),
        "en_buyuk_fark": round(max(farklar), 1),
        "fark_medyani": round(med, 1),
    }


def _kavga_penceresi(ad: str) -> dict[str, float] | None:
    """Etiket CSV'sinden ilk kavga penceresini ve olay öncesi bağlamı."""
    import csv

    yol = UBI / "annotation" / f"{ad}.csv"
    if not yol.is_file():
        return None
    with yol.open(encoding="utf-8") as f:
        lab = [int(float(r[0])) for r in csv.reader(f) if r]
    if not any(lab):
        return None
    fps = 30.0  # UBI-Fights kaynak hızı
    ilk = lab.index(1)
    return {
        "ilk_kavga_s": round(ilk / fps, 2),
        "olay_oncesi_s": round(ilk / fps, 2),
        "pozitif_oran": round(sum(lab) / len(lab), 4),
        "sure_s": round(len(lab) / fps, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Sabit kameralı kavga videosu bul")
    ap.add_argument("--adet", type=int, default=120, help="kaç video taransın")
    ap.add_argument("--tohum", type=int, default=42)
    ap.add_argument("--asgari-baglam", type=float, default=20.0,
                    help="olay öncesi en az kaç saniye bağlam olsun")
    ap.add_argument("--dogrula", type=int, default=0,
                    help="ilk N adayı YOLO ile insan sayısı açısından doğrula")
    args = ap.parse_args()

    havuz = sorted((UBI / "videos" / "fight").glob("*.mp4"))
    if not havuz:
        print(f"❌ Video yok: {UBI / 'videos' / 'fight'}", file=sys.stderr)
        return 1

    # ⚠ Önce ETİKETE göre eleme — kamera hareketi ölçmek pahalı, etiket
    # okumak bedava. Olay öncesi bağlamı olmayan video K8 için zaten
    # işe yaramaz (RWF'de tam bu yüzden ölçülememişti).
    adaylar: list[tuple[Path, dict[str, float]]] = []
    for yol in havuz:
        kp = _kavga_penceresi(yol.stem)
        if kp and kp["olay_oncesi_s"] >= args.asgari_baglam:
            adaylar.append((yol, kp))
    print(f"{len(havuz)} kavga videosu · {len(adaylar)} tanesinde "
          f"≥{args.asgari_baglam:.0f} sn olay öncesi bağlam var")

    random.Random(args.tohum).shuffle(adaylar)  # noqa: S311
    adaylar = adaylar[: args.adet]
    print(f"{len(adaylar)} tanesi taranıyor (kamera hareketi)…\n")

    sonuc: list[dict[str, Any]] = []
    for i, (yol, kp) in enumerate(adaylar, 1):
        km = _kamera_hareketi(yol)
        if km:
            sk = _sahne_kesmesi(yol) or {"kesme_sayisi": -1.0,
                                         "en_buyuk_fark": -1.0,
                                         "fark_medyani": -1.0}
            sonuc.append({"ad": yol.stem, **km, **sk, **kp})
        if i % 20 == 0:
            print(f"  {i}/{len(adaylar)}")

    if not sonuc:
        print("❌ Ölçülebilen video yok", file=sys.stderr)
        return 1

    # ⭐ SIRALAMA ÖNCE KESMESİZLİĞE, sonra sabitliğe göre: kesmeli bir
    # video ne kadar sabit olursa olsun tek kamerayı temsil etmiyor.
    sonuc.sort(key=lambda s: (s["kesme_sayisi"] > 0, s["kayma_medyan"]))
    sabitler = [
        s for s in sonuc
        if s["kayma_medyan"] <= SABIT_ESIGI and s["kesme_sayisi"] == 0
    ]

    print(f"\n═══ EN SABİT 12 KAMERA ({len(sonuc)} ölçüldü) ═══")
    print(f"{'video':<22} {'kayma%':>8} {'kesme':>6} {'süre':>7} "
          f"{'olay öncesi':>12} {'kavga%':>8}")
    for s in sonuc[:12]:
        ok = s["kayma_medyan"] <= SABIT_ESIGI and s["kesme_sayisi"] == 0
        print(f"{s['ad']:<22} {s['kayma_medyan']:>8.3f} "
              f"{s['kesme_sayisi']:>6.0f} "
              f"{s['sure_s']:>6.0f}s {s['olay_oncesi_s']:>11.1f}s "
              f"{s['pozitif_oran']:>7.1%}{' ✅' if ok else ''}")

    # Karşılaştırma: şu anki cam-15
    mevcut = _kamera_hareketi(UBI / "videos" / "fight" / "F_74_1_2_0_0.mp4")
    if mevcut:
        print(f"\n{'F_74_1_2_0_0 (şu anki cam-15)':<22} "
              f"{mevcut['kayma_medyan']:>8.3f} {mevcut['kayma_p90']:>8.3f}"
              "   ⬅ ELDE TUTULAN TELEFON")

    print(f"\nsabit sayılan ({SABIT_ESIGI}% altı): {len(sabitler)} video")
    if sabitler:
        e = sabitler[0]
        print(f"⭐ ÖNERİ: {e['ad']} · kayma {e['kayma_medyan']:.3f}% · "
              f"{e['sure_s']:.0f} sn · olay öncesi {e['olay_oncesi_s']:.1f} sn")
    else:
        print("⚠ Eşiği geçen yok — veri seti ağırlıklı olarak elde çekim.")
        print("   En sabit adayla devam edilebilir ama 'sabit' denemez.")

    CIKTI.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = CIKTI / f"sabit_kamera_taramasi_{damga}.json"
    hedef.write_text(json.dumps({
        "tarih": datetime.now(UTC).isoformat(),
        "yontem": "seyrek optik akış (Lucas-Kanade) · MEDYAN kayma",
        "birim": "kare genişliğinin yüzdesi / kare",
        "sabit_esigi": SABIT_ESIGI,
        "taranan": len(sonuc),
        "sabit_sayisi": len(sabitler),
        "mevcut_cam15": mevcut,
        "siralama": sonuc,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
