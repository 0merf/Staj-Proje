"""Kişi bazlı özellikler — PLAN.md §6.5.2.

Her takip kimliği için 3 saniyelik pencereden çıkarılan sayılar.
Bunlar hem saldırganlık modelinin (§6.5) hem anomali kurallarının
(§6.4 Katman B) girdisi.

⚠ TÜM MESAFE VE HIZ BİRİMLERİ GÖVDE BOYUNA NORMALİZE
----------------------------------------------------
Birim **gövde/saniye**, piksel/saniye DEĞİL. Kameraya 3 m uzaklıktaki
kişi ile 20 m uzaklıktaki kişi aynı hareketi yaptığında piksel hızları
10 kat farklı çıkar; ham piksel eşiğiyle yakındaki herkes "saldırgan",
uzaktaki hiç kimse olmaz (skeleton.py modül başlığı).

⚠ HER ÖZELLİK None DÖNEBİLİR
----------------------------
Keypoint görünmüyorsa uydurulmuyor (PLAN §6.2). `None`, hesaplamanın
başarısızlığı değil **"bu bilgi yok"** demek. Füzyon katmanı eksik
özelliği sıfır sanmamalı: sıfır "hareket etmedi" demektir, eksik ise
"bilmiyoruz".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from sentinel.analytics.features import skeleton as sk
from sentinel.analytics.features.window import IzPenceresi


@dataclass(slots=True)
class KisiOzellikleri:
    """Bir izin 3 saniyelik penceresinden çıkan özellik vektörü."""

    track_id: int

    # ─── Hareket (birim: gövde/sn) ───
    bilek_hizi_azami: float | None = None
    bilek_sarsintisi: float | None = None
    # ⚠ p75 SÜRÜMLERİ — gürültüye dayanıklı toplulaştırma (P-47).
    # `azami` alanları KARŞILAŞTIRMA için duruyor; skorlamada
    # `aggression.py` bunları kullanıyor.
    bilek_hizi_p75: float | None = None
    bilek_sarsintisi_p75: float | None = None
    hareket_enerjisi: float | None = None
    govde_hizi: float | None = None

    # ─── Duruş ───
    kol_yuksekligi_azami: float | None = None  # 0-1
    govde_egimi: float | None = None  # derece, 0 = dik
    govde_egimi_degisimi: float | None = None  # derece/sn
    durus_genisligi: float | None = None  # gövde oranı

    # ─── Bağlam ───
    en_boy_orani: float | None = None  # düşme tespiti için
    oyalanma_s: float = 0.0

    # ─── Güvenilirlik ───
    # ⚠ Bu iki alan füzyona GİRMEK ZORUNDA (window.py · tamlik).
    tamlik: float = 0.0
    ornek_sayisi: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _p75(sirali: list[float]) -> float:
    """Sıralı bir listenin 75. yüzdeliği.

    ⚠ `statistics.quantiles` KULLANILMIYOR: o en az 2 örnek istiyor ve
    3 saniyelik pencerede tek örnek sık görülüyor (kare atma). Tek
    örnekte doğru cevap o örneğin kendisi, istisna değil.
    """
    if not sirali:
        return 0.0
    return sirali[min(len(sirali) - 1, int(len(sirali) * 0.75))]


def _bilek_hizlari(pencere: IzPenceresi, olcek: float) -> list[float]:
    """Ardışık örneklerde bileklerin normalize edilmiş hızları."""
    hizlar: list[float] = []
    for onceki, sonraki in pencere.gecerli_ciftler():
        if onceki.kp is None or sonraki.kp is None:
            continue
        dt = sonraki.ts - onceki.ts
        for indeks in sk.BILEKLER:
            a, b = sk.nokta(onceki.kp, indeks), sk.nokta(sonraki.kp, indeks)
            if a is None or b is None:
                continue
            hizlar.append(float(np.linalg.norm(b - a) / dt / olcek))
    return hizlar


def _tum_keypoint_hizlari(pencere: IzPenceresi, olcek: float) -> list[float]:
    """Tüm eklemlerin hızları — genel ajitasyonun ölçüsü."""
    hizlar: list[float] = []
    for onceki, sonraki in pencere.gecerli_ciftler():
        if onceki.kp is None or sonraki.kp is None:
            continue
        dt = sonraki.ts - onceki.ts
        n = min(len(onceki.kp), len(sonraki.kp))
        for i in range(n):
            a, b = sk.nokta(onceki.kp, i), sk.nokta(sonraki.kp, i)
            if a is None or b is None:
                continue
            hizlar.append(float(np.linalg.norm(b - a) / dt / olcek))
    return hizlar


def cikar(pencere: IzPenceresi) -> KisiOzellikleri:
    """Bir izin penceresinden özellik vektörü üretir.

    Pencere kısa olsa bile çalışır — üretilen alanlar azalır ve
    `tamlik` düşük çıkar. Bu bilinçli: ölçüm izlerin medyan ömrünün
    4 kare (1 sn) olduğunu gösterdi, "12 örnek yoksa hesaplama" kuralı
    modülü pratikte susturur (window.py modül başlığı).
    """
    ozellik = KisiOzellikleri(
        track_id=pencere.track_id,
        tamlik=pencere.tamlik,
        ornek_sayisi=pencere.sayi,
    )

    son = pencere.son
    if son is None:
        return ozellik

    # ─── Tek kareden çıkanlar (pencere kısa olsa da hesaplanır) ───
    genislik = son.bbox[2] - son.bbox[0]
    yukseklik = son.bbox[3] - son.bbox[1]
    if yukseklik > 1e-6:
        # ⚠ Düşme tespitinin ana girdisi (PLAN §6.4 Katman B):
        # ayakta duran kişide ~0.4, yere yatmış kişide > 1.0
        ozellik.en_boy_orani = float(genislik / yukseklik)

    olcek = pencere.olcek()
    if son.kp is not None:
        ozellik.govde_egimi = sk.govde_egimi(son.kp)
        sol = sk.kol_yuksekligi(son.kp, "sol")
        sag = sk.kol_yuksekligi(son.kp, "sag")
        mevcut = [v for v in (sol, sag) if v is not None]
        if mevcut:
            ozellik.kol_yuksekligi_azami = max(mevcut)
        if olcek is not None:
            ozellik.durus_genisligi = sk.durus_genisligi(son.kp, olcek)

    # ─── Zamansal olanlar (en az iki örnek gerekiyor) ───
    if not pencere.hazir:
        return ozellik

    ciftler = pencere.gecerli_ciftler()
    if not ciftler:
        # Örnek var ama aralarında büyük boşluk — hız hesaplanamaz.
        # Sistem doygunken sık görülüyor (karelerin %70'i atılıyor).
        return ozellik

    # Gövde hızı: ayak noktasından, takipçininkiyle aynı referans
    if olcek is not None and olcek > 1e-6:
        govde_hizlari = [
            float(np.linalg.norm(b.ayak - a.ayak) / (b.ts - a.ts) / olcek)
            for a, b in ciftler
        ]
        if govde_hizlari:
            ozellik.govde_hizi = float(np.median(govde_hizlari))

        bilek = _bilek_hizlari(pencere, olcek)
        if bilek:
            # ⚠⚠ 07.09.2026 — `azami` GÜRÜLTÜ ÖLÇÜYORDU (P-47)
            #
            # Buradaki gerekçe şuydu ve makul görünüyordu:
            #     "AZAMİ, ortalama değil: vuruş anlık bir olaydır ve
            #      ortalama onu 3 saniyeye yayıp söndürür."
            #
            # Mantık doğru, sonuç yanlıştı. `max` aynı zamanda en
            # gürültülü istatistik: TEK bir hatalı eklem tahmini tüm
            # pencereyi ele geçiriyor. RWF-2000'de ölçüldü
            # (`deney_toplulastirma.py`, 200 klip):
            #
            #     toplulaştırma   AUC     kavga p50   normal p50
            #     azami           0.558     2.577       2.077   ⬅ şans
            #     p90             0.659     1.625       1.003
            #     p75             0.677     0.954       0.542   ⬅ EN İYİ
            #     medyan          0.652     0.437       0.274
            #
            # ⚠ p99/p50 oranı 9.7 — dağılımın kuyruğu medyanın 10 katı.
            # Saniyede 10 gövde boyu bilek hareketi FİZİKSEL OLARAK
            # İMKÂNSIZ; o kuyruk hareket değil, eklem hatası. `max`
            # tam olarak o kuyruğu örneklemiş oluyordu.
            #
            # ⭐ p75 hem uç değeri hem gürültüyü dengeliyor: vuruş
            # pencerenin üst çeyreğinde kalıyor (sönmüyor) ama tek bir
            # bozuk eklem üst çeyreği belirleyemiyor.
            #
            # ⚠ ESKİ DEĞER SİLİNMEDİ, yanına yazıldı: makalede iki
            # toplulaştırmanın karşılaştırması raporlanacak ve eski
            # davranışı yeniden üretebilmek gerekiyor.
            sirali = sorted(bilek)
            ozellik.bilek_hizi_azami = sirali[-1]
            ozellik.bilek_hizi_p75 = _p75(sirali)
            if len(bilek) >= 2:
                # Sarsıntı: hızın değişim hızı. Kontrollü bir hareket
                # düzgün hızlanır; vuruş ani sıçrama yapar.
                # ⚠ Burada da aynı düzeltme: `max` yerine p75.
                farklar = sorted(float(v) for v in np.abs(np.diff(bilek)))
                ozellik.bilek_sarsintisi = farklar[-1]
                ozellik.bilek_sarsintisi_p75 = _p75(farklar)

        tum = _tum_keypoint_hizlari(pencere, olcek)
        if tum:
            # Karesel toplamın karekökü — birkaç eklemin çok hızlı
            # olması, hepsinin biraz hareket etmesinden daha güçlü
            # bir ajitasyon işareti (PLAN §6.5.2 `motion_energy`).
            ozellik.hareket_enerjisi = float(np.sqrt(np.mean(np.square(tum))))

    # Gövde eğiminin değişim hızı — düşme ANİ bir eğim değişimidir,
    # eğilerek bir şey almak yavaştır. İkisini ayıran şey budur.
    egimler = [
        (o.ts, sk.govde_egimi(o.kp)) for o in pencere.ornekler if o.kp is not None
    ]
    gecerli = [(t, e) for t, e in egimler if e is not None]
    if len(gecerli) >= 2:
        sure = gecerli[-1][0] - gecerli[0][0]
        if sure > 1e-6:
            ozellik.govde_egimi_degisimi = abs(gecerli[-1][1] - gecerli[0][1]) / sure

    # Oyalanma: kişi penceredeki süre boyunca ne kadar yer değiştirdi?
    # Az yer değiştirip uzun kalmak = oyalanma (PLAN §6.4 Katman B).
    if olcek is not None and olcek > 1e-6:
        ilk, sonuncu = pencere.ornekler[0], pencere.ornekler[-1]
        yer_degistirme = float(np.linalg.norm(sonuncu.ayak - ilk.ayak) / olcek)
        if yer_degistirme < 0.5:  # yarım gövde boyundan az
            ozellik.oyalanma_s = pencere.sure_s

    return ozellik


__all__ = ["KisiOzellikleri", "cikar"]
