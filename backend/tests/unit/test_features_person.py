"""Kişi bazlı özellik çıkarımı — PLAN.md §6.5.2.

⚠ NEDEN BU TESTLER ÖNEMLİ
-------------------------
Bu sayılar doğrudan **saldırganlık skoruna** giriyor. Yanlış bir
`bilek_hizi_azami`, sakin bir insanı alarma dönüştürebilir ya da
gerçek bir kavgayı sessizce geçirebilir. Ve hata sessizdir: sayı
üretilir, makul görünür, sadece yanlıştır.

Üç sınıf hata özellikle kilitleniyor:

  1. **Ölçek normalizasyonu bozulursa** kameraya yakın herkes
     "saldırgan", uzaktaki hiç kimse olmaz.
  2. **Eksik keypoint uydurulursa** olmayan bir duruş üretilir.
  3. **Kare boşluğu hız sanılırsa** atlanan karelerden sahte
     hızlanma çıkar (sistem doygunken karelerin %70'i atılıyor).
"""

from __future__ import annotations

import numpy as np
import pytest

from sentinel.analytics.features import skeleton as sk
from sentinel.analytics.features.person import cikar
from sentinel.analytics.features.window import (
    MAX_BOSLUK_S,
    PENCERE_S,
    TAM_ORNEK,
    IzPenceresi,
    Ornek,
    PencereDeposu,
)

KUTU = (80.0, 40.0, 120.0, 200.0)


def iskelet(
    *,
    olcek: float = 1.0,
    kol_yukari: bool = False,
    yatay: bool = False,
    eksik: tuple[int, ...] = (),
) -> np.ndarray:
    """Kontrollü sentetik iskelet.

    `olcek` ile tüm kişi büyütülüp küçültülüyor — ölçek
    normalizasyonunu test etmenin yolu bu.
    """
    kp = np.zeros((17, 3), dtype=np.float64)
    kp[:, 2] = 0.9
    temel = {
        sk.BURUN: (100, 40),
        sk.SOL_OMUZ: (85, 60),
        sk.SAG_OMUZ: (115, 60),
        sk.SOL_DIRSEK: (80, 90),
        sk.SAG_DIRSEK: (120, 90),
        sk.SOL_BILEK: (78, 20) if kol_yukari else (78, 120),
        sk.SAG_BILEK: (122, 120),
        sk.SOL_KALCA: (90, 130),
        sk.SAG_KALCA: (110, 130),
        sk.SOL_AYAK: (88, 200),
        sk.SAG_AYAK: (112, 200),
    }
    for i, (x, y) in temel.items():
        kp[i][0] = x * olcek
        kp[i][1] = y * olcek

    if yatay:
        # Gövdeyi 90° çevir: omuz ile kalça AYNI yükseklikte, yan yana
        kp[sk.SOL_OMUZ][:2] = [60 * olcek, 130 * olcek]
        kp[sk.SAG_OMUZ][:2] = [60 * olcek, 150 * olcek]

    for i in eksik:
        kp[i][2] = 0.0  # güven sıfır = "görünmüyor"
    return kp


def pencere_kur(
    kareler: list[tuple[float, np.ndarray]],
    kutu: tuple[float, float, float, float] = KUTU,
) -> IzPenceresi:
    depo = PencereDeposu()
    for ts, kp in kareler:
        depo.ekle(
            "cam-01",
            1,
            Ornek(
                ts=ts,
                bbox=kutu,
                kp=kp,
                olcek=sk.govde_boyu(kp, kutu),
                ayak=sk.ayak_noktasi(kutu),
            ),
        )
    pencere = depo.al("cam-01", 1)
    assert pencere is not None
    return pencere


# ══════════════════════════════════════════════════════════════
#  Geometri
# ══════════════════════════════════════════════════════════════


class TestGeometri:
    def test_dik_durus_sifir_derece(self) -> None:
        """⚠ Görüntü koordinatlarında y AŞAĞI artar.

        Referans vektör yanlış işaretle yazılsaydı dik duruş 180°
        çıkar ve "yere yatmış" ile karışırdı — düşme kuralı ters
        çalışırdı.
        """
        assert sk.govde_egimi(iskelet()) == pytest.approx(0.0, abs=1.0)

    def test_yatay_govde_90_dereceye_yakin(self) -> None:
        """Düşme tespitinin (PLAN §6.4 Katman B) temel sinyali."""
        egim = sk.govde_egimi(iskelet(yatay=True))
        assert egim is not None
        assert egim > 60.0

    def test_kol_kalkinca_yukseklik_artiyor(self) -> None:
        asagida = sk.kol_yuksekligi(iskelet(), "sol")
        yukarida = sk.kol_yuksekligi(iskelet(kol_yukari=True), "sol")
        assert asagida is not None and yukarida is not None
        assert yukarida > asagida

    def test_eksik_keypoint_UYDURULMUYOR(self) -> None:
        """⚠ PLAN §6.2 — görünmeyen uzvun yeri tahmin edilmez.

        `None` dönmek "hesaplayamadım" demek. Bunun yerine 0.0
        dönseydi füzyon katmanı onu "kol tamamen aşağıda" diye okurdu
        — yani bilgisizliği veri sanardı.
        """
        kor = iskelet(eksik=(sk.SOL_OMUZ, sk.SOL_BILEK))
        assert sk.kol_yuksekligi(kor, "sol") is None

    def test_omuz_ve_kalca_yoksa_egim_hesaplanmiyor(self) -> None:
        kor = iskelet(eksik=(sk.SOL_KALCA, sk.SAG_KALCA))
        assert sk.govde_egimi(kor) is None

    def test_tek_omuz_gorunuyorsa_yine_kullaniliyor(self) -> None:
        """Tek omuz da omuz hattı hakkında bilgi taşır — atmak israf."""
        assert sk.omuz_merkezi(iskelet(eksik=(sk.SOL_OMUZ,))) is not None

    def test_ayak_noktasi_kutunun_alt_ortasi(self) -> None:
        """Takipçinin hız referansıyla AYNI nokta olmalı.

        Ayrışırlarsa hız ile mesafe farklı referanslarda ölçülür ve
        çift bazlı özellikler (yaklaşma hızı) tutarsızlaşır.
        """
        assert sk.ayak_noktasi(KUTU).tolist() == [100.0, 200.0]


# ══════════════════════════════════════════════════════════════
#  ⭐ Ölçek normalizasyonu — en kritik özellik
# ══════════════════════════════════════════════════════════════


class TestOlcekNormalizasyonu:
    def test_AYNI_hareket_FARKLI_uzaklikta_ayni_hizi_veriyor(self) -> None:
        """⚠ Bu tutmazsa sistem kullanılamaz.

        Kameraya yakın kişi ile uzak kişi aynı hareketi yaptığında
        piksel hızları kat kat farklıdır. Normalizasyon bozulursa
        yakındaki herkes "saldırgan", uzaktaki hiç kimse olur.

        Burada aynı hareket 1× ve 3× ölçekte yapılıyor; normalize
        edilmiş hız aynı çıkmalı.
        """
        hizlar = []
        for olcek in (1.0, 3.0):
            kutu = (
                KUTU[0] * olcek,
                KUTU[1] * olcek,
                KUTU[2] * olcek,
                KUTU[3] * olcek,
            )
            pencere = pencere_kur(
                [
                    (0.0, iskelet(olcek=olcek)),
                    (0.25, iskelet(olcek=olcek, kol_yukari=True)),
                ],
                kutu,
            )
            ozellik = cikar(pencere)
            assert ozellik.bilek_hizi_azami is not None
            hizlar.append(ozellik.bilek_hizi_azami)

        assert hizlar[0] == pytest.approx(hizlar[1], rel=0.02)

    def test_govde_boyu_omuz_kalcadan_turetiliyor(self) -> None:
        """Kutu yüksekliği yedek plan; omuz-kalça tercih edilir.

        Kollarını kaldıran kişinin KUTUSU uzar ama omuz-kalça mesafesi
        değişmez. Ölçek kutudan alınsaydı, ölçmek istediğimiz hareket
        ölçeğimizi bozardı.
        """
        normal = sk.govde_boyu(iskelet(), KUTU)
        kolu_kalkik = sk.govde_boyu(iskelet(kol_yukari=True), KUTU)
        assert normal is not None and kolu_kalkik is not None
        assert normal == pytest.approx(kolu_kalkik, rel=0.01)


# ══════════════════════════════════════════════════════════════
#  Pencere davranışı — ölçümün tasarıma girdiği yer
# ══════════════════════════════════════════════════════════════


class TestPencere:
    def test_KISMI_pencereyle_de_ozellik_uretiliyor(self) -> None:
        """⚠ Ölçüm: izlerin medyan ömrü 4 kare (1 sn).

        "12 örnek yoksa hesaplama" kuralı modülü izlerin yarısından
        fazlasında susturur ve saldırganlık tespiti pratikte çalışmaz.
        """
        pencere = pencere_kur(
            [(0.0, iskelet()), (0.25, iskelet(kol_yukari=True))]
        )
        ozellik = cikar(pencere)
        assert ozellik.bilek_hizi_azami is not None
        assert ozellik.ornek_sayisi == 2

    def test_tamlik_skoru_ornek_sayisiyla_artiyor(self) -> None:
        """⚠ Füzyona giren güvenilirlik sinyali.

        2 örnekten çıkan hız ile 12 örnekten çıkan aynı sayı aynı
        güvene sahip değil; bu skor olmadan füzyon ikisini eşit sayar.
        """
        az = cikar(pencere_kur([(0.0, iskelet()), (0.25, iskelet())]))
        cok = cikar(
            pencere_kur([(i * 0.25, iskelet()) for i in range(TAM_ORNEK)])
        )
        assert az.tamlik < cok.tamlik
        assert cok.tamlik == pytest.approx(1.0)

    def test_tek_ornekte_zamansal_ozellik_YOK_ama_durus_VAR(self) -> None:
        """Hız bir FARK — tek noktadan hesaplanamaz. Duruş hesaplanır."""
        ozellik = cikar(pencere_kur([(0.0, iskelet())]))
        assert ozellik.bilek_hizi_azami is None
        assert ozellik.govde_egimi is not None
        assert ozellik.en_boy_orani is not None

    def test_BUYUK_BOSLUK_hiz_sanilmiyor(self) -> None:
        """⚠ Sistem doygunken karelerin %70'i atılıyor (ölçüldü).

        Atlanan karelerden sonra kişi büyük bir mesafe kat etmiş
        görünür. O aralıktan hız hesaplamak sahte bir "ani hızlanma"
        üretir — ve tam da bu, saldırganlık skorunu tetikleyen sinyal.
        """
        pencere = pencere_kur(
            [
                (0.0, iskelet()),
                (0.25 + MAX_BOSLUK_S, iskelet(kol_yukari=True)),  # boşluk
            ]
        )
        assert pencere.gecerli_ciftler() == []
        assert cikar(pencere).bilek_hizi_azami is None

    def test_pencere_suresi_asilinca_eski_ornek_dusuyor(self) -> None:
        """3 sn'lik pencere gerçekten 3 sn tutmalı — ne fazla, ne eksik.

        Sınır DAHİL: `simdi - ts > PENCERE_S` olan düşer, tam 3.0 sn
        önceki örnek KALIR. Fazla tutmak eski hareketi güncel sanmak,
        az tutmak zamansal bilgiyi boşa harcamak olurdu.
        """
        pencere = pencere_kur([(t, iskelet()) for t in (0.0, 1.0, 2.0, 5.0)])

        # t=5.0'a göre: 0.0 (5 sn) ve 1.0 (4 sn) düştü,
        #               2.0 (tam 3 sn) ve 5.0 kaldı
        assert pencere.sayi == 2
        assert [o.ts for o in pencere.ornekler] == [2.0, 5.0]
        assert pencere.sure_s == pytest.approx(PENCERE_S)

    def test_kameralar_arasi_kimlik_KARISMIYOR(self) -> None:
        """⚠ Takip kimlikleri kamera İÇİNDE benzersiz, arasında değil.

        cam-01'deki 7 numaralı iz ile cam-09'daki 7 numaralı iz farklı
        kişiler. Karışsalardı iki ayrı insanın hareketleri tek bir
        özellik vektöründe birleşirdi.
        """
        depo = PencereDeposu()
        for kamera in ("cam-01", "cam-09"):
            depo.ekle(
                kamera,
                7,
                Ornek(
                    ts=0.0,
                    bbox=KUTU,
                    kp=iskelet(),
                    olcek=100.0,
                    ayak=sk.ayak_noktasi(KUTU),
                ),
            )
        assert depo.aktif_iz_sayisi == 2

    def test_eski_izler_budaniyor(self) -> None:
        """Budama olmazsa sözlük sınırsız büyür.

        Kimlik parçalanması yüksek (%45-72 ölçüldü), yani takipçi
        sürekli yeni kimlik üretiyor ve birikim hızlı.
        """
        depo = PencereDeposu(unut_s=5.0)
        depo.ekle(
            "cam-01",
            1,
            Ornek(ts=0.0, bbox=KUTU, kp=None, olcek=100.0, ayak=sk.ayak_noktasi(KUTU)),
        )
        assert depo.buda(simdi=100.0) == 1
        assert depo.aktif_iz_sayisi == 0


# ══════════════════════════════════════════════════════════════
#  Anlamsal doğruluk
# ══════════════════════════════════════════════════════════════


class TestOzellikAnlami:
    def test_hizli_kol_kaldirma_yavastan_YUKSEK_hiz_veriyor(self) -> None:
        """Vuruş hazırlığının ana sinyali."""
        hizli = cikar(
            pencere_kur([(0.0, iskelet()), (0.1, iskelet(kol_yukari=True))])
        )
        yavas = cikar(
            pencere_kur([(0.0, iskelet()), (1.0, iskelet(kol_yukari=True))])
        )
        assert hizli.bilek_hizi_azami is not None
        assert yavas.bilek_hizi_azami is not None
        assert hizli.bilek_hizi_azami > yavas.bilek_hizi_azami * 5

    def test_yerinde_duran_kisi_OYALANMA_sayiliyor(self) -> None:
        pencere = pencere_kur([(i * 0.25, iskelet()) for i in range(8)])
        assert cikar(pencere).oyalanma_s > 1.0

    def test_yatan_kisi_en_boy_orani_BUYUK(self) -> None:
        """Düşme kuralının girdisi: ayakta ~0.4, yatmış > 1.0."""
        ayakta = cikar(pencere_kur([(0.0, iskelet())], KUTU))
        yatmis = cikar(
            pencere_kur([(0.0, iskelet(yatay=True))], (40.0, 150.0, 200.0, 200.0))
        )
        assert ayakta.en_boy_orani is not None and yatmis.en_boy_orani is not None
        assert ayakta.en_boy_orani < 1.0 < yatmis.en_boy_orani

    def test_iskeletsiz_ornek_COKMEYE_yol_acmiyor(self) -> None:
        """Poz kademesi kapalıysa ya da iskelet çıkmadıysa (%7) None gelir."""
        depo = PencereDeposu()
        for t in (0.0, 0.25):
            depo.ekle(
                "cam-01",
                1,
                Ornek(
                    ts=t, bbox=KUTU, kp=None, olcek=None, ayak=sk.ayak_noktasi(KUTU)
                ),
            )
        pencere = depo.al("cam-01", 1)
        assert pencere is not None
        ozellik = cikar(pencere)  # patlamamalı
        assert ozellik.bilek_hizi_azami is None
        assert ozellik.en_boy_orani is not None  # kutudan gelen yine var
