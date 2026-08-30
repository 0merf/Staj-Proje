"""KATMAN B — kural tabanlı anomaliler (PLAN.md §6.4).

⚠ BU DOSYA 26.08.2026'DA YOKTU
------------------------------
Katman B'nin dört kuralı da (düşme, koşma, oyalanma, kalabalık)
**hiç birim testi olmadan** üretimde çalışıyordu. Daha kötüsü: bir
belge dosyasına "düşme kuralı sentetik testlerle doğrulanmıştı" diye
yazılmıştı ve bu doğru değildi.

Mimari kural 0 tam olarak bunun için var: *belgede yazan ile kodda
olan aynı olmalı.* Sapmanın kendisi değil, **gerekçesiz sapma** sorun —
burada gerekçe de yoktu, sadece yanlış bir cümle vardı.

Testlerin bakış açısı
---------------------
Bu kurallar bir insan hakkında iddiada bulunuyor ("bu kişi düştü").
Yanlış olduğunda iki yönde de pahalı ve hata SESSİZ: alarm makul
görünür, sadece yanlış sebeple çıkmıştır.

O yüzden her kural için **iki taraf** da sınanıyor:
  · olay gerçekten olduğunda ateşliyor mu
  · olaya BENZEYEN ama olay olmayan durumda susuyor mu

İkincisi daha önemli. Ateşlemeyen bir kural görünür bir eksiklik;
yanlış ateşleyen bir kural sistemin güvenilirliğini bitirir.
"""

from __future__ import annotations

from sentinel.analytics.anomaly.rules import (
    DUSME_EGIM_AZAMI,
    DUSME_EGIM_DERECE,
    DUSME_EGIM_HIZI,
    DUSME_EN_BOY,
    KOSMA_HIZ,
    KOSMA_MIN_TAMLIK,
    OYALANMA_OLAGAN_ORAN,
    OYALANMA_SANIYE,
    AnomaliTuru,
    KuralMotoru,
)
from sentinel.analytics.features.person import KisiOzellikleri


def kisi(track_id: int = 1, **alanlar: float) -> KisiOzellikleri:
    """Varsayılanı 'ayakta duran, sakin bir insan' olan özellik vektörü.

    ⚠ Varsayılanın NORMAL olması bilinçli: her test yalnızca
    değiştirdiği alanı anlatıyor, geri kalanı "normal" diye okunuyor.
    Aksi hâlde bir testin neyi sınadığı, yazılmayan alanlardan
    çıkarılmak zorunda kalırdı.
    """
    varsayilan: dict[str, float] = {
        "en_boy_orani": 0.4,      # ayakta duran kişi
        "govde_egimi": 5.0,       # neredeyse dik
        "govde_egimi_degisimi": 2.0,
        "govde_hizi": 0.3,        # ölçülen normal yaya medyanı
        "oyalanma_s": 0.0,
        "tamlik": 1.0,
        "ornek_sayisi": 12,
    }
    varsayilan.update(alanlar)
    return KisiOzellikleri(track_id=track_id, **varsayilan)  # type: ignore[arg-type]


def turleri(bulgular: list) -> set[AnomaliTuru]:
    return {b.tur for b in bulgular}


# ══════════════════════════════════════════════════════════════
#  DÜŞME — üç kanıt birden aranıyor
# ══════════════════════════════════════════════════════════════


class TestDusme:
    def test_yere_dusen_kisi_YAKALANIYOR(self) -> None:
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01",
            [kisi(
                en_boy_orani=DUSME_EN_BOY + 0.3,
                govde_egimi=DUSME_EGIM_DERECE + 25,
                govde_egimi_degisimi=DUSME_EGIM_HIZI + 40,
            )],
            simdi=100.0,
            dt=0.25,
        )
        assert AnomaliTuru.DUSME in turleri(bulgular)

    def test_EGILIP_BIR_SEY_ALAN_kisi_dusme_SAYILMIYOR(self) -> None:
        """⚠ Düşmeyi eğilmekten ayıran şey HIZ.

        Eğilen kişide de gövde yatar, kutu da genişler. Tek fark:
        eğilmek yavaştır, düşmek ani. `DUSME_EGIM_HIZI` bu ayrımı
        yapıyor — bu test o eşiğin gerçekten kanıt olarak kullanıldığını
        sabitliyor.
        """
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01",
            [kisi(
                en_boy_orani=DUSME_EN_BOY + 0.3,
                govde_egimi=DUSME_EGIM_DERECE + 25,
                govde_egimi_degisimi=DUSME_EGIM_HIZI - 25,  # yavaş eğildi
            )],
            simdi=100.0,
            dt=0.25,
        )
        assert AnomaliTuru.DUSME not in turleri(bulgular)

    def test_TERS_DONMUS_iskelet_dusme_SAYILMIYOR(self) -> None:
        """⚠ REGRESYON — canlı sistemde gerçekten yaşandı.

        Poz modeli baş ile ayağı karıştırınca gövde eğimi 175° çıkıyor
        ve kural skor 1.00 üretiyordu. 175° "yatay" değil, "baş aşağı
        dik" demek — fiziksel olarak düşmüş bir insanın gövdesi
        90° civarındadır.

        Üst sınır (`DUSME_EGIM_AZAMI`) bu yüzden eklendi (commit
        1dfa4ca). Bu hata SENTETİK testte asla çıkmazdı; gerçek
        görüntü olmadan bulunamazdı.
        """
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01",
            [kisi(
                en_boy_orani=DUSME_EN_BOY + 0.3,
                govde_egimi=DUSME_EGIM_AZAMI + 25,   # 175° — ters iskelet
                govde_egimi_degisimi=DUSME_EGIM_HIZI + 40,
            )],
            simdi=100.0,
            dt=0.25,
        )
        assert AnomaliTuru.DUSME not in turleri(bulgular)

    def test_AYAKTA_duran_kisi_dusme_SAYILMIYOR(self) -> None:
        m = KuralMotoru()
        bulgular = m.degerlendir("cam-01", [kisi()], simdi=100.0, dt=0.25)
        assert AnomaliTuru.DUSME not in turleri(bulgular)


# ══════════════════════════════════════════════════════════════
#  KOŞMA
# ══════════════════════════════════════════════════════════════


class TestKosma:
    def test_kosan_kisi_YAKALANIYOR(self) -> None:
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01", [kisi(govde_hizi=KOSMA_HIZ + 0.5)], simdi=100.0, dt=0.25
        )
        assert AnomaliTuru.KOSMA in turleri(bulgular)

    def test_DUSUK_TAMLIK_kosma_sayilmiyor(self) -> None:
        """⚠ Az örnekten çıkan yüksek hız, hız değil gürültüdür.

        İki örnekten hesaplanan hızda tek bir kutu sıçraması "koşuyor"
        gibi görünür. Gerçekten koşan biri kadrajda birkaç saniye kalır
        ve penceresi dolar.
        """
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01",
            [kisi(govde_hizi=KOSMA_HIZ + 2.0, tamlik=KOSMA_MIN_TAMLIK - 0.1)],
            simdi=100.0,
            dt=0.25,
        )
        assert AnomaliTuru.KOSMA not in turleri(bulgular)

    def test_NORMAL_yuruyus_kosma_sayilmiyor(self) -> None:
        # Ölçülen gövde hızı p99 = 0.94 (features_20260826-175748.json)
        m = KuralMotoru()
        bulgular = m.degerlendir("cam-01", [kisi(govde_hizi=0.94)], simdi=100.0, dt=0.25)
        assert AnomaliTuru.KOSMA not in turleri(bulgular)


# ══════════════════════════════════════════════════════════════
#  OYALANMA — süre TEK BAŞINA yetmiyor
# ══════════════════════════════════════════════════════════════


def _oyalandir(m: KuralMotoru, saniye: float, normal: float | None = None) -> list:
    """Bir kişiyi `saniye` boyunca aynı yerde tutar, TÜM bulguları döndürür.

    ⚠ Kare kare besleniyor: oyalanma sayacı `dt` ile birikiyor, tek
    çağrıda oluşmaz.

    ⚠ BULGULAR BİRİKTİRİLİYOR, son kare değil
    Oyalanma alarmı eşik aşıldığında **bir kez** ateşliyor; sonraki
    karelerde `durum.aktif` onu bastırıyor (aynı olay tekrar tekrar
    bildirilmemeli). Yalnızca son karenin çıktısına bakmak, alarm
    verilmiş olsa bile boş liste görmek demekti — testin ilk hâli tam
    bu yüzden yanlış yere kırmızı yandı.

    Ders, `test_aggression.akis` ile aynı aileden: zaman içinde durum
    biriktiren bir sistemi tek bir ana bakarak test edemezsin.
    """
    tumu: list = []
    t = 100.0
    adim = 1.0
    while t < 100.0 + saniye:
        tumu.extend(
            m.degerlendir(
                "cam-01",
                [kisi(oyalanma_s=3.0, govde_hizi=0.02)],
                simdi=t,
                dt=adim,
                oyalanma_normali={1: normal},
            )
        )
        t += adim
    return tumu


class TestOyalanma:
    def test_uzun_sure_ayni_yerde_YAKALANIYOR(self) -> None:
        """Profil bilgisi yokken kural ESKİ davranışına dönüyor."""
        m = KuralMotoru()
        bulgular = _oyalandir(m, OYALANMA_SANIYE + 5, normal=None)
        assert AnomaliTuru.OYALANMA in turleri(bulgular)

    def test_INSANLARIN_NORMALDE_DURDUGU_yerde_alarm_YOK(self) -> None:
        """⚠ 26.08.2026'da eklenen ikinci kanıt.

        Bank, vitrin önü, otobüs durağı — buralarda 45 saniye durmak
        olayın kendisi değil, mekânın doğasıdır. Kural artık öğrenilmiş
        profile soruyor: "burada gözlemlerin kaçta kaçı durağandı?"

        Bu, mimari kural 7'nin ("her kameranın normali AYRI") mekân
        boyutundaki karşılığı.
        """
        m = KuralMotoru()
        bulgular = _oyalandir(m, OYALANMA_SANIYE + 5, normal=OYALANMA_OLAGAN_ORAN + 0.2)
        assert AnomaliTuru.OYALANMA not in turleri(bulgular)

    def test_GECIS_YOLUNDA_durmak_alarm_VERIYOR(self) -> None:
        """Aynı süre, farklı yer — ve skor daha yüksek olmalı.

        Bir geçiş yolunda (durağan oran ~%1) durmak, sıradan bir
        bekleme alanında durmaktan daha kayda değerdir; skor bunu
        yansıtmalı.
        """
        m = KuralMotoru()
        bulgular = _oyalandir(m, OYALANMA_SANIYE + 5, normal=0.01)
        oyalanma = [b for b in bulgular if b.tur is AnomaliTuru.OYALANMA]
        assert oyalanma, "geçiş yolunda oyalanma alarm vermeliydi"
        assert "bolgede_duranlarin_orani" in oyalanma[0].kanit, (
            "operatör NEDEN alarm verildiğini görebilmeli"
        )

    def test_kisa_sure_durmak_alarm_VERMIYOR(self) -> None:
        m = KuralMotoru()
        bulgular = _oyalandir(m, OYALANMA_SANIYE / 3, normal=0.01)
        assert AnomaliTuru.OYALANMA not in turleri(bulgular)


# ══════════════════════════════════════════════════════════════
#  Güvenilirlik kapısı — tüm kuralların ortak ön koşulu
# ══════════════════════════════════════════════════════════════


class TestTamlikKapisi:
    def test_DUSUK_TAMLIK_hicbir_kural_calismiyor(self) -> None:
        """Az örnekten çıkan bir sayı, ne kadar uç olursa olsun kanıt değil.

        Buradaki özellik vektörü hem düşme hem koşma eşiğini fena hâlde
        aşıyor — ama tek örnekten üretilmiş. Sistem susmalı.
        """
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01",
            [kisi(
                en_boy_orani=2.0,
                govde_egimi=90.0,
                govde_egimi_degisimi=200.0,
                govde_hizi=5.0,
                tamlik=0.05,
                ornek_sayisi=1,
            )],
            simdi=100.0,
            dt=0.25,
        )
        assert bulgular == []

    def test_KIMLIKSIZ_iz_degerlendirilmiyor(self) -> None:
        """Zamansal kural, kimliği olmayan bir tespite uygulanamaz (P-13)."""
        m = KuralMotoru()
        bulgular = m.degerlendir(
            "cam-01",
            [kisi(track_id=-1, en_boy_orani=2.0, govde_egimi=90.0,
                  govde_egimi_degisimi=200.0)],
            simdi=100.0,
            dt=0.25,
        )
        assert bulgular == []
