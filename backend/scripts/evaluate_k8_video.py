"""K8 — ERKEN UYARI AVANSI, kesilmemiş tek video üzerinde.

⭐ PROJENİN ÖZGÜN KATKISI — ve neden ancak ŞİMDİ ölçülebiliyor
--------------------------------------------------------------
K8 kriteri (PLAN §1.4): *"sistem olayı ≥2 saniye ÖNCE haber vermeli."*

İlk deneme RWF-2000 üzerindeydi ve **ölçülemedi.** 20 klip elle
etiketlendi ve sebep sayıyla ortaya çıktı:

    kavga başlangıcı:  min 0.23 sn · MEDYAN 0.58 sn · max 3.07 sn

RWF klipleri olayın etrafından KIRPILMIŞ; olay öncesi bağlam yok.
Bizim özellik penceremiz 3 saniye — sistem penceresini dolduramadan
kavga başlamış oluyor. *"Kaç saniye önce"* sorusu o veri setinde
**tanımsız.**

⚠ Bu, alanın kıyaslama setine yönelik veriye dayalı bir eleştiri ve
raporda böyle yer alacak: **şiddet tespiti literatürünün en yaygın
kıyaslama seti, o literatürün örtük olarak iddia ettiği "erken uyarı"
özelliğini ölçemez.**

Bu betik UBI-Fights'tan alınan **kesilmemiş** bir gözetim videosuyla
çalışıyor (cam-15).

⚠⚠ VERİ SETİNİN ETİKETİ OLAYIN BAŞLANGICINI VERMİYOR (07.09.2026)
------------------------------------------------------------------
UBI-Fights, F_74 için üç "şiddet penceresi" veriyor:

   58.0– 59.6s · 64.0– 73.4s · 96.9–112.0s

İlk ölçümler bunları esas aldı ve *"58 saniye olay öncesi bağlam"*
yazıldı. **Videoya bakılınca bu yanlış çıktı:**

   32.0s  normal — yürüyen insanlar
   33.6s  ⬅ açık saldırgan duruş, kollar açılmış
   34.4s  hamle
   36.8s  ⬅ YERDE YATAN KİŞİ
   38.4s  yerdekine müdahale

Fiziksel çatışma **~32.8 sn**'de başlıyor; etiket ~25 saniye GEÇ.

⭐ Geç bir başlangıç etiketi erken uyarı ölçümünü SİSTEMATİK OLARAK
ŞİŞİRİR. 37.8 sn'deki bir alarm, 58.0'a göre "+20.2 sn ERKEN"
görünür; 32.8'e göre "4.8 sn GEÇ"tir. **Aynı sayı, etikete göre
başarı ya da başarısızlık okunur.**

⚠ Veri setinin etiketi yanlış değil — kendi tanımına (şiddet
pencereleri) göre doğru. Yanlış olan, onu başka bir sorunun
("olay ne zaman başladı") cevabı sanmaktı.

Bu yüzden varsayılan yer gerçeği `cam-15.gorsel.json` (elle görsel
doğrulama). Veri setinin etiketi `--etiket veriseti` ile korunuyor;
ikisinin farkı raporlanacak bir bulgu.

⚠⚠ KAMERA SABİT DEĞİL — bu video elde tutulan bir telefonla çekilmiş.
Boru hattımız sabit kamera varsayıyor (`botsort.py`: `gmc_method="none"`,
`with_reid=False`). Kamera hareketi tüm kutulara sahte hız ekler; bu
videodaki hız temelli her özellik o yanlılığı taşıyor.

⭐ Aynı videoda hem AVANS hem YANLIŞ ALARM ölçülebiliyor — ikisi
birbirinden ayrılamaz ve tek başına avans raporlamak yanıltıcıdır.

İki skorlayıcı karşılaştırılıyor
--------------------------------
    KURAL   — `aggression.py` tırmanma skoru (elle ağırlıklı)
    MODEL   — LightGBM, KAYAN PENCERE ile çevrimiçi uygulanıyor

⚠ MODEL KLİP SINIFLANDIRICISI OLARAK EĞİTİLDİ, BURADA ÇEVRİMİÇİ
KULLANILIYOR. Eğitimde 5 saniyelik klibin tamamından özet çıkarılmıştı;
burada her karede SON 5 SANİYENİN özeti çıkarılıp modele veriliyor.
Pencere uzunluğu kasten aynı — farklı olsaydı model eğitildiğinden
başka bir dağılımla beslenirdi.

⚠ ÜÇ SEGMENT VAR, ÜÇÜ AYNI DEĞİL
Yalnızca BİRİNCİ segment gerçek bir "başlangıç": öncesinde 58 saniye
kavgasız bağlam var. İkinci ve üçüncü segmentlerden önce skor zaten
yükselmiş olabilir; oradan "avans" hesaplamak kendi kuyruğunu ölçmek
olurdu. Bu yüzden birinci segment AYRI raporlanıyor.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI (GPU paylaşılmamalı).

Kullanım
--------
    uv run python scripts/evaluate_k8_video.py
    uv run python scripts/evaluate_k8_video.py --fps 2.75 --kamera cam-15
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
VIDEOLAR = PROJECT_ROOT / "data" / "videos"
ETIKETLER = PROJECT_ROOT / "data" / "annotations"
MODEL_DOSYASI = PROJECT_ROOT / "backend" / "models" / "saldirganlik_lgbm.txt"

# ⚠ Eğitimdeki klip uzunluğuyla AYNI (RWF klipleri 5 sn). Model o
# uzunluktaki özetlerle eğitildi; başka bir pencere, eğitildiğinden
# farklı bir dağılım demek.
PENCERE_S = 5.0

# ⚠ ÖZELLİK ADLARI EĞİTİM BETİĞİNDEN İÇE AKTARILIYOR, KOPYALANMIYOR.
# Kopyalasaydık iki liste zamanla ayrışır ve model eğitildiğinden
# BAŞKA sütunlarla beslenirdi — hata sessiz olurdu (skor üretilir,
# yalnızca yanlış olur). Aynı tuzak `analytics/ifade.py` etiket
# kümesinde de var ve orada bir testle korunuyor.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_aggression import BILESENLER, HAM_ALANLAR  # noqa: E402

# Denenecek eşikler — avans ↔ yanlış alarm eğrisi için.
ESIKLER = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70,
           0.80, 0.85, 0.90, 0.95)

# ⚠⚠ GÖREV DÖNGÜSÜ KISITI — bu olmadan K8 ANLAMSIZ
#
# İlk sürüm yalnızca "saatlik ayrık alarm sayısı"na bakıyordu ve
# şu sonucu üretti:
#
#     eşik 0.05 → S1 avans +56.9 sn, alarm 29.5/saat  ✅ "TUTUYOR"
#
# Sayılar doğruydu, çıkarım saçmaydı: video 160 saniye, kavga 58.
# saniyede başlıyor. +56.9 sn avans, skorun 1.1. saniyede eşiği
# geçtiği anlamına geliyor — yani dedektör **baştan sona açık.**
# Normal dönemin %99.1'inde eşiğin üstünde.
#
# ⚠ Ayrık alarm sayısı bunu GİZLİYOR: skor hiç düşmezse 0→1 geçişi
# de olmuyor, sayaç "az alarm" diyor. Sürekli bağıran bir alarm ile
# hiç bağırmayan bir alarm aynı derecede işe yaramazdır.
#
# ⭐ Doğru ölçüt GÖREV DÖNGÜSÜ: normal dönemin yüzde kaçında eşik
# aşılıyor. %10 üstü bir dedektör "erken uyardı" diyemez — zaten
# hep uyarıyordur.
#
# Sınır %10 seçildi ve keyfi olduğu yazılıyor: operatörün alarm
# panelinde zamanın onda birinden fazla kırmızı görmesi, K7'nin asıl
# riskini (sistemi umursamamaya başlama) doğrudan besler.
AZAMI_GOREV_DONGUSU = 0.10

# ⚠⚠ GEÇERLİLİK KONTROLÜ — avanstan ÖNCE sorulması gereken soru
#
# İlk iki sürüm de yanlış "✅ TUTUYOR" verdi. İkincisi şunu ölçtü:
# *"skor olaydan önce eşiği geçti mi?"* — ve geçmişti (+19.8 sn).
#
# Ama sorulmayan soru şuydu: **skor olaya TEPKİ VERİYOR MU?**
# Dönem bazında bakınca cevap hayır çıktı:
#
#     dönem                KURAL p50   MODEL p50
#     NORMAL-1 (0-38s)       0.066       0.400
#     KAVGA-2  (64-73s)      0.080       0.424
#     KAVGA-3  (97-112s)     0.078       0.313   ⬅ en düşük
#     NORMAL-2 (112-160s)    0.087       0.421   ⬅ kavgadan yüksek
#
# Skor kavgada normalden yüksek DEĞİL. O hâlde "olaydan önce eşiği
# geçti" bir öngörü değil, olaydan önce denk gelmiş bir yanlış
# pozitiftir.
#
# ⭐ Bir dedektörün "erken uyardığı" ancak olayı normalden AYIRT
# ettiği gösterildikten sonra söylenebilir. Ayırt etmiyorsa geçiş
# anı tesadüftür ve avans sayısı anlamsızdır.
#
# Ölçüt: kavga dönemlerinin medyanı, normal dönemlerin medyanını
# belirgin biçimde (×1.2) aşmalı.
ASGARI_AYIRT_ORANI = 1.2

# ⚠⚠⚠ ÜÇÜNCÜ DÜZELTME — geçerlilik kontrolünün KENDİSİ bozuktu (P-49)
#
# Yukarıdaki kontrol "kavga segmentleri" ile "geri kalan her şeyi"
# kıyaslıyordu. Ama yer gerçeği segmentleri yalnızca FİZİKSEL DARBELERİ
# işaretliyor (segment 1 = 1.7 saniye). Kavgaya giden tartışma,
# yaklaşma, itişme — hepsi "normal" havuzuna düşüyordu.
#
# ⭐ Bu, bir ERKEN UYARI dedektörünü tam da erken uyardığı için
# cezalandırır: olaydan önce yükselen skor, "normal"i yükseltir ve
# oran 1'in altına iner. Ölçüt, ölçtüğü şeyi imkânsız kılıyordu.
#
# Ölçülen (cam-15, iki ayrı model, aynı desen):
#
#     dönem                model p50
#     NORMAL (uzak)          0.348
#     TIRMANMA (-20 sn)      0.733   ⬅ EN YÜKSEK
#     KAVGA (darbeler)       0.331   ⬅ EN DÜŞÜK
#
# ⚠ Ve bu bir kalabalık artefaktı DEĞİL — kişi sayısı eşleştirilmiş
# kontrolde tırmanma her kuşakta normalin üstünde kaldı:
#
#     kişi/kare   NORMAL   TIRMANMA   KAVGA
#      1-4         0.329     0.848      —
#      5           0.315     0.839    0.326
#      6           0.249     0.576    0.388
#      7-8         0.447     0.512    0.291
#
# ⚠ Kalabalık arttıkça ayrım zayıflıyor (2.6× → 1.14×): raporlanacak
# bir ÇALIŞMA SINIRI, gizlenecek bir kusur değil.
#
# ⚠ Skorun darbe anında DÜŞMESİ de raporlanıyor: model temasa gelişi
# öğrenmiş, temasın kendisini değil. RWF'nin 5 sn'lik kliplerinde
# yaklaşma payı darbelerden büyük — beklenebilir bir sonuç.
# ⚠ İLK DEĞER 20.0 SANİYEYDİ VE BU VİDEODA ÖLÇÜMÜ ÇÖKERTTİ.
#
# cam-15'in (F_45) olay öncesi bağlamı 23.5 saniye. 20 saniyelik bir
# tırmanma penceresi o bağlamın TAMAMINI yutuyor: "uzak normal"
# havuzunda 10 örnek kalıyor, medyanı 0.000 çıkıyor ve ayırt etme
# oranı 64 MİLYON gibi anlamsız bir sayıya fırlıyor.
#
# ⭐ Doğru büyüklük K8 hedefinden türetiliyor: hedef ≥2 saniye avans.
# Bir dedektöre "erken uyardı" kredisi vermek için makul üst sınır
# hedefin 3 katı. Bundan daha erken bir ateşleme erken uyarı değil,
# olaydan bağımsız bir yanlış pozitiftir — ve tam bu ayrım P-49'da
# atlanmıştı.
#
# ⚠ Ayrıca mevcut bağlamın 1/3'üyle sınırlanıyor: pencere bağlamı
# yutarsa kıyaslanacak normal kalmaz.
TIRMANMA_PENCERESI_S = 6.0

# ⚠⚠ ISINMA — ölçüm dışı bırakılan ilk saniyeler
#
# Özellik penceresi PENCERE_S = 5 sn. Videonun ilk saniyelerinde bu
# pencere DOLU DEĞİL: model, eğitildiğinden çok daha az örnekten
# hesaplanmış bir özetle besleniyor ve çıktısı anlamsız.
#
# Bu, uydurma bir kısıt değil — somut bir hata üretti. Görsel yer
# gerçeğiyle ilk koşuda şu çıktı:
#
#     eşik 0.80 → "S1 avans +31.7 sn"  ✅ görünüyordu
#
# Olay 32.8 sn'de başlıyor; +31.7 avans, skorun **1.1. saniyede**
# eşiği geçtiği anlamına geliyor. Yani "erken uyarı" diye raporlanacak
# olan şey, pencere dolmadan üretilmiş bir çöp skordu.
#
# ⭐ Aynı hata canlı sistemde de biliniyor ve orada zaten uygulanıyor
# (P-28: ilk 90 sn atılıyor). Ölçüm betiği o dersi almamıştı.
ISINMA_S = PENCERE_S + 1.0

# ⚠⚠⚠ DÖRDÜNCÜ DÜZELTME — "tespit" ile "ERKEN uyarı" ayrı şeyler
#
# Yukarıdaki geçerlilik kontrolü olay penceresini (tırmanma + kavga)
# tek havuz sayıyor. O hâlde kavga sırasındaki güçlü sinyal, olay
# ÖNCESİ hiçbir sinyal olmasa bile havuzu yukarı çeker ve ölçüt
# "✅ ayırt ediyor" der. Sonra tek bir sivri uç "avans" diye okunur.
#
# Görsel yer gerçeğiyle ölçüldü (cam-15):
#
#     dönem                  n    MODEL p50
#     normal (0-32.8 sn)    36      0.351
#     tırmanma (-20 sn)     56      0.207   ⬅ NORMALDEN DÜŞÜK
#     kavga (32.8-75)      117      0.819   ⬅ güçlü
#
# Model kavgayı normalden 2.3× ayırıyor — bu iyi bir TESPİT.
# Ama olay öncesinde skoru normalin altında; ortada ERKEN UYARI YOK.
# Eşik 0.50'de görünen "+15.2 sn avans", tırmanma medyanı 0.207 iken
# oluşmuş tek bir sivri uçtur.
#
# ⭐ Bu yüzden avans iddiası ayrı bir ön koşula bağlandı: olay ÖNCESİ
# pencerenin medyanı, normalin medyanını aşmalı. Aşmıyorsa dedektör
# "olayı tespit ediyor ama önceden haber vermiyor" diye raporlanır —
# ki bu da geçerli ve raporlanabilir bir sonuçtur.
ASGARI_ERKEN_ORANI = 1.2


def _p(sirali: list[float], oran: float) -> float:
    if not sirali:
        return 0.0
    return sirali[min(len(sirali) - 1, int(len(sirali) * oran))]


def _skor_serileri(
    yol: Path, *, dedektor: Any, poz: Any, ornek_fps: float, imgsz: int,
    sutunlar: list[str], booster: Any,
) -> list[dict[str, float]]:
    """Videoyu boru hattından geçirir, her örneklenen kare için skor üretir.

    Dönen: `[{"ts": .., "kural": .., "model": ..}, ...]`

    ⚠ `train_aggression.py · _klip_ozellikleri` ile AYNI özellik
    hesabı — tek fark, orada klibin TAMAMI özetleniyordu, burada
    KAYAN PENCERE özetleniyor. Hesap ayrışırsa model eğitildiğinden
    başka bir şeyle beslenir ve hata sessiz olur.
    """
    import cv2
    import numpy as np

    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    adim = max(1, round(kaynak_fps / ornek_fps))

    takipci = BotSortTracker(frame_rate=int(max(1, ornek_fps)))
    depo = PencereDeposu()
    skorlayici = TirmanmaSkorlayici()

    # Kayan pencereler — (ts, değer sözlüğü)
    pencere_seri: deque[tuple[float, dict[str, float]]] = deque()
    # ⚠ KARE BAZLI — her eleman (ts, o karedeki kişilerin listesi).
    # Düz havuz olsaydı "aynı karedeki diğerlerine göre" sorusu
    # sorulamazdı (P-49 aykırılık özelliği).
    pencere_ham: deque[tuple[float, list[dict[str, float]]]] = deque()

    cikti: list[dict[str, float]] = []
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

        kural_skor = 0.0
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

            # ─── TANI: takip sürekliliği ve özellik erişilebilirliği ───
            # Hipotez: kavga = yoğun örtüşme → kimlik kopuyor → pencere
            # sıfırlanıyor → tam da kavga edenler EN AZ zamansal veri
            # üretiyor. Doğruysa sorun modelde değil algıda.
            tani_ornek = [k.ornek_sayisi for k in kisiler if k.track_id >= 0]
            tani_zamansal = [
                1.0 if k.bilek_hizi_p75 is not None else 0.0
                for k in kisiler if k.track_id >= 0
            ]
            tani_bilek = [
                k.bilek_hizi_p75 for k in kisiler
                if k.track_id >= 0 and k.bilek_hizi_p75 is not None
            ]

            kare_kisileri = [
                {a: float(v) for a in HAM_ALANLAR
                 if (v := getattr(kisi, a, None)) is not None}
                for kisi in kisiler if kisi.track_id >= 0
            ]
            if kare_kisileri:
                pencere_ham.append((ts, kare_kisileri))

            if skorlar:
                en_riskli = max(skorlar, key=lambda s: s.skor)
                kural_skor = float(en_riskli.skor)
                satir = dict.fromkeys(BILESENLER, 0.0)
                satir.update({k: float(v) for k, v in en_riskli.bilesenler.items()
                              if k in BILESENLER})
                satir["skor"] = kural_skor
                satir["egim"] = float(en_riskli.egim)
                pencere_seri.append((ts, satir))

        # Pencereyi buda
        while pencere_seri and ts - pencere_seri[0][0] > PENCERE_S:
            pencere_seri.popleft()
        while pencere_ham and ts - pencere_ham[0][0] > PENCERE_S:
            pencere_ham.popleft()

        # ─── Model skoru: pencere özetini modele ver ───
        model_skor = 0.0
        if pencere_seri:
            ozet: dict[str, float] = {}
            seri_d = [s for _t, s in pencere_seri]
            for alan in (*BILESENLER, "skor"):
                d = sorted(s[alan] for s in seri_d)
                ozet[f"{alan}_azami"] = d[-1]
                ozet[f"{alan}_p90"] = _p(d, 0.90)
                ozet[f"{alan}_ortalama"] = statistics.fmean(d)
            ozet["egim_azami"] = max(s["egim"] for s in seri_d)
            ham_d = [s for _t, kare in pencere_ham for s in kare]
            for alan in HAM_ALANLAR:
                d = sorted(s[alan] for s in ham_d if alan in s)
                if d:
                    ozet[f"ham_{alan}_azami"] = d[-1]
                    ozet[f"ham_{alan}_p75"] = _p(d, 0.75)
                    ozet[f"ham_{alan}_medyan"] = statistics.median(d)
            # ⭐ AYKIRILIK — eğitimle BİREBİR aynı hesap (P-49).
            # `train_aggression.py · _klip_ozellikleri` ile aynı formül:
            # kare içinde max − medyan, sonra pencere boyunca özetle.
            # ⚠ İkisi ayrışırsa hata SESSİZ olur: model var olmayan bir
            # dağılımdan sütun okur ve skor sessizce bozulur.
            for alan in HAM_ALANLAR:
                ayk: list[float] = []
                med_l: list[float] = []
                for _t, kare in pencere_ham:
                    dd = sorted(k[alan] for k in kare if alan in k)
                    if len(dd) < 2:
                        continue
                    m = statistics.median(dd)
                    ayk.append(dd[-1] - m)
                    med_l.append(m)
                if ayk:
                    a_s = sorted(ayk)
                    ozet[f"ayk_{alan}_azami"] = a_s[-1]
                    ozet[f"ayk_{alan}_p75"] = _p(a_s, 0.75)
                    ozet[f"ayk_{alan}_medyan"] = statistics.median(a_s)
                    ozet[f"sahne_{alan}_medyan"] = statistics.median(med_l)
            # ⚠ Eksik alan `NaN` — eğitimle AYNI kural.
            x = np.array([[ozet.get(c, float("nan")) for c in sutunlar]])
            model_skor = float(booster.predict(x)[0])

        satir_c = {"ts": ts, "kural": kural_skor, "model": model_skor}
        if izler:
            satir_c["kisi"] = float(len(tani_ornek))
            satir_c["iz_omru"] = (
                float(statistics.median(tani_ornek)) if tani_ornek else 0.0)
            satir_c["zamansal_oran"] = (
                statistics.fmean(tani_zamansal) if tani_zamansal else 0.0)
            # ⭐ KARAR VERİCİ SAYI: ham özelliğin kendisi ayırt ediyor mu?
            satir_c["ham_bilek_p75"] = max(tani_bilek) if tani_bilek else 0.0
            # ⭐ SAHNE-GÖRELİ AYKIRILIK (P-49 düzeltmesi)
            # `max` kalabalıkla birlikte tanımı gereği büyüyor. Kavganın
            # işareti "biri hızlı" değil, "biri ÇEVRESİNDEKİLERE GÖRE
            # hızlı". Aynı karedeki medyanı çıkarmak kalabalık etkisini
            # götürüyor — payda değil, fark alınıyor: ölçü birimi
            # (gövde/sn) korunuyor.
            if len(tani_bilek) >= 2:
                med = statistics.median(tani_bilek)
                satir_c["bilek_aykirilik"] = max(tani_bilek) - med
                satir_c["bilek_medyan"] = med
            else:
                satir_c["bilek_aykirilik"] = 0.0
                satir_c["bilek_medyan"] = tani_bilek[0] if tani_bilek else 0.0
        cikti.append(satir_c)
        kare_no += 1

    cap.release()
    return cikti


def _avans_olc(
    seri: list[dict[str, float]], alan: str, esik: float,
    segmentler: list[tuple[float, float]],
) -> dict[str, Any]:
    """Her olay için avans (olay başlangıcı − ilk eşik geçişi).

    ⚠ GEÇİŞ, OLAYDAN ÖNCEKİ SESSİZ DÖNEMDE ARANIYOR
    Bir segment için avans, o segmentten ÖNCE ve bir önceki segmentin
    BİTİŞİNDEN SONRA aranan ilk eşik geçişidir. Aksi hâlde bir önceki
    kavganın kuyruğu "erken uyarı" sayılırdı — sistem hâlâ bağırıyor
    olduğu için değil, yeni olayı öngördüğü için değil.
    """
    avanslar: list[dict[str, Any]] = []
    for i, (bas, bit) in enumerate(segmentler):
        onceki_bitis = segmentler[i - 1][1] if i > 0 else 0.0
        gecis = None
        for s in seri:
            if s["ts"] < onceki_bitis:
                continue
            if s["ts"] > bit:
                break
            if s[alan] >= esik:
                gecis = s["ts"]
                break
        avanslar.append({
            "segment": i + 1,
            "olay_bas": round(bas, 2),
            "gecis": round(gecis, 2) if gecis is not None else None,
            # Pozitif = ÖNCE uyardı · Negatif = GEÇ kaldı · None = kaçırdı
            "avans_s": round(bas - gecis, 2) if gecis is not None else None,
            "temiz_baslangic": i == 0,
        })
    return {"esik": esik, "segmentler": avanslar}


def _yanlis_alarm(
    seri: list[dict[str, float]], alan: str, esik: float,
    segmentler: list[tuple[float, float]], sure: float,
    dogru_normal: list[tuple[float, float]] | None = None,
) -> dict[str, float]:
    """Normal dönemlerde eşiği aşan sürenin oranı ve saatlik alarm hızı.

    ⚠ Kavga segmentleri ve etraflarındaki 2 sn TAMPON hariç tutuluyor:
    olayın hemen bitişindeki sönme kuyruğu "yanlış alarm" değildir.

    ⚠⚠ `dogru_normal` verilirse yanlış alarm YALNIZCA orada sayılır.
    Görsel olarak normal olduğu doğrulanmamış bir aralıkta "yanlış
    alarm" saymak, alarmın yanlış olduğunu VARSAYMAK demektir — K7'de
    aynı hata yapılmış ve düzeltilmişti (CLAUDE.md: *"11.69 bir alarm
    oranı, yanlış alarm oranı değil"*).
    """
    tampon = 2.0
    if dogru_normal:
        normal = [s for s in seri
                  if any(a <= s["ts"] <= b for a, b in dogru_normal)]
        sure = sum(b - a for a, b in dogru_normal)
        segmentler = []
    else:
        normal = [
            s for s in seri
            if not any(b - tampon <= s["ts"] <= e + tampon for b, e in segmentler)
        ]
    if not normal:
        return {"normal_ornek": 0, "asan_oran": 0.0, "alarm_saatte": 0.0}
    asan = sum(1 for s in normal if s[alan] >= esik)
    # Ayrık alarm SAYISI (art arda aşan kareler tek alarm sayılır)
    olay = 0
    onceki = False
    for s in normal:
        simdi = s[alan] >= esik
        if simdi and not onceki:
            olay += 1
        onceki = simdi
    normal_sure = sure - sum(e - b + 2 * tampon for b, e in segmentler)
    return {
        "normal_ornek": len(normal),
        "asan_oran": round(asan / len(normal), 4),
        "alarm_saatte": round(olay / max(normal_sure, 1e-9) * 3600, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="K8 — kesilmemiş video üzerinde avans")
    ap.add_argument("--kamera", default="cam-15")
    ap.add_argument("--fps", type=float, default=2.75,
                    help="canlı sistemin ÖLÇÜLEN analiz hızı (K4)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument(
        "--etiket", default="gorsel", choices=("gorsel", "veriseti"),
        help="hangi yer gerçeği: gorsel (elle doğrulanmış) | veriseti (UBI)",
    )
    args = ap.parse_args()

    video = VIDEOLAR / f"{args.kamera}.mp4"
    # ⚠⚠ VARSAYILAN 'gorsel' — ÇÜNKÜ VERİ SETİNİN ETİKETİ OLAYIN
    # BAŞLANGICINI VERMİYOR.
    #
    # UBI-Fights, F_74 için üç "şiddet penceresi" işaretliyor; ilki
    # 57.967 sn'de başlıyor. Videoya bakıldığında fiziksel çatışma
    # 32.8-33.6 sn'de başlıyor (33.6 saldırgan duruş, 36.8 yerde kişi).
    # Etiket ~25 saniye GEÇ.
    #
    # ⭐ Geç bir başlangıç etiketi, erken uyarı ölçümünü SİSTEMATİK
    # OLARAK ŞİŞİRİR: 37.8 sn'deki bir alarm 58.0'a göre "+20.2 sn
    # erken" görünür — oysa olay 33 sn'de başlamıştır ve alarm 4.8 sn
    # GEÇ kalmıştır. Aynı sayı, etikete göre "başarı" ya da
    # "başarısızlık" okunur.
    #
    # ⚠ Veri setinin etiketi YANLIŞ DEĞİL: kendi tanımına (şiddet
    # pencereleri) göre doğru. Yanlış olan, onu başka bir sorunun
    # (başlangıç ne zaman) cevabı sanmaktı.
    truth = ETIKETLER / (f"{args.kamera}.gorsel.json" if args.etiket == "gorsel"
                         else f"{args.kamera}.truth.json")
    if not video.is_file():
        print(f"❌ Video yok: {video}", file=sys.stderr)
        return 1
    if not truth.is_file():
        print(f"❌ Yer gerçeği yok: {truth}", file=sys.stderr)
        return 1
    if not MODEL_DOSYASI.is_file():
        print(f"❌ Model yok: {MODEL_DOSYASI}", file=sys.stderr)
        return 1

    yg = json.loads(truth.read_text(encoding="utf-8"))
    segmentler = [(float(s["start_s"]), float(s["end_s"])) for s in yg["segments"]]
    sure = float(yg.get("sure_s", 0)) or max(e for _b, e in segmentler)
    # ⚠ DOĞRULANMIŞ NORMAL — varsa, normal havuzu YALNIZCA burası.
    #
    # Bu videonun 75-160 sn'si olay sonrası kalabalık: ne normal
    # olduğu ne olmadığı doğrulanabildi (veri seti 96.9-112'yi hâlâ
    # "fight" sayıyor). Etiketlenemeyen veriyi "normal" saymak,
    # P-49'da düzeltilen hatanın aynısı olurdu — o yüzden bu aralık
    # hiçbir havuza girmiyor, ölçüm dışı kalıyor.
    dogru_normal = [
        (float(a), float(b)) for a, b in yg.get("dogrulanmis_normal", [])
    ]
    # Tırmanma penceresi mevcut bağlamın 1/3'ünü aşamaz.
    baglam = segmentler[0][0]
    tirmanma_s = min(TIRMANMA_PENCERESI_S, baglam / 3.0)

    import lightgbm as lgb

    booster = lgb.Booster(model_file=str(MODEL_DOSYASI))
    kayitlar = sorted(BENCHMARKS.glob("saldirganlik_model_*.json"))
    if not kayitlar:
        print("❌ Model ölçüm JSON'u yok.", file=sys.stderr)
        return 1
    sutunlar = json.loads(kayitlar[-1].read_text(encoding="utf-8"))["ozellikler"]

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "backend" / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    print(f"{args.kamera} · {sure:.0f} sn · {len(segmentler)} kavga segmenti · "
          f"{args.fps} FPS örnekleme · etiket: {args.etiket.upper()}")
    if args.etiket == "gorsel":
        print("  ⚠ ELLE GÖRSEL ETİKET — kullanıcı doğrulaması bekliyor")
    for i, (b, e) in enumerate(segmentler, 1):
        print(f"  segment {i}: {b:6.1f}s – {e:6.1f}s  ({e - b:.1f} sn)")
    print(f"  ⭐ olay öncesi bağlam: {segmentler[0][0]:.0f} saniye\n")

    t0 = time.time()
    seri = _skor_serileri(
        video, dedektor=dedektor, poz=poz, ornek_fps=args.fps,
        imgsz=args.imgsz, sutunlar=sutunlar, booster=booster,
    )
    # ⚠ ISINMA KIRPMASI — pencere dolmadan üretilen skorlar atılıyor.
    # ⚠ Bu, dönem tablolarından ÖNCE yapılmalı. İlk sürümde sonra
    # yapılıyordu: tablolar kırpılmamış seriyi, karar kırpılmış seriyi
    # gösteriyordu — aynı raporun iki farklı veriye bakması.
    onceki_n = len(seri)
    seri = [s for s in seri if s["ts"] >= ISINMA_S]
    print(f"{onceki_n} örnek · {time.time() - t0:.0f} sn · ısınma: ilk "
          f"{ISINMA_S:.0f} sn atıldı ({onceki_n - len(seri)} örnek)\n")

    # ─── GEÇERLİLİK: skor olaya tepki veriyor mu ───
    def _donem(ts: float) -> str:
        if any(b <= ts <= e for b, e in segmentler):
            return "kavga"
        if any(b - tirmanma_s <= ts < b for b, e in segmentler):
            return "tirmanma"
        if dogru_normal:
            # Doğrulanmış normal listesi varsa dışı ÖLÇÜM DIŞI.
            return ("normal" if any(a <= ts <= b for a, b in dogru_normal)
                    else "haric")
        return "normal"

    def _donem_medyan(alan: str, donemler: tuple[str, ...]) -> float:
        x = [s[alan] for s in seri if _donem(s["ts"]) in donemler]
        return statistics.median(x) if x else 0.0

    print("═══ DÖNEM KIRILIMI ═══")
    print(f"{'dönem':<20} {'n':>5} {'KURAL p50':>10} {'MODEL p50':>10}")
    for ad in ("normal", "tirmanma", "kavga", "haric"):
        g = [s for s in seri if _donem(s["ts"]) == ad]
        if not g:
            continue
        print(f"{ad:<20} {len(g):>5} "
              f"{statistics.median(s['kural'] for s in g):>10.3f} "
              f"{statistics.median(s['model'] for s in g):>10.3f}")
    print()

    # ⭐ KALABALIK ESLEŞTİRİLMİŞ KONTROL — tırmanma sinyali gerçek mi,
    # yoksa o pencerede tesadüfen az kişi mi var?
    print("═══ KİŞİ SAYISI EŞLEŞTİRİLMİŞ KONTROL (model p50) ═══")
    print(f"{'kişi/kare':<12} {'normal':>12} {'tırmanma':>12} {'kavga':>12}")
    kisili = [s for s in seri if "kisi" in s]
    for lo, hi in ((1, 4), (5, 6), (7, 8), (9, 99)):
        hucre = []
        for ad in ("normal", "tirmanma", "kavga"):
            g = [s["model"] for s in kisili
                 if _donem(s["ts"]) == ad and lo <= s["kisi"] <= hi]
            hucre.append(f"{statistics.median(g):.3f}({len(g)})"
                         if len(g) >= 5 else "—")
        print(f"{f'{lo}-{hi}':<12} {hucre[0]:>12} {hucre[1]:>12} {hucre[2]:>12}")
    print()

    # ⚠ ISINMA KIRPMASI — pencere dolmadan üretilen skorlar atılıyor.
    onceki_n = len(seri)
    seri = [s for s in seri if s["ts"] >= ISINMA_S]
    print(f"⚠ ısınma: ilk {ISINMA_S:.0f} sn atıldı "
          f"({onceki_n - len(seri)} örnek) — özellik penceresi dolmamıştı\n")

    # ─── TANI TABLOSU — başarısızlığın nerede olduğunu söyler ───
    def _dm(alan: str, kavgada: bool) -> float:
        x = [s[alan] for s in seri if alan in s
             and any(b <= s["ts"] <= e for b, e in segmentler) == kavgada]
        return statistics.median(x) if x else 0.0

    print("═══ ALGI TANISI — başarısızlık algıda mı, modelde mi ═══")
    print(f"{'ölçüt':<26} {'kavga':>9} {'normal':>9} {'oran':>7}")
    for alan, ad in (
        ("kisi", "kişi/kare"),
        ("iz_omru", "iz ömrü (örnek)"),
        ("zamansal_oran", "zamansal özellik oranı"),
        ("ham_bilek_p75", "ham bilek p75 (max)"),
        ("bilek_medyan", "bilek p75 (sahne medyanı)"),
        ("bilek_aykirilik", "⭐ aykırılık (max − medyan)"),
    ):
        kv, nv = _dm(alan, True), _dm(alan, False)
        print(f"{ad:<26} {kv:>9.3f} {nv:>9.3f} {kv / max(nv, 1e-9):>7.2f}")
    print()

    print("═══ GEÇERLİLİK KONTROLÜ — skor olaya tepki veriyor mu ═══")
    print("⚠ Ölçüt: OLAY PENCERESİ (tırmanma + kavga) ⟷ UZAK NORMAL.")
    print("  Tırmanma 'normal' sayılırsa erken uyarı tanımı gereği kaybeder.")
    print(f"{'skorlayıcı':<10} {'olay p50':>10} {'uzak nrm':>11} {'oran':>7}  sonuç")
    gecerli: dict[str, bool] = {}
    ayirt: dict[str, dict[str, float]] = {}
    normal_n = sum(1 for s in seri if _donem(s["ts"]) == "normal")
    if normal_n < 20:
        print(f"⚠⚠ UZAK NORMAL HAVUZUNDA YALNIZCA {normal_n} ÖRNEK VAR.")
        print("   Medyan güvenilir değil; oranlar bilgi amaçlı okunmalı.\n")
    for alan, etiket in (("kural", "KURAL"), ("model", "MODEL")):
        kv = _donem_medyan(alan, ("tirmanma", "kavga"))
        nv = _donem_medyan(alan, ("normal",))
        oran = kv / max(nv, 1e-9)
        ok = oran >= ASGARI_AYIRT_ORANI
        gecerli[alan] = ok
        ayirt[alan] = {"olay_p50": round(kv, 4), "uzak_normal_p50": round(nv, 4),
                       "tirmanma_p50": round(_donem_medyan(alan, ("tirmanma",)), 4),
                       "kavga_p50": round(_donem_medyan(alan, ("kavga",)), 4),
                       "oran": round(oran, 3), "gecerli": ok}
        print(f"{etiket:<10} {kv:>10.3f} {nv:>11.3f} {oran:>7.2f}  "
              + ("✅ ayırt ediyor" if ok else "❌ AYIRT ETMİYOR — avans anlamsız"))
    print()

    sonuc: dict[str, Any] = {}
    for alan, etiket in (("kural", "KURAL (tırmanma skoru)"),
                         ("model", "MODEL (LightGBM, kayan pencere)")):
        print(f"═══ {etiket} ═══")
        # ⚠ Segment sayısı yer gerçeğine göre değişiyor (görsel etikette
        # 1, veri seti etiketinde 3) — başlık sabit yazılamaz.
        seg_bas = " ".join(f"{f'S{i}':>8}" for i in range(2, len(segmentler) + 1))
        print(f"{'eşik':>6} {'S1 avans':>10} {seg_bas} "
              f"{'kaçan':>6} {'y.alarm/sa':>11} {'aşan%':>7}")
        satirlar = []
        for esik in ESIKLER:
            a = _avans_olc(seri, alan, esik, segmentler)
            ya = _yanlis_alarm(seri, alan, esik, segmentler, sure, dogru_normal)
            av = [s["avans_s"] for s in a["segmentler"]]
            kacan = sum(1 for v in av if v is None)
            gos = [f"{v:+.1f}" if v is not None else "  —" for v in av]
            kuyruk = " ".join(f"{v:>8}" for v in gos[1:])
            print(f"{esik:>6.2f} {gos[0]:>10} {kuyruk} "
                  f"{kacan:>6} {ya['alarm_saatte']:>11.1f} {ya['asan_oran']:>6.1%}")
            satirlar.append({**a, "yanlis_alarm": ya, "kacan": kacan})
        sonuc[alan] = satirlar
        print()

    # ─── K8 kararı — YALNIZCA birinci segment ───
    print("⭐ K8 HEDEFİ: ilk olayda avans ≥ 2.0 sn")
    print("   ⚠ yalnızca SEGMENT 1 sayılıyor — tek 'temiz başlangıç' o.\n")
    karar: dict[str, Any] = {}
    for alan, etiket in (("kural", "KURAL"), ("model", "MODEL")):
        # ⚠ GEÇERLİLİK ÖN KOŞUL: ayırt etmeyen bir skorun avansı
        # ölçülmez. Bu kontrol olmadan iki kez yanlış "✅" verildi.
        if not gecerli[alan]:
            print(f"  {etiket:<6} ❌ TUTMUYOR — skor kavgayı normalden ayırt "
                  f"etmiyor (oran {ayirt[alan]['oran']:.2f} < {ASGARI_AYIRT_ORANI})")
            print("         Eşik geçişi bir öngörü değil, denk gelmiş yanlış pozitif.")
            karar[alan] = {"tutuyor": False, "sebep": "ayırt etmiyor",
                           "ayirt": ayirt[alan]}
            continue
        # ⭐ ERKEN UYARI ÖN KOŞULU — tespit ≠ önceden haber verme.
        t_p50 = _donem_medyan(alan, ("tirmanma",))
        n_p50 = _donem_medyan(alan, ("normal",))
        erken_oran = t_p50 / max(n_p50, 1e-9)
        if erken_oran < ASGARI_ERKEN_ORANI:
            print(f"  {etiket:<6} ❌ ERKEN UYARI YOK — olayı TESPİT ediyor "
                  f"(oran {ayirt[alan]['oran']:.2f}) ama ÖNCEDEN haber vermiyor.")
            print(f"         olay öncesi {tirmanma_s:.1f} sn medyanı "
                  f"{t_p50:.3f} · normal medyanı {n_p50:.3f} "
                  f"(oran {erken_oran:.2f} < {ASGARI_ERKEN_ORANI})")
            # ─── TESPİT GECİKMESİ ───
            # ⚠ Görev döngüsü kısıtı (%10) BURADA YETMİYOR. Bu videoda
            # eşik 0.40 kısıtı geçiyor (%6.9) ama oradaki "+16.6 sn
            # avans" tek bir sivri uçtan geliyor — tırmanma medyanı
            # 0.207 iken eşik 0.40. Görev döngüsü "ne kadar sık"
            # sorusunu yanıtlıyor, "bu geçiş anlamlı mı"yı değil.
            #
            # ⭐ Bu yüzden gecikme, doğrulanmış normalde HİÇ yanlış
            # alarm üretmeyen eşiklerden okunuyor. Böyle bir eşik yoksa
            # gecikme raporlanmıyor — uydurulmuyor.
            temiz = [
                (s["esik"], s["segmentler"][0]["avans_s"])
                for s in sonuc[alan]
                if s["segmentler"] and s["segmentler"][0]["avans_s"] is not None
                and s["yanlis_alarm"]["asan_oran"] == 0.0
            ]
            gecikme_s = None
            if temiz:
                e_iyi = max(temiz, key=lambda x: x[1])
                gecikme_s = round(-e_iyi[1], 2)
                aralik = (min(v for _e, v in temiz), max(v for _e, v in temiz))
                print("         ⭐ YANLIŞ ALARMSIZ EŞİKLERDE TESPİT: olay "
                      f"başlangıcından {-aralik[1]:.1f}–{-aralik[0]:.1f} sn SONRA "
                      f"(eşik {min(e for e, _v in temiz):.2f}–"
                      f"{max(e for e, _v in temiz):.2f})")
                print(f"         en iyisi: eşik {e_iyi[0]:.2f} → "
                      f"{gecikme_s:+.1f} sn gecikme")
            karar[alan] = {
                "tutuyor": False, "sebep": "erken uyarı yok, tespit var",
                "ayirt": ayirt[alan],
                "erken": {"tirmanma_p50": round(t_p50, 4),
                          "normal_p50": round(n_p50, 4),
                          "oran": round(erken_oran, 3)},
                "tespit_gecikmesi_s": gecikme_s,
            }
            continue
        uygun = [
            s for s in sonuc[alan]
            if (v := s["segmentler"][0]["avans_s"]) is not None and v >= 2.0
            # ⚠ GÖREV DÖNGÜSÜ KISITI: sürekli açık bir dedektör
            # "erken uyardı" sayılmaz (gerekçe modül başında).
            and s["yanlis_alarm"]["asan_oran"] <= AZAMI_GOREV_DONGUSU
        ]
        if uygun:
            # ⚠ Aralarından en DÜŞÜK yanlış alarmlı seçiliyor, en yüksek
            # avanslı değil: eşiği düşürerek avansı büyütmek her zaman
            # mümkün ve o bir keşif değil, aritmetik.
            # ⚠ En düşük görev döngülü seçiliyor, en yüksek avanslı DEĞİL:
            # eşiği düşürerek avansı büyütmek her zaman mümkün ve bu bir
            # keşif değil, aritmetik.
            en = min(uygun, key=lambda s: s["yanlis_alarm"]["asan_oran"])
            v = en["segmentler"][0]["avans_s"]
            print(f"  {etiket:<6} ✅ TUTUYOR — eşik {en['esik']:.2f}'te "
                  f"avans {v:+.1f} sn · görev döngüsü %{en['yanlis_alarm']['asan_oran']:.1%}"
                  f" · {en['yanlis_alarm']['alarm_saatte']:.1f} alarm/saat")
            karar[alan] = {"tutuyor": True, "esik": en["esik"], "avans_s": v,
                           "gorev_dongusu": en["yanlis_alarm"]["asan_oran"],
                           "yanlis_alarm_saatte": en["yanlis_alarm"]["alarm_saatte"]}
        else:
            # Neden tutmadığını AYIRT ET: avans mı yetersiz, görev
            # döngüsü mü fazla? İkisi çok farklı arızalar.
            sessiz = [s for s in sonuc[alan]
                      if s["yanlis_alarm"]["asan_oran"] <= AZAMI_GOREV_DONGUSU]
            if not sessiz:
                sebep = (f"hiçbir eşikte görev döngüsü %{AZAMI_GOREV_DONGUSU:.0%} "
                         "altına inmiyor — dedektör SÜREKLİ AÇIK")
                v = None
            else:
                en_iyi = max(
                    (s for s in sessiz
                     if s["segmentler"][0]["avans_s"] is not None),
                    key=lambda s: s["segmentler"][0]["avans_s"], default=None,
                )
                v = en_iyi["segmentler"][0]["avans_s"] if en_iyi else None
                sebep = (f"en iyi avans {v:+.1f} sn (hedef ≥2.0)" if v is not None
                         else "sessiz kalan eşiklerde olay hiç yakalanmıyor")
            print(f"  {etiket:<6} ❌ TUTMUYOR — {sebep}")
            karar[alan] = {"tutuyor": False, "en_iyi_avans_s": v, "sebep": sebep}

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kriter": "K8 — erken uyarı avansı",
        "hedef_avans_s": 2.0,
        "azami_gorev_dongusu": AZAMI_GOREV_DONGUSU,
        "gorev_dongusu_gerekcesi": (
            "Ayrık alarm sayısı sürekli açık bir dedektörü GİZLİYOR: skor hiç "
            "düşmezse 0→1 geçişi olmaz ve sayaç 'az alarm' der. İlk sürüm bu "
            "yüzden eşik 0.05'te '+56.9 sn avans' raporladı — oysa dedektör "
            "videonun %99'unda açıktı."
        ),
        "kamera": args.kamera,
        "veri_seti": yg.get("kaynak"),
        "etiket_turu": yg.get("etiket_turu"),
        "ornekleme_fps": args.fps,
        "pencere_s": PENCERE_S,
        "sure_s": sure,
        "segmentler": [{"bas": b, "bit": e} for b, e in segmentler],
        "olay_oncesi_baglam_s": segmentler[0][0],
        "sonuc": sonuc,
        "gecerlilik": ayirt,
        "asgari_ayirt_orani": ASGARI_AYIRT_ORANI,
        "tirmanma_penceresi_s": tirmanma_s,
        "karar": karar,
        "not": (
            "⚠ Avans YALNIZCA segment 1 için anlamlı: öncesinde 58 sn kavgasız "
            "bağlam var. Segment 2 ve 3'ten önce skor bir önceki olaydan zaten "
            "yükselmiş olabilir; oradan avans hesaplamak kendi kuyruğunu ölçmek olur."
        ),
        "seri": [{k: round(v, 4) for k, v in s.items()} for s in seri],
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"k8_video_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
