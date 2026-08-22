"""KATMAN A — kamera başına normal profili.

⚠ NEDEN BU TESTLER
------------------
Bu katman **öğreniyor**, yani hatası zamanla birikiyor ve sessiz.
Yanlış öğrenilmiş bir profil çökme üretmez; sadece yanlış alarm verir
ya da gerçek olayı kaçırır. İkisi de fark edilmesi en zor hata türü.

Üç sınıf hata kilitleniyor:
  1. **Soğuk başlangıçta alarm** — hiçbir şey öğrenilmemişken her
     gözlem "hiç görülmemiş" olur ve sistem açılışta alarm yağdırır.
  2. **Kendi kendini normalleştirme** — gözlem önce öğrenilip sonra
     skorlanırsa, olay kendi normalini yükseltip kendini gizler.
  3. **Kalıcılık kaybı** — profil diske yazılmazsa her yeniden
     başlatma sistemi saatlerce kör bırakır.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from sentinel.analytics.anomaly.normalcy import (
    HUCRE_ASGARI_ORNEK,
    PROFIL_ASGARI_ORNEK,
    KameraNormali,
    NormalProfilDeposu,
)

W, H = 1280.0, 720.0


def _egit(
    profil: KameraNormali,
    *,
    n: int,
    x: float,
    y: float,
    hiz: float = 0.5,
    yon: float | None = 0.0,
) -> None:
    """Profili aynı davranışla n kez besler."""
    for _ in range(n):
        profil.ogren(x, y, W, H, hiz, yon)


# ══════════════════════════════════════════════════════════════
#  Soğuk başlangıç koruması
# ══════════════════════════════════════════════════════════════


class TestSogukBaslangic:
    def test_ogrenmeden_HIC_skor_uretilmiyor(self) -> None:
        """⚠ En kritik koruma.

        Profil boşken her gözlem "hiç görülmemiş bölge" olur. Bu kontrol
        olmasa sistem her açılışta 20 kameradan alarm yağdırırdı ve
        operatör ilk dakikada alarmları kapatırdı.
        """
        profil = KameraNormali(camera="cam-01")
        skor, kanit = profil.skorla(640.0, 700.0, W, H, 0.5, 0.0)
        assert skor == 0.0
        assert kanit == {}

    def test_esik_asilinca_hazir_oluyor(self) -> None:
        profil = KameraNormali(camera="cam-01")
        assert not profil.hazir
        _egit(profil, n=PROFIL_ASGARI_ORNEK, x=640.0, y=700.0)
        assert profil.hazir

    def test_hucre_az_ornekliyse_hiz_karari_verilmiyor(self) -> None:
        """Tek gözlemden "burada hız 0.4'tür" demek istatistik değil.

        Profil geneli hazır olsa bile, O HÜCRE yeterince görülmediyse
        hız kararı verilmiyor.
        """
        profil = KameraNormali(camera="cam-01")
        # Profili başka bir bölgede doyur
        _egit(profil, n=PROFIL_ASGARI_ORNEK, x=100.0, y=700.0)
        # Yeni bölgede az örnek: burada hız kararı OLMAMALI
        _egit(profil, n=HUCRE_ASGARI_ORNEK - 5, x=1200.0, y=700.0, hiz=0.5)

        _skor, kanit = profil.skorla(1200.0, 700.0, W, H, 5.0, 0.0)
        assert "hiz_sapmasi_sigma" not in kanit


# ══════════════════════════════════════════════════════════════
#  Öğrenilen normal — mimari kural 7
# ══════════════════════════════════════════════════════════════


class TestOgrenilenNormal:
    def test_ALISILMIS_bolge_ve_hiz_anomali_DEGIL(self) -> None:
        """Öğrendiğini normal saymalı — yoksa her şey alarm olur."""
        profil = KameraNormali(camera="cam-01")
        _egit(profil, n=PROFIL_ASGARI_ORNEK, x=640.0, y=700.0, hiz=0.5)

        skor, _ = profil.skorla(640.0, 700.0, W, H, 0.5, 0.0)
        assert skor == 0.0

    def test_HIC_GIDILMEYEN_bolge_anomali(self) -> None:
        """Otoparkta hep aynı yoldan geçiliyorsa, çimenin ortası tuhaftır."""
        profil = KameraNormali(camera="cam-01")
        _egit(profil, n=PROFIL_ASGARI_ORNEK, x=640.0, y=700.0)

        # Kadrajın tamamen başka bir köşesi
        skor, kanit = profil.skorla(60.0, 60.0, W, H, 0.5, 0.0)
        assert skor > 0.5
        assert "nadir_bolge" in kanit

    def test_AYNI_bolgede_OLAGANDISI_hiz_yakalaniyor(self) -> None:
        """Aynı yerde ama üç kat hızlı → sapma."""
        profil = KameraNormali(camera="cam-01")
        # Hafif değişken bir hız dağılımı öğret (sapma sıfır olmasın)
        for i in range(PROFIL_ASGARI_ORNEK):
            profil.ogren(640.0, 700.0, W, H, 0.5 + (i % 5) * 0.02, 0.0)

        skor, kanit = profil.skorla(640.0, 700.0, W, H, 3.0, 0.0)
        assert skor > 0.0
        assert kanit["hiz_sapmasi_sigma"] > 3.0

    def test_TERS_YON_yakalaniyor(self) -> None:
        """⚠ "Ters yön" kuralı ayrıca yazılmadı — profilden DOĞAL çıkıyor.

        Koridorda herkes bir yöne gidiyorsa, ters yön o hücrede nadir
        bir kovadır. Katman A'nın kural yazmadan kural üretmesi.
        """
        profil = KameraNormali(camera="cam-01")
        _egit(profil, n=PROFIL_ASGARI_ORNEK, x=640.0, y=700.0, yon=0.0)

        # Tam ters yön (π radyan)
        skor, kanit = profil.skorla(640.0, 700.0, W, H, 0.5, math.pi)
        assert skor > 0.0
        assert "yon_orani" in kanit

    def test_HER_KAMERANIN_normali_AYRI(self) -> None:
        """⚠ Mimari kural 7.

        Aynı hız, bir kamerada normal diğerinde anormal olabilmeli.
        """
        sakin = KameraNormali(camera="cam-otopark")
        hareketli = KameraNormali(camera="cam-cadde")
        for i in range(PROFIL_ASGARI_ORNEK):
            sakin.ogren(640.0, 700.0, W, H, 0.2 + (i % 5) * 0.01, 0.0)
            hareketli.ogren(640.0, 700.0, W, H, 1.2 + (i % 5) * 0.01, 0.0)

        hiz = 1.2
        sakin_skor, _ = sakin.skorla(640.0, 700.0, W, H, hiz, 0.0)
        hareketli_skor, _ = hareketli.skorla(640.0, 700.0, W, H, hiz, 0.0)

        assert sakin_skor > 0.0, "sakin kamerada 1.2 olağandışı olmalıydı"
        assert hareketli_skor == 0.0, "hareketli kamerada 1.2 normal olmalıydı"


# ══════════════════════════════════════════════════════════════
#  Kişi sayısı
# ══════════════════════════════════════════════════════════════


class TestKisiSayisi:
    def test_kamera_normaline_gore_kalabalik(self) -> None:
        profil = KameraNormali(camera="cam-01")
        _egit(profil, n=PROFIL_ASGARI_ORNEK, x=640.0, y=700.0)
        for i in range(500):
            profil.kare_ogren(3 + (i % 3))  # tipik 3-5 kişi

        assert profil.kisi_skoru(4)[0] == 0.0  # normal
        assert profil.kisi_skoru(40)[0] > 0.0  # olağandışı


# ══════════════════════════════════════════════════════════════
#  Kalıcılık
# ══════════════════════════════════════════════════════════════


class TestKalicilik:
    def test_profil_gidip_geliyor(self, tmp_path: Path) -> None:
        """⚠ Profil kaybı = sistem körlüğü.

        Yeniden başlatmada yüklenmezse öğrenme sıfırlanır ve sistem
        saatlerce hiçbir şeyi olağandışı sayamaz.
        """
        depo = NormalProfilDeposu(tmp_path)
        profil = depo.al("cam-01")
        for i in range(PROFIL_ASGARI_ORNEK):
            profil.ogren(640.0, 700.0, W, H, 0.5 + (i % 5) * 0.02, 0.0)
        profil.kare_ogren(4)

        # `kaydet` aralık koruması var; ilk çağrıyı zorlamak için sıfırla
        assert depo.kaydet(aralik_s=0.0) == 1

        # Yeni bir depo — diskten yüklemeli
        yeni = NormalProfilDeposu(tmp_path)
        geri = yeni.al("cam-01")

        assert geri.hazir
        assert geri.toplam_ornek == profil.toplam_ornek
        assert int(geri.ziyaret.sum()) == int(profil.ziyaret.sum())
        # Öğrenilen normal korunmuş olmalı: aynı gözlem yine normal
        assert geri.skorla(640.0, 700.0, W, H, 0.5, 0.0)[0] == 0.0

    def test_bozuk_profil_dosyasi_COKMEYE_yol_acmiyor(self, tmp_path: Path) -> None:
        """Bozuk profil sistemi durdurmamalı — sıfırdan öğrensin."""
        (tmp_path / "cam-01.json").write_text("{bozuk json", encoding="utf-8")
        depo = NormalProfilDeposu(tmp_path)
        profil = depo.al("cam-01")
        assert profil.toplam_ornek == 0  # sıfırdan başladı, patlamadı

    def test_kaydet_araligi_diski_yormuyor(self, tmp_path: Path) -> None:
        """Her karede yazmak diski boşuna yorar; profil yavaş değişir."""
        depo = NormalProfilDeposu(tmp_path)
        depo.al("cam-01")
        assert depo.kaydet(aralik_s=0.0) == 1
        assert depo.kaydet(aralik_s=3600.0) == 0  # aralık dolmadı


# ══════════════════════════════════════════════════════════════
#  Sayısal kararlılık
# ══════════════════════════════════════════════════════════════


def test_welford_varyansi_NEGATIF_cikmiyor() -> None:
    """⚠ Naif formülün (Σx²/n − ort²) katastrofik iptal sorunu.

    Büyük ve birbirine yakın sayılarda naif yöntem negatif varyans
    üretebilir; karekökü alınınca NaN çıkar ve tüm skorlar sessizce
    bozulur. Welford bu sorunu yaşamıyor.
    """
    profil = KameraNormali(camera="cam-01")
    # Büyük taban + küçük değişim: naif formülün en çok zorlandığı durum
    for i in range(1000):
        profil.ogren(640.0, 700.0, W, H, 1e6 + (i % 3) * 0.001, 0.0)

    w = profil.hiz[(profil._hucre(640.0, 700.0, W, H)[1], profil._hucre(640.0, 700.0, W, H)[0])]
    assert w.varyans >= 0.0
    assert not math.isnan(w.sapma)


def test_kadraj_disi_gozlem_yok_sayiliyor() -> None:
    """Koordinat kadraj dışındaysa profile yazılmamalı."""
    profil = KameraNormali(camera="cam-01")
    profil.ogren(-50.0, 700.0, W, H, 0.5, 0.0)
    profil.ogren(640.0, 5000.0, W, H, 0.5, 0.0)
    assert profil.toplam_ornek == 0


@pytest.mark.parametrize("hiz", [None, 0.0, 10.0])
def test_hiz_yoksa_veya_ucta_COKMUYOR(hiz: float | None) -> None:
    """Poz kademesi kapalıysa hız None gelir — patlamamalı."""
    profil = KameraNormali(camera="cam-01")
    profil.ogren(640.0, 700.0, W, H, hiz, None)
    assert profil.toplam_ornek == 1
