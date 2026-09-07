"""K6 — anomali tespiti ROC-AUC ölçümü (PLAN §1.4, hedef ≥0.75).

Neden bu betik
--------------
K6 bugüne kadar **hiç ölçülmedi.** Oysa PLAN'ın kendi sözü şu:

> *"Hedefi tutturamamak başarısızlık değildir; ÖLÇMEMEK
> başarısızlıktır."*

Ölçüm için gereken iki şey de elimizde:
  · **yer gerçeği** — CUHK Avenue test bölümü, kare seviyesinde piksel
    maskesi (39 anomali segmenti, `data/annotations/cam-19.truth.json`)
  · **sürekli skor** — füzyon katmanının risk skoru
    (`analytics/fusion.py`)

⚠ NEDEN FÜZYON SKORU, KATMAN A SKORU DEĞİL
Katman A tek başına bir sapma sinyali; K6 "sistem anomaliyi ayırt
edebiliyor mu" diye soruyor ve sistemin cevabı füzyondur. Katman A'yı
tek başına ölçmek, sistemin bir parçasını sistem sanmak olurdu.

Yine de **her iki skor da** raporlanıyor: füzyonun tek tek
bileşenlerinden daha iyi olup olmadığı, füzyonun kendisini haklı
çıkaran ya da çürüten sayıdır. Bileşeninden kötü bir füzyon,
karmaşıklığı boşuna eklemiş demektir.

⚠⚠ 03.09.2026 — BU KARŞILAŞTIRMA ELMAYLA ARMUTTU (P-41)
--------------------------------------------------------
İlk ölçüm şu sonucu verdi ve rapora "füzyon kendini haklı çıkardı"
diye yazılmak üzereydi:

    katman_a  0.789
    füzyon    0.867   ⬅ "demek ki birleştirme kazandırıyor"

**Bu çıkarım desteklenmiyordu.** Karşılaştırılan iki sayı aynı
işlemden geçmemişti:

    katman_a  = HAM, kare başına anomali skoru
    füzyon    = EMA(α=0.4) ile ZAMANSAL YUMUŞATILMIŞ ağırlıklı toplam

Yani füzyona iki şey birden eklenmişti — sinyal birleştirme VE
zamansal yumuşatma — ve ölçüm ikisini ayırmıyordu.

Elde olan sayılar ikinciyi işaret ediyordu:

  · saldırganlık AUC 0.465 (şans altı), kural AUC 0.4996 (tam şans).
    Şans seviyesindeki iki sinyali eklemek AUC'yi yükseltemez.
  · katman_a karelerinin **%42'si tam 0.0**. `_roc_auc` eşitlikleri
    0.5 sayıyor (doğru davranış) ve bu kadar çok eşitlik AUC'ye
    TAVAN koyuyor. EMA geçmişten sızdırıp o sıfırları dolduruyor →
    eşitlik azalıyor → AUC mekanik olarak yükseliyor.

Bu yüzden beşinci bir seri eklendi: **`katman_a_ema`** — katman A'nın
tek başına, füzyonla AYNI EMA'dan geçmiş hâli. Doğru soru artık
sorulabiliyor:

    füzyon > katman_a_ema  → birleştirme gerçekten kazandırıyor
    füzyon ≈ katman_a_ema  → kazanan YUMUŞATMA; füzyon katmanı bu
                             veri setinde karşılığını vermiyor

⚠ İki sonuç da rapor için değerli. Kötü olan tek şey, hangisi
olduğunu bilmeden birini iddia etmekti. Bu, aynı sınıf hatanın
DÖRDÜNCÜSÜ olurdu (P-17 sıralı koşu · P-36 bozuk blok · P-39
koordinat uzayı): ölçüm aracına, ölçtüğü şeye gösterilen şüpheyi
göstermemek.

⚠ NEDEN ROC-AUC, DOĞRULUK DEĞİL
Avenue'da anomali kareleri azınlıkta. "Hiçbir şey anomali değil"
diyen bir sistem yüksek doğruluk alır ve hiçbir işe yaramaz. AUC
eşikten bağımsız: "rastgele bir anomali karesi, rastgele bir normal
kareden yüksek skor alma olasılığı".

Ne yapar
--------
Avenue test kliplerini canlı boru hattının aynısından geçirir:

    kare → YOLO26 tespit → BoT-SORT → poz → özellikler
         → Katman A + Katman B + saldırganlık → FÜZYON

Her kare için o karedeki izlerin **azami** risk skorunu alır (bir
karede birinin riskli olması o kareyi riskli yapar), yer gerçeğiyle
karşılaştırır.

⚠ NEDEN AZAMİ, ORTALAMA DEĞİL
Kalabalık bir karede tek bir kişi anormal davranıyorsa, ortalama onu
kalabalığın içinde söndürürdü. Anomali tanımı gereği azınlıktadır.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI olmalı — GPU paylaşılmamalı.

Kullanım
--------
    uv run python scripts/evaluate_k6.py
    uv run python scripts/evaluate_k6.py --klip 6 --fps 4
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
AVENUE = PROJECT_ROOT / "data" / "archive" / "Avenue_Dataset" / "Avenue Dataset"
TRUTH = PROJECT_ROOT / "data" / "annotations" / "cam-19.truth.json"


def _roc_auc(pozitif: list[float], negatif: list[float]) -> float:
    """Mann-Whitney U ile ROC eğrisi altındaki alan.

    ⚠ Eşitlikler 0.5 sayılıyor. Skorların çoğu tam 0.0 olduğunda
    (hiçbir sinyal yok) bu fark yaratıyor: eşitliği 1 saymak AUC'yi
    yapay olarak yükseltirdi.
    """
    if not pozitif or not negatif:
        return float("nan")
    n = sorted(negatif)
    toplam = 0.0
    for p in pozitif:
        # Kaç negatif p'den küçük / eşit — ikili arama ile
        import bisect

        kucuk = bisect.bisect_left(n, p)
        esit = bisect.bisect_right(n, p) - kucuk
        toplam += kucuk + 0.5 * esit
    return toplam / (len(pozitif) * len(negatif))


def _segment_haritasi() -> dict[str, list[tuple[float, float]]]:
    """Klip adı → anomali aralıkları."""
    d = json.loads(TRUTH.read_text(encoding="utf-8"))
    harita: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for s in d["segments"]:
        harita[str(s["clip"])].append((float(s["start_s"]), float(s["end_s"])))
    return harita


def _anomali_mi(araliklar: list[tuple[float, float]], t: float) -> bool:
    return any(bas <= t <= bit for bas, bit in araliklar)


def _klip_skorla(
    yol: Path,
    *,
    dedektor: Any,
    poz: Any,
    ornek_fps: float,
    imgsz: int,
    kamera: str = "avenue",
    sadece_ogren: bool = False,
) -> list[tuple[float, float, float, float, float, float]]:
    """Bir klibi boru hattından geçirir.

    Dönen: her örneklenen kare için
    `(zaman, füzyon_riski, katman_a, saldırganlık, kural, katman_a_ema)`.

    ⚠ Bileşenler de dönüyor: füzyonun bileşenlerinden daha iyi olup
    olmadığını görmeden füzyonu savunmak mümkün değil.

    ⚠ `katman_a_ema` — ADİL KARŞILAŞTIRMANIN KENDİSİ (P-41)
    Katman A'nın füzyonla aynı zamansal yumuşatmadan geçmiş hâli.
    Bu sütun olmadan "füzyon 0.867 > katman_a 0.789" cümlesi,
    birleştirmenin mi yumuşatmanın mı kazandırdığını söylemiyor.

    ⚠ `sadece_ogren=True` — ISITMA İÇİN HIZLI YOL
    Isıtma aşamasında yalnızca profil besleniyor; çift özellikleri,
    tırmanma skoru, kural motoru ve füzyon HESAPLANMIYOR.

    Ölçüldü: ilk sürüm ısıtmayı tam boru hattıyla yapıyordu ve
    15 328 kare **47 dakika** sürdü (kare başına ~184 ms — canlı
    hattın ~25 ms'inin 7 katı). Sebep, canlı hatta kamera başına
    ~3 FPS koşan O(n²) çift özelliklerinin burada 25 FPS'te
    koşması.

    Profilin öğrendiği şey yalnızca konum, hız ve durağanlık. Bunlar
    için tespit + takip + poz yeterli; gerisi ısıtmada boşuna iş.
    """
    import cv2

    from sentinel.analytics import fusion
    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.anomaly.normalcy import KameraNormali
    from sentinel.analytics.anomaly.rules import KuralMotoru
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    adim = max(1, round(kaynak_fps / ornek_fps))

    takipci = BotSortTracker(frame_rate=int(ornek_fps))
    depo = PencereDeposu()
    kurallar = KuralMotoru()
    tirmanma = TirmanmaSkorlayici()
    fuzyon = fusion.RiskFuzyonu()
    # ⚠ HER KLİP İÇİN TAZE PROFİL DEĞİL — Avenue'nun tüm test klipleri
    # AYNI sahne. Profili klip başına sıfırlamak, kameranın normalini
    # her seferinde yeniden öğrenmek olurdu ve ilk saniyeler hep
    # "anomali" çıkardı. Profil dışarıdan veriliyor.
    # ⚠ Profil KLİP başına değil KAMERA başına. Avenue'nun tüm
    # klipleri aynı sahne ve "her kameranın normali ayrı öğrenilir"
    # ilkesi kamera düzeyinde tanımlı (mimari kural 7). Klip başına
    # sıfırlamak, her klibin ilk saniyelerini yapay anomali yapardı.
    profil = _PROFIL.setdefault(kamera, KameraNormali(camera=kamera))

    cikti: list[tuple[float, float, float, float, float, float]] = []
    kare_no = 0
    onceki_ts = 0.0
    # ⚠ Katman A'nın KENDİ EMA'sı — füzyonunkiyle aynı α, aynı başlangıç.
    # Kare seviyesinde tutuluyor (iz seviyesinde değil) çünkü
    # karşılaştırılan şey de kare seviyesindeki azami skor.
    # Füzyon EMA'yı iz başına uyguluyor; bu fark raporda yazılacak
    # ama yönü BU SERİNİN LEHİNE değil: iz başına yumuşatma daha
    # keskin bir sinyal verir, yani bu seri füzyonu haksız yere
    # aşağı çekmiyor.
    a_ema = 0.0
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps
        dt = max(0.0, min(5.0, ts - onceki_ts))
        onceki_ts = ts

        tespitler = dedektor.detect([hazir])[0]
        izler = takipci.update(kamera, tespitler, ts)

        risk_azami = a_azami = s_azami = k_azami = 0.0
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                d = iz.detection
                bbox = (d.x1, d.y1, d.x2, d.y2)
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera,
                    iz.track_id,
                    Ornek(
                        ts=ts, bbox=bbox, kp=kp,
                        olcek=sk.govde_boyu(kp, bbox) if kp is not None else None,
                        ayak=sk.ayak_noktasi(bbox),
                    ),
                )
            kisiler = [cikar(depo.al(kamera, t.track_id)) for t in izler]  # type: ignore[arg-type]
            tirmanma_map: dict[int, float] = {}
            kural_map: dict[int, float] = {}
            if not sadece_ogren:
                ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(kamera))
                skorlar = tirmanma.degerlendir(kamera, kisiler, ciftler, ts)
                bulgular = kurallar.degerlendir(kamera, kisiler, ts, dt)
                tirmanma_map = {s.track_id: s.skor for s in skorlar}
                for b in bulgular:
                    if b.track_id is not None and b.track_id >= 0:
                        kural_map[b.track_id] = max(
                            kural_map.get(b.track_id, 0.0), b.skor
                        )

            kare_h, kare_w = kare.shape[:2]
            for iz, ozellik in zip(izler, kisiler, strict=False):
                # ⚠ Isıtmadaki ile AYNI koordinat uzayı — kaynak kare.
                # İkisi ayrışırsa profil, öğrendiğinden başka bir yerle
                # karşılaştırılır.
                bbox = _lb.to_source_box(
                    iz.detection.x1, iz.detection.y1,
                    iz.detection.x2, iz.detection.y2,
                )
                ayak_x = (bbox[0] + bbox[2]) / 2.0
                # ⚠ Isıtmada SKORLAMA da atlanıyor: profil henüz hazır
                # değil, dönecek değer zaten 0.0 olurdu.
                # Isıtmadaki ile AYNI yön hesabı — ikisi ayrışırsa
                # profil öğrendiğinden başka bir şeyle karşılaştırılır.
                yon = None
                if abs(iz.velocity_x) > 1.0 or abs(iz.velocity_y) > 1.0:
                    yon = math.atan2(iz.velocity_y, iz.velocity_x)

                anomali_skor = 0.0
                if not sadece_ogren:
                    anomali_skor, _kanit = profil.skorla(
                        ayak_x, bbox[3], float(kare_w), float(kare_h),
                        ozellik.govde_hizi, yon,
                    )
                profil.ogren(
                    ayak_x, bbox[3], float(kare_w), float(kare_h),
                    ozellik.govde_hizi, yon,
                    duragan=ozellik.oyalanma_s > 0.0,
                )
                if not sadece_ogren:
                    sinyaller = fusion.Sinyaller(
                        saldirganlik=tirmanma_map.get(iz.track_id, 0.0),
                        anomali=anomali_skor,
                        kural=kural_map.get(iz.track_id, 0.0),
                    )
                    sonuc = fuzyon.degerlendir(
                        kamera, iz.track_id, sinyaller, ozellik.tamlik, ts
                    )
                    if sonuc is not None:
                        risk_azami = max(risk_azami, sonuc.risk)
                a_azami = max(a_azami, anomali_skor)
                s_azami = max(s_azami, tirmanma_map.get(iz.track_id, 0.0))
                k_azami = max(k_azami, kural_map.get(iz.track_id, 0.0))
            profil.kare_ogren(len(izler))

        # Füzyonla AYNI yumuşatma katsayısı — tek fark, girdide
        # yalnızca Katman A'nın olması.
        a_ema = fusion.EMA_ALFA * a_azami + (1 - fusion.EMA_ALFA) * a_ema
        cikti.append((ts, risk_azami, a_azami, s_azami, k_azami, a_ema))
        kare_no += 1

    cap.release()
    return cikti


def _profili_isit(
    yol: Path,
    *,
    dedektor: Any,
    poz: Any,
    ornek_fps: float,
    imgsz: int,
    kamera: str = "avenue",
) -> int:
    """Profili besler — YALIN yol, özellik makinesi kurulmadan.

    ⚠ NEDEN AYRI BİR FONKSİYON
    İlk sürüm ısıtmayı tam boru hattıyla (`_klip_skorla`) yapıyordu ve
    15 328 kare **56 dakikada bitmedi** — kare başına ~184 ms, canlı
    hattın ~25 ms'inin 7 katı.

    Sebep ölçek değişiminde: `PencereDeposu` 3 saniyelik pencere
    tutuyor. Canlı hat kamera başına ~3 FPS koşuyor, yani pencerede
    ~12 örnek var. Isıtma 25 FPS'te koşunca pencere **75 örneğe**
    çıktı ve `cikar()` her karede o pencerenin tamamını dolaşıyor
    (`_tum_keypoint_hizlari`: 17 eklem × 74 çift).

    Sonuç: 6× büyük pencere × 6× sık çağrı = **36× maliyet.**

    ⚠ Bu, "örnekleme hızını artırmak maliyeti doğrusal artırır"
    varsayımının çürüdüğü yer. Pencere tabanlı bir sistemde hız
    artışı KAREsel etki yapıyor.

    Profilin öğrendiği şey yalnızca `(ayak noktası, hız, durağanlık)`.
    Bunun için pencereye gerek yok — ama ARDIŞIK İKİ KARE DE YETMİYOR.

    ⚠ İLK SÜRÜM HIZI ARDIŞIK KAREDEN HESAPLIYORDU VE YANLIŞTI
    Tanı betiği (`scripts/diagnose_katman_a.py`) ortaya çıkardı:

        öğrenilen hız p50 : 1.645 gövde/sn   (canlı ölçüm: 0.30)
        hücre sapması p50 : 4.734 gövde/sn   (fiziksel olarak saçma)

    Bir insan hızını saniyede 4.7 gövde boyu değiştiremez. O sayı
    hareket değil GÜRÜLTÜ.

    Sebep ölçek: 25 FPS'te iki kare arası 0.04 sn. Yürüyen bir insan o
    sürede ~3 piksel yer değiştiriyor; takipçinin konum gürültüsü ise
    5-20 piksel. **Gürültü sinyalden büyük.**

    ⚠ Bu, "daha yüksek kare hızı = daha iyi ölçüm" sezgisinin
    çürüdüğü yer: yer değiştirme `dt` ile küçülüyor, gürültü
    küçülmüyor. Kare hızını artırmak hız ölçümünü İYİLEŞTİRMİYOR,
    bozuyor.

    Canlı boru hattı bunu zaten doğru yapıyor (`person.py`): ardışık
    fark yerine pencere üzerinden **medyan**. Burada da aynı ilke
    uygulanıyor — hız sabit bir zaman TABANI üzerinden ölçülüyor.
    """
    import cv2

    from sentinel.analytics.anomaly.normalcy import KameraNormali
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    adim = max(1, round(kaynak_fps / ornek_fps))
    takipci = BotSortTracker(frame_rate=int(max(1, ornek_fps)))
    profil = _PROFIL.setdefault(kamera, KameraNormali(camera=kamera))

    # ⚠ HIZ TABANI — ardışık kare DEĞİL, sabit bir zaman aralığı.
    # Canlı hattın kamera başına ~3 FPS'ine karşılık gelen aralık;
    # bu süre içinde yürüyen bir insan ~50 piksel yol alıyor ve
    # takip gürültüsü (5-20 px) artık baskın değil.
    hiz_tabani_s = 0.3

    # iz kimliği → (zaman, ayak_x, ayak_y, gövde_yüksekliği)
    onceki: dict[int, tuple[float, float, float, float]] = {}
    eklenen = 0
    kare_no = 0
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        hazir, lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps
        kare_h, kare_w = kare.shape[:2]

        izler = takipci.update(kamera, dedektor.detect([hazir])[0], ts)
        profil.kare_ogren(len(izler))
        for iz in izler:
            d = iz.detection
            # ⚠ KOORDİNAT UZAYI — sessiz ama ölümcül bir hataydı
            # Tespitler MODEL uzayında (640×640 letterbox), profil ise
            # ızgarayı KAYNAK kare boyutlarıyla (640×360) hesaplıyordu.
            # Yani her konum yanlış hücreye düşüyordu: dolgu bandı
            # yüzünden y ekseni 140 piksel kaymış, alt hücreler
            # tümüyle kadraj dışına taşmıştı.
            #
            # Canlı boru hattı bunu doğru yapıyor (`to_source_box` ile
            # geri eşleme); ölçüm betiğinde o adım atlanmıştı.
            sx1, sy1, sx2, sy2 = lb.to_source_box(d.x1, d.y1, d.x2, d.y2)
            ayak_x = (sx1 + sx2) / 2.0
            ayak_y = sy2
            # ⚠ Gövde boyu kutu yüksekliğinden. Poz iskeletinden daha
            # kaba ama ısıtma için yeterli — ve poz çağrısını tamamen
            # elemek ısıtmayı bir kat daha hızlandırıyor.
            boy = max(sy2 - sy1, 1.0)

            hiz = None
            duragan = False
            gecmis = onceki.get(iz.track_id)
            if gecmis is not None:
                dt = ts - gecmis[0]
                # ⚠ Taban dolmadıysa referans GÜNCELLENMİYOR — bir
                # sonraki karede aynı referansa göre daha uzun bir
                # aralık ölçülecek. Her karede referansı güncellemek,
                # tam da düzeltmeye çalıştığımız ardışık-kare hatasını
                # geri getirirdi.
                if dt >= hiz_tabani_s:
                    if dt <= 1.5:
                        mesafe = (
                            (ayak_x - gecmis[1]) ** 2 + (ayak_y - gecmis[2]) ** 2
                        ) ** 0.5
                        olcek = max(gecmis[3], 1.0)
                        hiz = mesafe / dt / olcek
                        # `person.py` ile aynı ölçüt: pencere boyunca
                        # yarım gövde boyundan az yer değiştirme.
                        duragan = (mesafe / olcek) < 0.5
                    onceki[iz.track_id] = (ts, ayak_x, ayak_y, boy)
            else:
                onceki[iz.track_id] = (ts, ayak_x, ayak_y, boy)

            # ⚠ YÖN — Katman A'nın üçüncü kolu, ilk sürümde ÖLÜYDÜ
            # `yon=None` geçiliyordu, yani "ters yön" testi hiç
            # çalışmıyordu. Avenue'nun anomali türlerinden biri tam
            # olarak ters yön; o kolu kapalı bırakmak, ölçülen şeyin
            # bir parçasını görmezden gelmekti.
            #
            # Takipçi hız vektörü veriyor (ayak noktasından). Çok küçük
            # hızda yön anlamsız — duran bir kişinin "yönü" gürültüdür.
            yon = None
            if abs(iz.velocity_x) > 1.0 or abs(iz.velocity_y) > 1.0:
                yon = math.atan2(iz.velocity_y, iz.velocity_x)

            profil.ogren(
                ayak_x, ayak_y, float(kare_w), float(kare_h), hiz, yon,
                duragan=duragan,
            )
            eklenen += 1
        kare_no += 1

    cap.release()
    return eklenen


# Klip başına değil KAMERA başına profil: Avenue'nun tüm klipleri aynı
# sahne, ve "her kameranın normali ayrı öğrenilir" ilkesi kamera
# düzeyinde tanımlı (mimari kural 7).
_PROFIL: dict[str, Any] = {}


def main() -> int:
    ap = argparse.ArgumentParser(description="K6 — anomali ROC-AUC")
    ap.add_argument("--klip", type=int, default=99, help="kaç test klibi (yer gerçeği olanlardan)")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument(
        "--isinma-fps",
        type=float,
        default=25.0,
        help="profil ısıtmasında örnekleme hızı. ⚠ ANALİZ hızından "
             "yüksek olması KASITLI — gerekçe kodda.",
    )
    ap.add_argument(
        "--isinma-klip",
        type=int,
        default=16,
        help="profili ısıtmak için kaç EĞİTİM klibi (0 = ısıtma yok). "
             "⚠ Profil 2000 gözlem görmeden hiçbir skor üretmiyor; "
             "6 klip 1368'de kaldı, hepsini kullanmak gerekiyor.",
    )
    args = ap.parse_args()

    videolar_dizini = AVENUE / "testing_videos"
    if not videolar_dizini.is_dir():
        print(f"Avenue test videoları yok: {videolar_dizini}", file=sys.stderr)
        return 1
    if not TRUTH.is_file():
        print(f"Yer gerçeği yok: {TRUTH}", file=sys.stderr)
        return 1

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    harita = _segment_haritasi()

    # ⚠ YALNIZCA YER GERÇEĞİ OLAN KLİPLER
    #
    # İlk ölçümde tüm test klipleri kullanıldı ve `10.avi` "0 anomali
    # segmenti" diye işlendi. Ama Avenue'nun TEST bölümündeki her klip
    # tanımı gereği anomali içerir — bizim yer gerçeği dosyamız yalnızca
    # 01-09'u kapsıyor (`build_avenue` o kadarını üretmiş).
    #
    # Yer gerçeği olmayan bir klibi ölçüme katmak, içindeki GERÇEK
    # anomalileri "normal" diye etiketlemek demek: sistem onları doğru
    # bulduğunda ceza alır. Ölçüm, ölçtüğü şeyi cezalandırır hâle gelir.
    #
    # Kapsam dışı bırakmak bir kayıp değil dürüstlüktür: "9 klipte
    # ölçtük" demek, "21 klipte ölçtük ama 12'sinin etiketi yoktu"
    # demekten iyidir.
    tumu = sorted(videolar_dizini.glob("*.avi"))
    klipler = [y for y in tumu if y.name in harita][: args.klip]
    atlanan = [y.name for y in tumu if y.name not in harita]
    if not klipler:
        print("yer gerçeği olan test klibi bulunamadı", file=sys.stderr)
        return 1
    if atlanan:
        print(
            f"⚠ {len(atlanan)} klip ÖLÇÜM DIŞI (yer gerçeği yok): "
            f"{', '.join(atlanan[:5])}{'…' if len(atlanan) > 5 else ''}"
        )
    print(f"{len(klipler)} klip · örnekleme {args.fps} FPS · yer gerçeği: {TRUTH.name}")

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "backend" / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    # ─── PROFİL ISITMA — metodolojik olarak zorunlu ───
    #
    # ⚠ İLK ÖLÇÜM BUNSUZ YAPILDI VE KATMAN A HİÇ SKOR ÜRETMEDİ
    # `PROFIL_ASGARI_ORNEK = 2000`: profil bu kadar gözlem görmeden
    # hiçbir şeyi olağandışı saymıyor (soğuk başlangıçta her şey
    # "hiç görülmemiş" olur diye konmuş bir koruma). 2 test klibinde
    # o eşiğe ulaşılmadı; `katman_a` skorlarının %100'ü sıfır çıktı ve
    # AUC tam 0.500 (yani ölçüm hiçbir şey ölçmedi).
    #
    # ⚠ AMA ASIL MESELE EŞİK DEĞİL, DENEY TASARIMI
    # Modülün tanımı "önce normali öğren, sonra sapmayı bul". Profili
    # test verisiyle ısıtmak iki hata birden olurdu:
    #   · test verisinde öğrenmek (anomaliyi de normal öğrenir)
    #   · ilk kareler profilsiz kalır ve ölçümü aşağı çeker
    #
    # Avenue'nun EĞİTİM bölümü tam bu iş için var: tanımı gereği
    # yalnızca normal davranış. Sistem sahada da böyle kurulur —
    # temiz bir dönem izlenir, sonra izlemeye geçilir.
    #
    # ⚠ ISITMA ANALİZDEN HIZLI ÖRNEKLENİYOR — ve bu kasıtlı
    # İkinci ölçümde profil "hazır" oldu (2314 gözlem) ama Katman A
    # yine neredeyse sustu: skorların yalnızca %5.3'ü sıfırdan farklı.
    # Aritmetik açık:
    #
    #     2314 gözlem ÷ 576 hücre (32×18) = hücre başına 4 örnek
    #     HUCRE_ASGARI_ORNEK = 30
    #
    # Yani hiçbir hücre hız/yön istatistiği yapacak kadar veri
    # görmemiş; profil "hazır" ama içi boş.
    #
    # Çözüm eşiği düşürmek DEĞİL — 4 örnekten çıkan bir sapma ölçüsü
    # zaten gürültü olurdu. Çözüm daha çok veri, ve o veri elimizde:
    # analiz 4 FPS'te yapılıyor çünkü GPU bütçesi öyle gerektiriyor,
    # ama PROFİL yalnızca konum ve hız öğreniyor ve bunlar her karede
    # zaten mevcut.
    #
    # ⚠ Gerçek bir kurulumda bu ayrım daha da belirgin: profil
    # GÜNLERCE öğrenir, analiz saniyede birkaç kare yapar. Öğrenme
    # hızını analiz hızına eşitlemek, sistemin sahadaki davranışını
    # değil ölçüm betiğinin kısıtını modellemek olurdu.
    if args.isinma_klip > 0:
        egitim = sorted((AVENUE / "training_videos").glob("*.avi"))[: args.isinma_klip]
        print(
            f"profil ısıtılıyor: {len(egitim)} eğitim klibi (tümü normal) · "
            f"{args.isinma_fps:.0f} FPS örnekleme"
        )
        for i, yol in enumerate(egitim, 1):
            _profili_isit(
                yol, dedektor=dedektor, poz=poz,
                ornek_fps=args.isinma_fps, imgsz=args.imgsz,
                kamera="avenue",
            )
            print(f"\r  {i}/{len(egitim)}", end="", flush=True)
        profil = _PROFIL.get("avenue")
        ornek = getattr(profil, "toplam_ornek", 0)
        hazir = getattr(profil, "hazir", False)
        print(f"\n  profil: {ornek} gözlem · hazır={hazir}")
        if not hazir:
            print(
                "  ⚠ PROFİL HÂLÂ HAZIR DEĞİL — Katman A yine sıfır üretecek.\n"
                "    --isinma-klip değerini artırın.",
                file=sys.stderr,
            )

    # skor adı → (anomali kareleri, normal kareler)
    seriler: dict[str, tuple[list[float], list[float]]] = {
        ad: ([], [])
        for ad in ("fuzyon", "katman_a", "katman_a_ema", "saldirganlik", "kural")
    }
    t0 = time.time()
    kapsanan = 0
    for i, yol in enumerate(klipler, 1):
        araliklar = harita.get(yol.name, [])
        kareler = _klip_skorla(
            yol, dedektor=dedektor, poz=poz, ornek_fps=args.fps,
            imgsz=args.imgsz, kamera="avenue",
        )
        for ts, risk, a, s, k, a_ema in kareler:
            hedef = 0 if _anomali_mi(araliklar, ts) else 1
            kapsanan += 1 - hedef
            for ad, deger in (
                ("fuzyon", risk), ("katman_a", a), ("katman_a_ema", a_ema),
                ("saldirganlik", s), ("kural", k),
            ):
                seriler[ad][hedef].append(deger)
        print(
            f"\r  {i}/{len(klipler)} {yol.name} · {len(kareler)} kare · "
            f"{len(araliklar)} anomali segmenti",
            end="", flush=True,
        )
    print()

    sure = time.time() - t0
    poz_n = len(seriler["fuzyon"][0])
    neg_n = len(seriler["fuzyon"][1])
    print(
        f"\n{poz_n + neg_n} kare · {poz_n} anomali ({poz_n / (poz_n + neg_n):.1%}) · "
        f"{neg_n} normal · {sure:.0f} sn"
    )

    if poz_n == 0:
        print(
            "\n⚠ HİÇ ANOMALİ KARESİ YOK — ölçüm yapılamaz.\n"
            "  Yer gerçeği zaman damgaları klip zamanıyla eşleşmiyor olabilir.",
            file=sys.stderr,
        )
        return 1

    print(f"\n{'SKOR':<14} {'AUC':>7} {'anomali p50':>12} {'normal p50':>11} {'anomali p90':>12}")
    ozet: dict[str, Any] = {}
    for ad, (poz, neg) in seriler.items():
        auc = _roc_auc(poz, neg)
        p_med = statistics.median(poz) if poz else 0.0
        n_med = statistics.median(neg) if neg else 0.0
        p90 = sorted(poz)[int(len(poz) * 0.9)] if poz else 0.0
        ozet[ad] = {
            "auc": round(auc, 4),
            "anomali_p50": round(p_med, 4),
            "normal_p50": round(n_med, 4),
            "anomali_p90": round(p90, 4),
            "sifir_olmayan_oran": round(
                sum(1 for v in poz + neg if v > 0) / max(len(poz) + len(neg), 1), 4
            ),
        }
        print(f"{ad:<14} {auc:>7.3f} {p_med:>12.3f} {n_med:>11.3f} {p90:>12.3f}")

    fuzyon_auc = ozet["fuzyon"]["auc"]
    # ⚠ EMA'lı seri "tek bileşen" yarışmasına GİRMİYOR: o bir bileşen
    # değil, bir KONTROL GRUBU. Karşılaştırması ayrıca yapılıyor.
    en_iyi_bilesen = max(
        (ad for ad in seriler if ad not in ("fuzyon", "katman_a_ema")),
        key=lambda a: ozet[a]["auc"],
    )
    print(f"\nK6 HEDEFİ: AUC ≥ 0.75 · ölçülen (füzyon): {fuzyon_auc:.3f}")
    print("  " + ("✅ TUTUYOR" if fuzyon_auc >= 0.75 else "❌ TUTMUYOR"))
    print(
        f"\n(1) FÜZYON HAM BİLEŞENLERİNDEN İYİ Mİ?\n"
        f"  en iyi ham bileşen: {en_iyi_bilesen} = {ozet[en_iyi_bilesen]['auc']:.3f}\n"
        f"  füzyon            : {fuzyon_auc:.3f}"
    )

    # ─── ASIL SORU (P-41) ───
    ema_auc = ozet["katman_a_ema"]["auc"]
    fark = fuzyon_auc - ema_auc
    print(
        f"\n(2) ⭐ PEKİ KAZANDIRAN BİRLEŞTİRME Mİ, YUMUŞATMA MI?\n"
        f"  katman_a (ham)          : {ozet['katman_a']['auc']:.3f}\n"
        f"  katman_a + EMA (kontrol): {ema_auc:.3f}   ⬅ tek sinyal, füzyonla aynı yumuşatma\n"
        f"  füzyon (5 sinyal + EMA) : {fuzyon_auc:.3f}\n"
        f"  fark (füzyon − kontrol) : {fark:+.3f}"
    )
    # ⚠ Eşik 0.02 KEYFİ ve öyle olduğu yazılıyor. 9 klip / 69 anomali
    # karesiyle AUC'nin belirsizliği bu mertebede; daha küçük bir farkı
    # "kazanç" saymak, gürültüyü bulgu ilan etmek olurdu. Gerçek bir
    # güven aralığı bootstrap ister ve bu örneklem için abartı olurdu —
    # ama eşiğin nereden geldiği raporda böyle yazılacak.
    if fark > 0.02:
        print("  → BİRLEŞTİRME kazandırıyor: füzyon, yumuşatılmış tek sinyali AŞIYOR")
    elif fark < -0.02:
        print("  → ⚠ FÜZYON ZARAR VERİYOR: tek sinyal + yumuşatma DAHA İYİ")
    else:
        print(
            "  → ⚠ KAZANDIRAN YUMUŞATMA: füzyonun ham bileşene üstünlüğü\n"
            "     büyük ölçüde EMA'dan geliyor, sinyal birleştirmeden değil.\n"
            "     Bu veri setinde füzyon katmanı karşılığını VERMİYOR —\n"
            "     ve bu, gizlenecek değil raporlanacak bir bulgudur."
        )

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kriter": "K6",
        "hedef_auc": 0.75,
        "veri_seti": "CUHK Avenue (testing)",
        "klip_sayisi": len(klipler),
        "ornekleme_fps": args.fps,
        "isinma_fps": args.isinma_fps,
        "isinma_klip": args.isinma_klip,
        "profil_gozlem": getattr(_PROFIL.get("avenue"), "toplam_ornek", 0),
        "kare_toplam": poz_n + neg_n,
        "kare_anomali": poz_n,
        "kare_normal": neg_n,
        "sure_s": round(sure, 1),
        "sonuc": ozet,
        "k6_tutuyor": bool(fuzyon_auc >= 0.75),
        # ⚠ FÜZYONUN KENDİ SINAVI (P-41) — sayı JSON'a da giriyor ki
        # rapor bu karşılaştırmayı yeniden koşmadan alıntılayabilsin.
        "fuzyon_sinavi": {
            "soru": "kazandıran sinyal birleştirme mi, zamansal yumuşatma mı",
            "katman_a_ham": ozet["katman_a"]["auc"],
            "katman_a_ema_kontrol": ema_auc,
            "fuzyon": fuzyon_auc,
            "fark": round(fark, 4),
            "anlamlilik_esigi": 0.02,
            "esik_gerekcesi": (
                "9 klip / 69 anomali karesinde AUC belirsizliği bu mertebede; "
                "daha küçük farkı kazanç saymak gürültüyü bulgu ilan etmek olur"
            ),
            "sonuc": (
                "birlestirme_kazandiriyor" if fark > 0.02
                else "fuzyon_zarar_veriyor" if fark < -0.02
                else "kazandiran_yumusatma"
            ),
        },
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"k6_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
