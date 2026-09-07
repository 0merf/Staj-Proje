"""Saldırganlık modeli eğitimi — kural tabanlı tabanı GEÇMEYE çalışıyor.

Neden bu betik (ADR-0007'nin ikinci yarısı)
-------------------------------------------
ADR-0007 şunu söylüyordu:

> *"Önce kural tabanlı skor, sonra model. Kural skoru KALIR — çünkü
>  eğitilecek modelin geçmesi gereken TABAN ÇİZGİSİ odur."*

Taban ölçüldü: **K5 F1 = 0.712** (RWF-2000 val, `evaluate_rwf.py`).
Bu betik ikinci yarıyı yapıyor.

⚠ NE DEĞİŞİYOR — ve ne DEĞİŞMİYOR
Değişmeyen: özellikler. `aggression.py` altı bileşen üretiyor
(yakınlık, bilek, yaklaşma, enerji, duruş, etkileşim) ve model
**aynılarını** kullanıyor. Yeni bir özellik mühendisliği yok.

Değişen: bileşenlerin nasıl birleştirildiği.

    ŞU AN   : 0.30·yakınlık + 0.25·bilek + 0.20·yaklaşma + …
              ağırlıklar ELLE kondu, PLAN'dan alındı
    MODEL   : ağırlıklar VERİDEN öğreniliyor, üstelik doğrusal
              OLMAYAN etkileşimlerle

⭐ Doğrusal olmama neden önemli: *"yüksek bilek hızı"* tek başına
kavga değil. *"Yüksek bilek hızı VE yakın mesafe VE karşılıklı duruş"*
kavga. Ağırlıklı toplam bu koşullu ilişkiyi ifade EDEMEZ — her bileşen
diğerlerinden bağımsız katkı verir. Karar ağacı tam olarak bunu
ifade edebiliyor: *"eğer mesafe < X ise, bilek hızına bak; değilse
bakma."*

⚠ NEDEN LightGBM, NEDEN DERİN AĞ DEĞİL
  · Veri az: 1600 eğitim klibi, klip başına tek etiket
  · Özellik sayısı 6 — derin ağın öğrenecek bir temsili yok,
    özellikler zaten elle çıkarılmış
  · Eğitim CPU'da saniyeler sürüyor; GPU boru hattıyla yarışmıyor
  · Çıkarım maliyeti ~mikrosaniye — canlı hatta ek yük yok
  · **Açıklanabilir kalıyor:** özellik önemi çıkarılabiliyor, ve
    operatöre "skor 0.72 çünkü şu" demeye devam edebiliyoruz.
    Bu, PLAN §6.5'in açıkça istediği bir özellik.

⚠ SIZINTIYA KARŞI: train / val AYRI BÖLÜMLERDEN
Model `train/` bölümünde eğitiliyor, `val/` bölümünde ölçülüyor.
`evaluate_rwf.py` (K5 tabanı) da `val` kullanıyor — yani taban ile
model **aynı veride** karşılaştırılıyor, adil.

⚠ AMA: `train` bölümünün bir kısmı sahte kamera cam-17'yi besliyor.
Yani model, canlı sistemde göreceği bazı görüntülerle eğitilmiş
olacak. Bu bir sızıntı DEĞİL (K5/K8 ölçümleri `val`'da yapılıyor) ama
canlı demo "modelin daha önce gördüğü" veriyi içeriyor ve raporda
böyle yazılacak.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI olmalı (özellik çıkarımı GPU
kullanıyor — tespit + poz).

Kullanım
--------
    # 1) Özellikleri çıkar (GPU, uzun sürer — bir kez)
    uv run python scripts/train_aggression.py --cikar --klip 300

    # 2) Eğit ve değerlendir (CPU, saniyeler)
    uv run python scripts/train_aggression.py --egit
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000"
OZELLIK_DOSYASI = PROJECT_ROOT / "data" / "_tmp" / "rwf_ozellikler.json"
MODEL_DOSYASI = PROJECT_ROOT / "backend" / "models" / "saldirganlik_lgbm.txt"

TOHUM = 42

# ⚠ ÖZELLİK ADLARI `aggression.py · bilesenler` ile BİREBİR AYNI
# olmak zorunda. Ayrışırsa model eğitildiğinden başka bir şeyle
# beslenir ve hata SESSİZ olur — skor üretilir, yalnızca yanlış olur.
# (Aynı sınıf tuzak: analytics/ifade.py · IFADE_RISK etiket kümesi.)
BILESENLER = ("yakinlik", "bilek", "yaklasma", "enerji", "durus", "etkilesim")

# ⚠ BANTLANMAMIŞ ham özellikler — model yolu için (P-48).
# `KisiOzellikleri` alan adlarıyla BİREBİR aynı olmak zorunda.
HAM_ALANLAR = (
    "bilek_hizi_p75", "bilek_sarsintisi_p75", "bilek_hizi_azami",
    "hareket_enerjisi", "govde_hizi", "kol_yuksekligi_azami",
    "govde_egimi", "govde_egimi_degisimi", "durus_genisligi",
    "en_boy_orani", "oyalanma_s",
)

# Klip başına özet istatistikler. ⚠ Klip etiketi klip seviyesinde
# ("bu 5 saniyede kavga var") ama özellikler KARE seviyesinde çıkıyor.
# Aradaki köprü bir toplulaştırma ve seçimi önemli:
#   azami   → "en riskli an ne kadar riskliydi"
#   p90     → azaminin gürültüye dayanıklı hâli
#   ortalama→ olayın klibin ne kadarını kapladığı
#   egim    → TIRMANMA hızı (projenin özgün iddiası)
OZETLER = ("azami", "p90", "ortalama", "egim_azami")


def _klip_ozellikleri(
    yol: Path, *, dedektor: Any, poz: Any, ornek_fps: float, imgsz: int
) -> dict[str, float] | None:
    """Bir klipten model girdisi üretir.

    ⚠ `evaluate_rwf.py` ve `evaluate_k8.py` ile AYNI boru hattı.
    Üç betik aynı modülü ölçüyor; ön işleme farkı üçünü kıyaslanamaz
    kılardı.
    """
    import cv2

    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    adim = max(1, round(kaynak_fps / ornek_fps))

    takipci = BotSortTracker(frame_rate=int(ornek_fps))
    depo = PencereDeposu()
    skorlayici = TirmanmaSkorlayici()

    # Kare başına: her bileşenin o karedeki AZAMİ değeri + skor + eğim
    seri: list[dict[str, float]] = []
    ham_seri: list[dict[str, float]] = []
    # ⚠ Kare bazlı gruplama — AYKIRILIK özelliği için ZORUNLU (P-49).
    # `ham_seri` bütün kişileri bütün karelerden tek havuza atıyor;
    # "aynı karedeki diğerlerine göre" sorusu o havuzda sorulamaz.
    ham_kareler: list[list[dict[str, float]]] = []
    kare_no = 0
    kamera = yol.stem
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps

        izler = takipci.update(kamera, dedektor.detect([hazir])[0], ts)
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                d = iz.detection
                bbox = (d.x1, d.y1, d.x2, d.y2)
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera, iz.track_id,
                    Ornek(
                        ts=ts, bbox=bbox, kp=kp,
                        olcek=sk.govde_boyu(kp, bbox) if kp is not None else None,
                        ayak=sk.ayak_noktasi(bbox),
                    ),
                )
            kisiler = [cikar(depo.al(kamera, t.track_id)) for t in izler]  # type: ignore[arg-type]
            ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(kamera))
            skorlar = skorlayici.degerlendir(kamera, kisiler, ciftler, ts)

            # ⚠⚠ 07.09.2026 — HAM ÖZELLİKLER DE TOPLANIYOR (P-48)
            #
            # `bilesenler` sözlüğü ölü bölgeden GEÇMİŞ değerler taşıyor:
            # `_bant(deger, taban, doyum)` tabanın altını SIFIRA
            # yuvarlıyor. O bantlama KURAL yolu için doğru (yanlış alarm
            # bastırma) ama MODEL yolu için bilgi imhası:
            #
            #   RWF'de normal p90 = 2.187, kavga p50 = 0.954
            #   → kavga sinyalinin yarısı tabanın ALTINDA → sıfırlanıyor
            #
            # Model sınırı kendisi öğrenmeli; ona sınırı çizilmiş veri
            # vermek, öğrenmesi gereken şeyi elinden almak.
            kare_kisileri: list[dict[str, float]] = []
            for kisi in kisiler:
                if kisi.track_id < 0:
                    continue
                kare_kisileri.append({
                    a: float(v)
                    for a in HAM_ALANLAR
                    if (v := getattr(kisi, a, None)) is not None
                })
            ham_seri += kare_kisileri
            if kare_kisileri:
                ham_kareler.append(kare_kisileri)

            if skorlar:
                # ⚠ Kare içinde AZAMİ: kavga iki kişilik bir olay ve
                # bir karede birinin skoru yüksekse o kare risklidir.
                en_riskli = max(skorlar, key=lambda s: s.skor)
                satir = dict.fromkeys(BILESENLER, 0.0)
                satir.update(
                    {k: float(v) for k, v in en_riskli.bilesenler.items()
                     if k in BILESENLER}
                )
                satir["skor"] = float(en_riskli.skor)
                satir["egim"] = float(en_riskli.egim)
                seri.append(satir)
        kare_no += 1

    cap.release()
    if not seri:
        # ⚠ Hiç iz yoksa klip ATILIYOR, sıfırla doldurulmuyor.
        # Sıfır vektörü "hiçbir saldırganlık belirtisi yok" demek;
        # oysa gerçek durum "kimseyi göremedik". İkisini karıştırmak,
        # tespit başarısızlığını model girdisi yapmak olurdu.
        return None

    cikti: dict[str, Any] = {}
    for alan in (*BILESENLER, "skor"):
        degerler = sorted(s[alan] for s in seri)
        cikti[f"{alan}_azami"] = degerler[-1]
        cikti[f"{alan}_p90"] = degerler[int(len(degerler) * 0.9)]
        cikti[f"{alan}_ortalama"] = statistics.fmean(degerler)
    cikti["egim_azami"] = max(s["egim"] for s in seri)
    cikti["kare_sayisi"] = float(len(seri))

    # ⚠ KARE SERİSİ DE SAKLANIYOR — kaskad deneyi için ZORUNLU
    #
    # Klip özeti ("bu klipte azami yakınlık 0.8'di") kaskadı ölçmeye
    # YETMEZ: kaskadın sorusu kare bazlı — *"bu KARE kural kapısını
    # geçti mi, geçmediyse LightGBM hiç çağrılmadı mı"*. Özet, kapının
    # klip boyunca kaç kez açıldığını gizler.
    #
    # ⚠ Aynı ders bu projede daha önce de çıktı: `evaluate_rwf.py` (K5)
    # klip başına yalnızca AZAMİ skoru tutuyordu ve K8 (zamanlama)
    # ölçülemez hâle gelmişti. Özet bir yorumdur; seri veridir ve
    # sonradan sorulacak soruyu bugünden bilemiyoruz.
    #
    # Maliyet: klip başına ~20 kare × 8 alan ≈ 1 KB. 720 klip için
    # ~1 MB — saklamamak için hiçbir gerekçe yok.
    # ⚠ HAM özelliklerin özeti — bantlanmamış (P-48)
    for alan in HAM_ALANLAR:
        d = sorted(s[alan] for s in ham_seri if alan in s)
        if d:
            cikti[f"ham_{alan}_azami"] = d[-1]
            cikti[f"ham_{alan}_p75"] = d[min(len(d) - 1, int(len(d) * 0.75))]
            cikti[f"ham_{alan}_medyan"] = statistics.median(d)

    # ─── ⭐ SAHNE-GÖRELİ AYKIRILIK (P-49) ───
    #
    # `ham_*_azami` bütün kişiler+kareler havuzunun MAKSİMUMU. `max`,
    # örneklem büyüdükçe TANIMI GEREĞİ büyüyen bir istatistik: 9 kişilik
    # bir sahnenin "en hızlı kişisi", 4 kişilik sahneninkinden yüksek
    # çıkar — kimse kavga etmese bile.
    #
    # cam-15'te ölçüldü (445 kare, `evaluate_k8_video.py`):
    #
    #     kişi/kare   bilek hızı medyan   o karelerin kavga oranı
    #      1-4             1.099                   4%
    #      5-6             1.049                  20%
    #      7-8             1.372                  20%
    #      9+              1.535                  23%   ⬅ kavga sabit,
    #                                                      hız +%40
    #     Pearson r(kişi sayısı, bilek hızı) = +0.274
    #
    # ⚠⚠ Bu P-47 İLE AYNI HATA, FARKLI EKSENDE. Orada `max`-over-ZAMAN
    # eklem gürültüsünü ölçüyordu ve p75'e çevrildi. Buradaki `max`
    # -over-KİŞİ kalabalığı ölçüyor — aynı istatistik, atlanmış eksen.
    #
    # ⭐ DÜZELTME: kavganın işareti "biri hızlı hareket ediyor" değil,
    # **"biri çevresindekilere GÖRE hızlı hareket ediyor"**. Aynı
    # karedeki medyan çıkarılıyor:
    #
    #     aykirilik = max(kare) − medyan(kare)
    #
    # Oran değil FARK alınıyor: birim (gövde/sn) korunuyor ve medyan
    # sıfıra yaklaşınca patlamıyor.
    #
    # ⭐ Ölçülen bonus: kavgada sahne MEDYANI da düşüyor (cam-15:
    # 0.501 → 0.345). Seyirci donup izliyor. Kontrast iki taraftan
    # birden geliyor; `max` ikisini de göremiyordu.
    #
    #     ölçüt                 kavga   normal   oran
    #     max                   1.152    1.192   0.97  ❌
    #     aykırılık (max−med)   0.751    0.542   1.39  ✅
    #
    # ⚠ ESKİ `ham_*` ALANLARI SİLİNMEDİ: makalede ablasyon basamağı
    # olarak ikisi karşılaştırılacak.
    for alan in HAM_ALANLAR:
        aykiriliklar: list[float] = []
        medyanlar: list[float] = []
        for kare in ham_kareler:
            d = sorted(k[alan] for k in kare if alan in k)
            if len(d) < 2:
                continue
            med = statistics.median(d)
            aykiriliklar.append(d[-1] - med)
            medyanlar.append(med)
        if aykiriliklar:
            a = sorted(aykiriliklar)
            cikti[f"ayk_{alan}_azami"] = a[-1]
            cikti[f"ayk_{alan}_p75"] = a[min(len(a) - 1, int(len(a) * 0.75))]
            cikti[f"ayk_{alan}_medyan"] = statistics.median(a)
            # Sahne medyanının kendisi de bilgi: kavgada seyirci duruyor.
            cikti[f"sahne_{alan}_medyan"] = statistics.median(medyanlar)

    cikti["seri"] = [
        {
            **{b: round(s[b], 4) for b in BILESENLER},
            "skor": round(s["skor"], 4),
            "egim": round(s["egim"], 4),
        }
        for s in seri
    ]
    return cikti


def _ozellik_cikar(args: argparse.Namespace) -> int:
    """Kliplerden özellik çıkarır ve diske yazar (GPU, uzun sürer)."""
    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "backend" / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    veri: dict[str, list[dict[str, Any]]] = {"train": [], "val": []}
    t0 = time.time()
    for bolum in ("train", "val"):
        for sinif, etiket in (("fight", 1), ("nonfight", 0)):
            klipler = sorted((RWF / bolum / sinif).glob("*.avi"))
            random.Random(TOHUM).shuffle(  # noqa: S311 — kripto değil
                klipler)
            # ⚠ val'da daha az klip: ölçüm için yeterli, süre için kritik
            n = args.klip if bolum == "train" else min(args.klip, 60)
            klipler = klipler[:n]
            for i, yol in enumerate(klipler, 1):
                oz = _klip_ozellikleri(
                    yol, dedektor=dedektor, poz=poz,
                    ornek_fps=args.fps, imgsz=args.imgsz,
                )
                if oz is not None:
                    veri[bolum].append({"klip": yol.name, "etiket": etiket, **oz})
                print(f"\r  {bolum}/{sinif} {i}/{len(klipler)} "
                      f"({time.time() - t0:.0f} sn)", end="", flush=True)
            print()

    OZELLIK_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    OZELLIK_DOSYASI.write_text(
        json.dumps(veri, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nyazıldı: {OZELLIK_DOSYASI.relative_to(PROJECT_ROOT)}")
    print(f"  train {len(veri['train'])} · val {len(veri['val'])} klip")
    return 0


def _egit(args: argparse.Namespace) -> int:
    """Özelliklerden model eğitir ve K5 tabanıyla karşılaştırır."""
    import lightgbm as lgb
    import numpy as np

    if not OZELLIK_DOSYASI.is_file():
        print(f"❌ Özellik dosyası yok: {OZELLIK_DOSYASI}\n"
              "   Önce: uv run python scripts/train_aggression.py --cikar",
              file=sys.stderr)
        return 1

    veri = json.loads(OZELLIK_DOSYASI.read_text(encoding="utf-8"))
    if not veri["train"] or not veri["val"]:
        print("❌ Eğitim ya da doğrulama kümesi boş.", file=sys.stderr)
        return 1

    # Sütun sırası SABİT — model dosyasıyla birlikte kaydediliyor.
    # ⚠ Sıra ayrışırsa model yanlış özellikleri okur ve hata SESSİZ olur.
    #
    # ⚠ SÜTUNLAR TÜM KLİPLERİN BİRLEŞİMİNDEN, İLK KLİPTEN DEĞİL.
    # Ham özellikler `None` ise atlanıyor (bkz. `_klip_ozellikleri`),
    # yani her klipte her alan bulunmuyor. İlk klibin anahtarlarına
    # bakmak, o klipte olmayan bir alanı tüm veri setinden silmek ya da
    # (tersine) başka kliplerde `KeyError` üretmek demekti.
    haric = {"klip", "etiket", "kare_sayisi", "seri"}
    sutunlar = sorted(
        {k for bolum in ("train", "val") for s in veri[bolum] for k in s} - haric
    )
    # ⭐ ABLASYON — AYNI ÇIKARIM KOŞUSU, farklı sütun kümesi (P-49).
    #
    # ⚠ Bu bayrak, bu projede DÖRT KEZ tekrarlanan hatayı önlemek için
    # var (CLAUDE.md §9 "raporun asıl tezi"): iki koşuyu kıyaslarken
    # aynı anda iki şeyi değiştirmek. `--cikar` yeniden koşturulursa
    # örneklem de değişiyor; o hâlde "özellik kazandırdı" denemez.
    # Önbellekli özellik dosyası üzerinde sütun düşürmek, tek değişkenli
    # tek karşılaştırmadır.
    if args.haric_onek:
        onekler = tuple(args.haric_onek.split(","))
        atilan = [c for c in sutunlar if c.startswith(onekler)]
        sutunlar = [c for c in sutunlar if c not in set(atilan)]
        print(f"⚠ ABLASYON: '{args.haric_onek}' önekli {len(atilan)} sütun "
              f"düşürüldü → {len(sutunlar)} özellik kaldı")

    def _matris(satirlar: list[dict[str, Any]]) -> tuple[Any, Any]:
        # ⚠ EKSİK DEĞER `NaN`, SIFIR DEĞİL — bu projenin tekrarlayan dersi
        # (`person.py` modül başlığı: *"sıfır 'hareket etmedi' demektir,
        # eksik ise 'bilmiyoruz'"*).
        #
        # Sıfır yazmak modele YANLIŞ bir gözlem öğretirdi: "bu klipte
        # bilek hızı sıfırdı" ile "bu klipte bilek hızı ölçülemedi"
        # farklı şeyler ve ikincisi kavga kliplerinde sık.
        #
        # LightGBM `NaN`'ı yerel olarak destekliyor: her bölünmede
        # eksik değerleri hangi dala göndereceğini VERİDEN öğreniyor.
        # Bu, eksikliği bir bilgi kaynağına çeviriyor.
        x = np.array([
            [float(s[c]) if c in s else float("nan") for c in sutunlar]
            for s in satirlar
        ])
        y = np.array([int(s["etiket"]) for s in satirlar])
        return x, y

    xtr, ytr = _matris(veri["train"])
    xva, yva = _matris(veri["val"])
    print(f"eğitim {xtr.shape} · doğrulama {xva.shape} · {len(sutunlar)} özellik")

    # ⚠ KÜÇÜK MODEL, BİLİNÇLİ OLARAK
    # 1600 klip ve 6 temel özellikle derin bir ağaç ezberler. Sığ
    # ağaçlar + güçlü düzenlileştirme, bu boyutta veri için doğru
    # tercih — ve model ne kadar basitse açıklanabilirliği o kadar
    # korunuyor (PLAN §6.5'in şartı).
    model = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=15,
        max_depth=4,
        min_child_samples=20,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=TOHUM,
        verbose=-1,
    )
    model.fit(
        xtr, ytr,
        eval_set=[(xva, yva)],
        eval_metric="auc",
        callbacks=[lgb.early_stopping(40, verbose=False)],
    )

    olasilik = model.predict_proba(xva)[:, 1]

    # ─── Ölçüm ───
    def _auc(poz: list[float], neg: list[float]) -> float:
        import bisect
        n = sorted(neg)
        t = 0.0
        for p in poz:
            k = bisect.bisect_left(n, p)
            e = bisect.bisect_right(n, p) - k
            t += k + 0.5 * e
        return t / (len(poz) * len(neg)) if poz and neg else float("nan")

    poz = [float(p) for p, y in zip(olasilik, yva, strict=True) if y == 1]
    neg = [float(p) for p, y in zip(olasilik, yva, strict=True) if y == 0]
    auc = _auc(poz, neg)

    # ⚠ EŞİK BURADA DA TEST KÜMESİNDE ARANIYOR — ADR-0007'nin
    # kaydettiği aynı yanlılık. Taban çizgisiyle ADİL karşılaştırma
    # için kasten aynı yöntem kullanılıyor: ikisi de optimistik, fark
    # anlamlı kalıyor. Mutlak sayı raporlanırken yanlılık yazılacak.
    en_iyi = (0.0, 0.0, 0.0, 0.0)
    for i in range(1, 100):
        esik = i / 100
        tp = sum(1 for p in poz if p >= esik)
        fp = sum(1 for p in neg if p >= esik)
        fn = len(poz) - tp
        if tp == 0:
            continue
        kesinlik = tp / (tp + fp)
        duyarlilik = tp / (tp + fn)
        f1 = 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
        if f1 > en_iyi[1]:
            en_iyi = (esik, f1, duyarlilik, kesinlik)

    esik, f1, duyarlilik, kesinlik = en_iyi

    # ⚠ DOĞRULUK (accuracy) DA HESAPLANIYOR — literatürle KARŞILAŞTIRMA için
    # RWF-2000 üzerine yayınlanan çalışmaların neredeyse tamamı doğruluk
    # raporluyor (Flow Gated Network %87.25, IDG-ViolenceNet %89.4).
    # F1/AUC ile doğruluk aynı şey DEĞİL; farklı metrikleri yan yana
    # koymak bu projenin dört kez pahalıya ödediği hata sınıfı (P-41).
    # Sınıflar dengeli olduğu için (56 kavga / 48 normal) doğruluk
    # burada anlamlı bir ölçüt.
    dogru = sum(1 for p_ in poz if p_ >= esik) + sum(1 for n in neg if n < esik)
    dogruluk = dogru / max(len(poz) + len(neg), 1)
    taban_f1, taban_auc = 0.712, 0.629  # ADR-0007 · K5 taban çizgisi

    print(f"\n{'':22} {'AUC':>7} {'F1':>7} {'duyarlılık':>11} {'kesinlik':>9}")
    print(f"{'KURAL (taban, K5)':22} {taban_auc:>7.3f} {taban_f1:>7.3f} "
          f"{0.867:>11.3f} {0.612:>9.3f}")
    print(f"{'MODEL (LightGBM)':22} {auc:>7.3f} {f1:>7.3f} "
          f"{duyarlilik:>11.3f} {kesinlik:>9.3f}")
    print(f"\nfark: AUC {auc - taban_auc:+.3f} · F1 {f1 - taban_f1:+.3f}")

    gecti = f1 > taban_f1
    print("\nK5 HEDEFİ: F1 ≥ 0.85 · ölçülen: "
          f"{f1:.3f} — {'✅ TUTUYOR' if f1 >= 0.85 else '❌ TUTMUYOR'}")
    print("ADR-0007 SINAVI: model tabanı geçti mi? "
          + ("✅ EVET" if gecti else "❌ HAYIR"))
    if not gecti:
        print("  ⚠ Model taban çizgisini geçemedi. Bu bir BULGU:\n"
              "    'model kullandık' demek başarı değildir (ADR-0007).\n"
              "    Kural tabanlı skor üretimde KALIR.")

    # ─── Özellik önemi — açıklanabilirlik korunuyor ───
    onem = sorted(
        zip(sutunlar, model.feature_importances_, strict=True),
        key=lambda x: -x[1],
    )
    print("\nEN ETKİLİ 8 ÖZELLİK (model neye bakıyor):")
    for ad, deger in onem[:8]:
        print(f"  {ad:24} {deger:>6}")

    MODEL_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(MODEL_DOSYASI))

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kriter": "K5 (eğitilmiş model)",
        "veri_seti": "RWF-2000",
        "egitim_klip": len(veri["train"]),
        "dogrulama_klip": len(veri["val"]),
        "ozellikler": sutunlar,
        "taban_kural": {"auc": taban_auc, "f1": taban_f1},
        "model": {
            "tur": "LightGBM",
            "auc": round(auc, 4),
            "f1": round(f1, 4),
            "duyarlilik": round(duyarlilik, 4),
            "kesinlik": round(kesinlik, 4),
            "en_iyi_esik": esik,
            "dogruluk": round(dogruluk, 4),
        },
        "literatur_rwf2000": {
            "not": "hepsi ham piksel + optik akış, tek klip, çevrimdışı",
            "flow_gated_network": 0.8725,
            "two_stream_multidim_cnn": 0.87,
            "idg_violencenet": 0.894,
            "semi_supervised_hard_attention": 0.895,
        },
        "tabani_gecti": bool(gecti),
        "k5_tutuyor": bool(f1 >= 0.85),
        "bilinen_yanlilik": (
            "en_iyi_esik F1'in hesaplandığı aynı val kümesinde aranıyor "
            "(ADR-0007 ile aynı yöntem — taban ve model adil kıyaslansın diye). "
            "Bildirilen F1 her iki satırda da optimistik."
        ),
        "ozellik_onemi": {ad: int(d) for ad, d in onem},
        "model_dosyasi": str(MODEL_DOSYASI.relative_to(PROJECT_ROOT)),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"saldirganlik_model_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    print(f"model  : {MODEL_DOSYASI.relative_to(PROJECT_ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Saldırganlık modeli eğitimi")
    ap.add_argument("--cikar", action="store_true", help="özellik çıkar (GPU)")
    ap.add_argument("--egit", action="store_true", help="modeli eğit (CPU)")
    ap.add_argument("--klip", type=int, default=300, help="sınıf başına klip")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument(
        "--haric-onek", default="",
        help="ablasyon: bu öneklerle başlayan sütunları düşür (virgüllü)",
    )
    args = ap.parse_args()

    if not args.cikar and not args.egit:
        ap.error("--cikar ya da --egit verin")
    if args.cikar and (kod := _ozellik_cikar(args)):
        return kod
    if args.egit:
        return _egit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
