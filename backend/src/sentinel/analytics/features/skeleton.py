"""İskelet geometrisi — özellik çıkarımının ortak dili.

COCO-17 keypoint düzeni
-----------------------
     0 burun
   1 sol göz      2 sağ göz
   3 sol kulak    4 sağ kulak
   5 sol omuz     6 sağ omuz
   7 sol dirsek   8 sağ dirsek
   9 sol bilek   10 sağ bilek
  11 sol kalça   12 sağ kalça
  13 sol diz     14 sağ diz
  15 sol ayak    16 sağ ayak

⚠ ÖLÇEK NORMALİZASYONU ZORUNLU
------------------------------
Kameraya 3 metre uzaklıktaki bir kişi ile 20 metre uzaklıktaki kişi
aynı hareketi yaptığında piksel cinsinden hızları **10 kat** farklı
çıkar. Ham piksel hızıyla eşik koyarsak, kameraya yakın herkes
"saldırgan", uzaktaki hiç kimse değil olur.

Bu yüzden mesafe ve hız birimlerinin tamamı **gövde boyuna** bölünür:

    normalize edilmiş hız = piksel/sn ÷ gövde_boyu_px   →  birim: gövde/sn

Böylece "bileğini saniyede 2 gövde boyu kadar hareket ettirdi" cümlesi
kameradaki konumdan bağımsız anlam taşır.

⚠ EKSİK KEYPOINT UYDURULMAZ
---------------------------
Güveni eşiğin altında olan keypoint **yok** sayılır, enterpolasyon
yapılmaz (PLAN.md §6.2). Görünmeyen bir uzvun yerini tahmin etmek,
olmayan bir duruşu varmış gibi göstermektir — ve o duruş doğrudan
"saldırganlık" skoruna girer.

Bunun sonucu: her özellik `None` dönebilir. Çağıran taraf bunu
istisna değil **normal durum** olarak ele almalı.
"""

from __future__ import annotations

import math

import numpy as np

# ─── COCO-17 indeksleri ───────────────────────────────────────
BURUN = 0
SOL_OMUZ, SAG_OMUZ = 5, 6
SOL_DIRSEK, SAG_DIRSEK = 7, 8
SOL_BILEK, SAG_BILEK = 9, 10
SOL_KALCA, SAG_KALCA = 11, 12
SOL_DIZ, SAG_DIZ = 13, 14
SOL_AYAK, SAG_AYAK = 15, 16

BILEKLER = (SOL_BILEK, SAG_BILEK)

# Bir keypoint'in "var" sayılması için gereken en düşük güven.
# PLAN.md §6.2 ile aynı değer; panelde de aynı eşik kullanılıyor
# (frontend/src/lib/skeleton.ts · KP_CONF_MIN) — ikisi ayrışırsa
# operatörün gördüğü iskelet ile analiz edilen iskelet farklı olur.
KP_MIN_CONF = 0.3

# Gövde boyu bu değerin altındaysa normalizasyon güvenilmez:
# küçük bir ölçü hatası bölme sonrasında büyük bir hıza dönüşür.
MIN_GOVDE_PX = 20.0


def var_mi(kp: np.ndarray, indeks: int) -> bool:
    """Keypoint yeterince güvenilir mi?"""
    return bool(indeks < len(kp) and kp[indeks][2] >= KP_MIN_CONF)


def nokta(kp: np.ndarray, indeks: int) -> np.ndarray | None:
    """Keypoint konumu (x, y) — güveni düşükse None."""
    if not var_mi(kp, indeks):
        return None
    return np.asarray(kp[indeks][:2], dtype=np.float64)


def orta_nokta(kp: np.ndarray, sol: int, sag: int) -> np.ndarray | None:
    """İki simetrik keypoint'in ortası.

    Biri görünmüyorsa görünen kullanılır — tek omuz da omuz hattı
    hakkında bilgi taşır. İkisi de yoksa None.
    """
    a, b = nokta(kp, sol), nokta(kp, sag)
    if a is not None and b is not None:
        return np.asarray((a + b) / 2.0, dtype=np.float64)
    return a if a is not None else b


def omuz_merkezi(kp: np.ndarray) -> np.ndarray | None:
    return orta_nokta(kp, SOL_OMUZ, SAG_OMUZ)


def kalca_merkezi(kp: np.ndarray) -> np.ndarray | None:
    return orta_nokta(kp, SOL_KALCA, SAG_KALCA)


def govde_boyu(kp: np.ndarray, bbox: tuple[float, float, float, float]) -> float | None:
    """Ölçek normalizasyonu için referans uzunluk (piksel).

    ⚠ İKİ KADEMELİ — ve sıra önemli
    Tercih edilen ölçü **omuz-kalça mesafesi**: kişi otursa, eğilse ya
    da kollarını kaldırsa bile bu mesafe sabit kalır.

    Kutu yüksekliği yedek plandır ve daha gürültülüdür: kollarını
    kaldıran bir kişinin kutusu uzar, oturan kişininki kısalır. Yani
    tam da ölçmek istediğimiz hareket, ölçeğimizi bozar. Yine de
    iskelet eksikken hiç ölçek olmamasından iyidir.

    Omuz-kalça mesafesi tipik olarak gövde boyunun ~%30'u; ölçekleri
    yaklaşık aynı büyüklüğe getirmek için 3 ile çarpılıyor ki iki
    yöntem arasında geçiş yapıldığında değerler sıçramasın.
    """
    omuz, kalca = omuz_merkezi(kp), kalca_merkezi(kp)
    if omuz is not None and kalca is not None:
        mesafe = float(np.linalg.norm(omuz - kalca))
        if mesafe >= MIN_GOVDE_PX / 3.0:
            return mesafe * 3.0

    yukseklik = bbox[3] - bbox[1]
    return yukseklik if yukseklik >= MIN_GOVDE_PX else None


def aci(a: np.ndarray, tepe: np.ndarray, b: np.ndarray) -> float:
    """`tepe` noktasındaki açı (derece, 0-180)."""
    v1, v2 = a - tepe, b - tepe
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    kosinus = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return math.degrees(math.acos(kosinus))


def dikeyle_aci(vektor: np.ndarray) -> float:
    """Bir vektörün dikey eksenle açısı (derece, 0-180).

    ⚠ Görüntü koordinatlarında y AŞAĞI doğru artar. Dik duran bir
    kişide kalça→omuz vektörü **yukarı**, yani negatif y yönündedir.
    Referans olarak `(0, -1)` alınıyor; `(0, 1)` alınsaydı dik duruş
    180° çıkar ve "yere yatmış" ile karışırdı.
    """
    norm = np.linalg.norm(vektor)
    if norm < 1e-6:
        return 0.0
    kosinus = float(np.clip(np.dot(vektor / norm, np.array([0.0, -1.0])), -1.0, 1.0))
    return math.degrees(math.acos(kosinus))


def govde_egimi(kp: np.ndarray) -> float | None:
    """Gövdenin dikeyden sapması (derece).

    0° = dik duruyor · 90° = yatay (düşmüş ya da öne eğilmiş)

    PLAN §6.5.2'de "öne yaslanma (agresif duruş)" göstergesi; ayrıca
    §6.4 Katman B'deki **düşme** kuralının ana girdisi.
    """
    omuz, kalca = omuz_merkezi(kp), kalca_merkezi(kp)
    if omuz is None or kalca is None:
        return None
    return dikeyle_aci(omuz - kalca)


def kol_yuksekligi(kp: np.ndarray, taraf: str = "sol") -> float | None:
    """Omuz-dirsek-bilek zincirinden kolun kalkma derecesi.

    Dönen değer 0-1 arası: bileğin omuz hizasına göre yüksekliği,
    kol uzunluğuna normalize edilmiş.

        0.0 = bilek omuz hizasında ya da altında (kol aşağıda)
        1.0 = bilek kol boyu kadar yukarıda (kol tam kalkmış)

    PLAN §6.5.2 `arm_elevation`. Vuruş hazırlığının en doğrudan
    göstergelerinden biri.
    """
    omuz_i, dirsek_i, bilek_i = (
        (SOL_OMUZ, SOL_DIRSEK, SOL_BILEK)
        if taraf == "sol"
        else (SAG_OMUZ, SAG_DIRSEK, SAG_BILEK)
    )
    omuz, dirsek, bilek = nokta(kp, omuz_i), nokta(kp, dirsek_i), nokta(kp, bilek_i)
    if omuz is None or bilek is None:
        return None

    # Kol uzunluğu: dirsek varsa iki parçadan, yoksa doğrudan mesafeden
    if dirsek is not None:
        kol_uzunlugu = float(
            np.linalg.norm(omuz - dirsek) + np.linalg.norm(dirsek - bilek)
        )
    else:
        kol_uzunlugu = float(np.linalg.norm(omuz - bilek))
    if kol_uzunlugu < 1e-6:
        return None

    # y aşağı arttığı için "yukarıda" = omuz.y - bilek.y pozitif
    yukseklik = float(omuz[1] - bilek[1])
    return float(np.clip(yukseklik / kol_uzunlugu, 0.0, 1.0))


def durus_genisligi(kp: np.ndarray, olcek: float) -> float | None:
    """Ayak bilekleri arası mesafe / gövde boyu.

    PLAN §6.5.2 `stance_width`. Geniş duruş savunma/saldırı
    hazırlığıdır; dar duruş rahat yürüyüştür.
    """
    sol, sag = nokta(kp, SOL_AYAK), nokta(kp, SAG_AYAK)
    if sol is None or sag is None or olcek < 1e-6:
        return None
    return float(np.linalg.norm(sol - sag) / olcek)


def omuz_yonu(kp: np.ndarray) -> np.ndarray | None:
    """Kişinin baktığı yönün yatay bileşeni (birim vektör).

    Omuz hattına **dik** olan yön. İki kişinin karşılıklı olup
    olmadığını (`mutual_facing`) anlamak için kullanılıyor.

    ⚠ İşaret belirsizliği var: omuz hattına dik iki yön vardır (öne ve
    arkaya) ve tek bir 2B iskeletten hangisinin "ön" olduğu kesin
    bilinemez. Burun görünüyorsa onu kullanarak ayrım yapılıyor;
    görünmüyorsa (kişi sırtı dönük) None dönüyor — yanlış yön üretmek
    yerine bilgi vermemek doğru.
    """
    sol, sag = nokta(kp, SOL_OMUZ), nokta(kp, SAG_OMUZ)
    if sol is None or sag is None:
        return None

    omuz_vektoru = sag - sol
    norm = np.linalg.norm(omuz_vektoru)
    if norm < 1e-6:
        return None
    # Dik vektör (saat yönünde 90° döndürme)
    dik = np.array([-omuz_vektoru[1], omuz_vektoru[0]]) / norm

    burun = nokta(kp, BURUN)
    if burun is None:
        return None
    # Burun omuz merkezinin hangi tarafında? O taraf "ön".
    merkez = (sol + sag) / 2.0
    yon = dik if float(np.dot(burun - merkez, dik)) >= 0 else -dik
    return np.asarray(yon, dtype=np.float64)


def ayak_noktasi(bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Kişinin zemindeki konumu — kutunun alt orta noktası.

    Mesafe hesaplarında merkez yerine bu kullanılıyor: kişi kameraya
    yaklaştıkça kutu büyür ve merkez yukarı kayar, ama ayak noktası
    zemin düzleminde kalır. Takipçideki hız hesabı da aynı noktayı
    kullanıyor (tracker/botsort.py) — iki yerin tutarlı olması şart,
    yoksa hız ile mesafe farklı referanslarda ölçülür.
    """
    x1, _y1, x2, y2 = bbox
    return np.array([(x1 + x2) / 2.0, y2], dtype=np.float64)


__all__ = [
    "BILEKLER",
    "BURUN",
    "KP_MIN_CONF",
    "SAG_AYAK",
    "SAG_BILEK",
    "SAG_DIRSEK",
    "SAG_DIZ",
    "SAG_KALCA",
    "SAG_OMUZ",
    "SOL_AYAK",
    "SOL_BILEK",
    "SOL_DIRSEK",
    "SOL_DIZ",
    "SOL_KALCA",
    "SOL_OMUZ",
    "aci",
    "ayak_noktasi",
    "dikeyle_aci",
    "durus_genisligi",
    "govde_boyu",
    "govde_egimi",
    "kalca_merkezi",
    "kol_yuksekligi",
    "nokta",
    "omuz_merkezi",
    "omuz_yonu",
    "orta_nokta",
    "var_mi",
]
