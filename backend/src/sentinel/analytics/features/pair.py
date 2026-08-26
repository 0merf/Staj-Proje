"""Çift bazlı özellikler — PLAN.md §6.5.2.

Neden çift, neden tek kişi yetmiyor
-----------------------------------
Saldırganlık **iki kişi arasında** olur. Tek kişinin bilek hızına
bakarak "kavga var" demek yanılgıdır: koşan bir çocuk da, el sallayan
biri de, spor yapan biri de yüksek bilek hızı üretir.

Ayırt eden şey **etkileşim**:

    hızlı bilek + KİMSE YOK          → egzersiz, oyun, el sallama
    hızlı bilek + BİRİ ÇOK YAKIN     → temas ihtimali
    hızlı bilek + yakın + KARŞILIKLI → kavga örüntüsü

Bu dosya o farkı ölçen sayıları üretiyor. Kişi bazlı özellikler
(`person.py`) "ne yapıyor" der; çift bazlı özellikler "kiminle" der.

⚠ MESAFE ZEMİN DÜZLEMİNDEN ÖLÇÜLÜYOR
------------------------------------
İki kişinin yakınlığı **ayak noktaları** arasından hesaplanıyor, kutu
merkezlerinden değil. Sebep perspektif: kameraya yakın duran uzun bir
kişi ile arkasındaki kısa bir kişinin kutu merkezleri üst üste
gelebilir, oysa aralarında metrelerce mesafe vardır. Ayak noktası
zeminde olduğu için bu yanılgıyı büyük ölçüde önlüyor.

⚠ ÖLÇEK NORMALİZASYONU BURADA DA ZORUNLU
----------------------------------------
Mesafe **gövde boyuna** bölünüyor. Kameraya 3 metredeki iki kişi
arasındaki 100 piksel ile 20 metredeki 100 piksel çok farklı gerçek
mesafelere karşılık gelir. Birim: "gövde boyu" — yani `1.0` kabaca bir
insan boyu kadar uzaklık demek.

⚠ KOMBİNATORİK PATLAMA — ve neden sınırlıyoruz
----------------------------------------------
N kişi arasında N·(N−1)/2 çift var. cam-09'da 17 kişi görüldü →
136 çift. Kalabalık bir sahnede bu hızla büyür ve çoğu çift birbirinden
metrelerce uzaktır, yani hiçbir bilgi taşımaz.

Bu yüzden yalnızca **yakın çiftler** hesaplanıyor (`MAX_ILGI_MESAFE`).
Uzak çiftleri elemek Kademe 0'ın aynı mantığı: pahalı işi yapmadan
önce ucuz bir kontrolle ele.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from sentinel.analytics.features import skeleton as sk
from sentinel.analytics.features.window import IzPenceresi

# Bu mesafeden uzak çiftler hiç hesaplanmıyor (gövde boyu birimi).
# 4.0 ≈ 7 metre; iki kişi arasında temas ihtimali için fazlasıyla geniş.
# Daha dar tutmak yaklaşma AŞAMASINI kaçırırdı — tırmanma tam da
# yaklaşırken başlıyor.
MAX_ILGI_MESAFE = 4.0

# "Yakın" sayılan mesafe. Kişilerarası mesafe literatüründe (Hall)
# 1.2 metre altı "kişisel alan"; gövde boyu ~1.7 m olduğu için ~0.7.
# Bu mesafeye izinsiz girmek gerilimin ilk fiziksel işareti.
YAKIN_MESAFE = 0.7


@dataclass(slots=True)
class CiftOzellikleri:
    """İki iz arasındaki etkileşimin 3 saniyelik özeti."""

    track_a: int
    track_b: int

    # ─── Mesafe (birim: gövde boyu) ───
    mesafe: float | None = None
    en_yakin_mesafe: float | None = None
    # Negatif = YAKLAŞIYOR. Tırmanmanın en erken sinyali.
    yaklasma_hizi: float | None = None

    # ─── Yönelim ───
    # 0-1: ikisi de birbirine ne kadar dönük. 1.0 = tam karşılıklı.
    karsilikli_bakis: float | None = None

    # ─── Etkileşim ───
    yakin_kalma_s: float = 0.0
    # İki kişinin hareket enerjilerinin eşzamanlılığı (0-1).
    # Kavgada hareketler birbirine tepki verir, yani senkronize olur.
    senkron_enerji: float | None = None

    # ─── Güvenilirlik ───
    tamlik: float = 0.0
    ornek_sayisi: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _ortak_zamanlar(
    a: IzPenceresi, b: IzPenceresi, tolerans_s: float = 0.2
) -> list[tuple[float, np.ndarray, np.ndarray, float]]:
    """İki izin AYNI ANLARDAKİ örneklerini eşler.

    ⚠ NEDEN EŞLEME GEREKİYOR
    İki iz aynı kameradan gelse bile örnekleri birebir aynı anlara denk
    gelmiyor: takipçi bir kişiyi bir karede kaybedip sonrakinde
    bulabiliyor. Farklı anlardaki iki konumu karşılaştırmak, aradaki
    hareketi mesafe değişimi sanmaya yol açar.

    Tolerans örnekleme aralığının altında (4 FPS → 250 ms): aynı kareden
    gelen örnekler eşleşir, farklı karelerden gelenler eşleşmez.
    """
    cikti: list[tuple[float, np.ndarray, np.ndarray, float]] = []
    b_ornekler = list(b.ornekler)
    j = 0
    for oa in a.ornekler:
        while j < len(b_ornekler) - 1 and b_ornekler[j].ts < oa.ts - tolerans_s:
            j += 1
        if j >= len(b_ornekler):
            break
        ob = b_ornekler[j]
        if abs(ob.ts - oa.ts) > tolerans_s:
            continue
        # Ölçek: iki kişinin ortalaması. Biri eksikse diğeri kullanılır.
        olcekler = [o for o in (oa.olcek, ob.olcek) if o is not None]
        if not olcekler:
            continue
        cikti.append((oa.ts, oa.ayak, ob.ayak, float(np.mean(olcekler))))
    return cikti


def _bakis_skoru(kp_a: np.ndarray | None, kp_b: np.ndarray | None,
                 ayak_a: np.ndarray, ayak_b: np.ndarray) -> float | None:
    """İki kişinin birbirine dönüklüğü (0-1).

    Her biri için: baktığı yön ile diğerine giden yön arasındaki açı.
    İkisi de karşısındakine dönükse 1.0'a yaklaşır.

    ⚠ Omuz yönü bilinmiyorsa (sırtı dönük, omuzlar görünmüyor) None
    dönüyor — uydurulmuyor. Yanlış bir "karşılıklı bakıyor" sinyali
    doğrudan sahte kavga alarmı üretir.
    """
    if kp_a is None or kp_b is None:
        return None
    yon_a = sk.omuz_yonu(kp_a)
    yon_b = sk.omuz_yonu(kp_b)
    if yon_a is None or yon_b is None:
        return None

    ab = ayak_b - ayak_a
    mesafe = float(np.linalg.norm(ab))
    if mesafe < 1e-6:
        return None
    ab_birim = ab / mesafe

    # nokta çarpımı: 1 = tam dönük, -1 = tam ters
    a_bakiyor = float(np.dot(yon_a, ab_birim))
    b_bakiyor = float(np.dot(yon_b, -ab_birim))
    # [-1,1] → [0,1] ve ikisinin çarpımı: BİRİ bakmıyorsa skor düşer
    return float(max(0.0, a_bakiyor) * max(0.0, b_bakiyor))


def cikar(a: IzPenceresi, b: IzPenceresi) -> CiftOzellikleri | None:
    """İki izin penceresinden çift özellikleri üretir.

    `None` döner: ortak zaman yoksa, ölçek bilinmiyorsa ya da çift
    ilgi mesafesinin dışındaysa. Uzak çiftleri hesaplamamak bilinçli —
    kombinatorik patlamayı önleyen tek şey bu (modül başlığı).
    """
    ortak = _ortak_zamanlar(a, b)
    if len(ortak) < 1:
        return None

    mesafeler = [
        float(np.linalg.norm(ayak_b - ayak_a) / olcek)
        for _ts, ayak_a, ayak_b, olcek in ortak
        if olcek > 1e-6
    ]
    if not mesafeler:
        return None

    # ⚠ İLGİ KAPISI: uzak çift hiç hesaplanmıyor
    if min(mesafeler) > MAX_ILGI_MESAFE:
        return None

    ozellik = CiftOzellikleri(
        track_a=a.track_id,
        track_b=b.track_id,
        mesafe=mesafeler[-1],
        en_yakin_mesafe=min(mesafeler),
        ornek_sayisi=len(ortak),
        # Çiftin tamlığı iki pencerenin ORTAK örnek sayısına bağlı —
        # tek tek pencereler dolu olsa bile örtüşmeleri az olabilir.
        tamlik=min(a.tamlik, b.tamlik, len(ortak) / 12.0),
    )

    # ─── Yaklaşma hızı ───
    if len(ortak) >= 2:
        dt = ortak[-1][0] - ortak[0][0]
        if dt > 1e-6:
            # Negatif = yaklaşıyor. Tırmanmanın EN ERKEN sinyali:
            # kavga, iki kişi birbirine yaklaşarak başlar.
            ozellik.yaklasma_hizi = (mesafeler[-1] - mesafeler[0]) / dt

    # ─── Yakın kalma süresi ───
    yakin_ornekler = [m for m in mesafeler if m <= YAKIN_MESAFE]
    if yakin_ornekler and len(ortak) >= 2:
        pencere_suresi = ortak[-1][0] - ortak[0][0]
        ozellik.yakin_kalma_s = pencere_suresi * len(yakin_ornekler) / len(mesafeler)

    # ─── Karşılıklı bakış (son kareden) ───
    son_a, son_b = a.son, b.son
    if son_a is not None and son_b is not None:
        ozellik.karsilikli_bakis = _bakis_skoru(
            son_a.kp, son_b.kp, son_a.ayak, son_b.ayak
        )

    # ─── Senkron enerji ───
    # ⚠ Kavgada hareketler birbirine TEPKİ verir: biri vurur, diğeri
    # çekilir. Yani hareket enerjileri eşzamanlı yükselir. Yan yana
    # yürüyen iki kişide de korelasyon vardır ama enerji DÜŞÜKTÜR;
    # bu yüzden korelasyon tek başına değil, enerjiyle çarpılarak
    # kullanılıyor (aşağıdaki skorlayıcıda).
    ozellik.senkron_enerji = _senkron(a, b, ortak)

    return ozellik


def _senkron(
    a: IzPenceresi, b: IzPenceresi, ortak: list[tuple[float, np.ndarray, np.ndarray, float]]
) -> float | None:
    """İki kişinin hareket enerjilerinin eşzamanlılığı (0-1)."""
    if len(ortak) < 3:
        return None

    def enerjiler(pencere: IzPenceresi) -> list[float]:
        cikti: list[float] = []
        for onceki, sonraki in pencere.gecerli_ciftler():
            olcek = pencere.olcek()
            if olcek is None or olcek < 1e-6:
                continue
            dt = sonraki.ts - onceki.ts
            cikti.append(float(np.linalg.norm(sonraki.ayak - onceki.ayak) / dt / olcek))
        return cikti

    ea, eb = enerjiler(a), enerjiler(b)
    n = min(len(ea), len(eb))
    if n < 3:
        return None

    va, vb = np.array(ea[-n:]), np.array(eb[-n:])
    if va.std() < 1e-6 or vb.std() < 1e-6:
        return None
    korelasyon = float(np.corrcoef(va, vb)[0, 1])
    if np.isnan(korelasyon):
        return None
    # [-1,1] → [0,1]; ters korelasyon da bilgi taşır ama zayıf
    return max(0.0, korelasyon)


def kamera_ciftleri(
    pencereler: dict[int, IzPenceresi], azami_cift: int = 40
) -> list[CiftOzellikleri]:
    """Bir kameradaki tüm anlamlı çiftleri üretir.

    ⚠ ÜST SINIR VAR — kombinatorik patlama koruması
    17 kişilik bir sahnede 136 çift var. `cikar` uzak çiftleri zaten
    eliyor ama kalabalık bir anda yine de çok sayıda yakın çift olabilir.
    Sınır, en yakın çiftlere öncelik vererek uygulanıyor: tehlike
    yakınlıkla artıyor, uzak çiftleri atmak bilgi kaybı değil.
    """
    ids = sorted(pencereler)
    cikti: list[CiftOzellikleri] = []
    for i, ta in enumerate(ids):
        for tb in ids[i + 1 :]:
            ozellik = cikar(pencereler[ta], pencereler[tb])
            if ozellik is not None:
                cikti.append(ozellik)
    cikti.sort(key=lambda o: o.en_yakin_mesafe or 999.0)
    return cikti[:azami_cift]


__all__ = [
    "MAX_ILGI_MESAFE",
    "YAKIN_MESAFE",
    "CiftOzellikleri",
    "cikar",
    "kamera_ciftleri",
]
