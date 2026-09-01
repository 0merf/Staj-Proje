"""Füzyon katmanı — beş sinyalin birleştirilmesi (PLAN §6.6).

⚠ FÜZYONUN KENDİNE ÖZGÜ HATA BİÇİMİ
-----------------------------------
Diğer modüllerde hata "yanlış cevap" biçiminde çıkar. Füzyonda hata
**karmaşıklığın karşılığını vermemesi** biçiminde çıkar: skor üretilir,
makul görünür, ama tek bir bileşenden daha iyi ayırt etmez. O zaman
katman bir şey eklemiyor, yalnızca bir katman ekliyor.

Bu yüzden testler iki şeye bakıyor:
  · ağırlıklı toplam doğru mu hesaplanıyor (mekanik)
  · BİRLEŞTİRME gerçekten fark yaratıyor mu (amaç)
"""

from __future__ import annotations

import pytest

from sentinel.analytics import fusion
from sentinel.analytics.fusion import RiskFuzyonu, Sinyaller


class TestAgirlikliToplam:
    def test_agirliklar_PLAN_ile_ayni_ve_toplami_bir(self) -> None:
        """⚠ Ağırlıkların toplamı 1.00 olmalı.

        Olmasaydı risk skoru 0-1 aralığından çıkar ve eşikler anlamsız
        hâle gelirdi. Ayrıca değerler PLAN §6.6'daki başlangıç
        ağırlıklarıyla birebir aynı — koddan sapan bir ağırlık, planla
        gerçek arasındaki ilk çatlak olurdu (mimari kural 0).
        """
        toplam = (
            fusion.A_SALDIRGANLIK
            + fusion.A_ANOMALI
            + fusion.A_KURAL
            + fusion.A_IFADE
            + fusion.A_KALABALIK
        )
        assert toplam == pytest.approx(1.0)
        assert fusion.A_SALDIRGANLIK == 0.40
        assert fusion.A_IFADE == 0.10, "ifade ağırlığı bilimsel belirsizlik yüzünden düşük"

    def test_tum_sinyaller_tam_ise_risk_bir(self) -> None:
        assert Sinyaller(1.0, 1.0, 1.0, 1.0, 1.0).ham_risk() == pytest.approx(1.0)

    def test_hicbir_sinyal_yoksa_risk_sifir(self) -> None:
        assert Sinyaller().ham_risk() == 0.0

    def test_saldirganlik_en_agir_bilesen(self) -> None:
        """En spesifik sinyal en çok ağırlığı almalı."""
        yalniz_sald = Sinyaller(saldirganlik=1.0).ham_risk()
        for digeri in (
            Sinyaller(anomali=1.0),
            Sinyaller(kural=1.0),
            Sinyaller(ifade=1.0),
            Sinyaller(kalabalik=1.0),
        ):
            assert yalniz_sald > digeri.ham_risk()


class TestBirlestirme:
    """⚠ Füzyonun VARLIK SEBEBİ bu sınıfta sınanıyor."""

    def _oturt(self, f: RiskFuzyonu, s: Sinyaller, *, tur: int = 12) -> float:
        """EMA oturana kadar besler, son riski döndürür.

        ⚠ Tek çağrı yetmiyor: EMA_ALFA=0.4 ile ilk çağrıda ham değerin
        yalnızca %40'ı görünür. Bu tuzağa `test_aggression` ve
        `test_rules` içinde birer kez düşüldü; zamansal yumuşatması
        olan bir sistemi tek adımda test etmek, sistemi test etmemek.
        """
        risk = 0.0
        for i in range(tur):
            sonuc = f.degerlendir("cam-01", 1, s, tamlik=1.0, simdi=float(i))
            assert sonuc is not None
            risk = sonuc.risk
        return risk

    def test_TEK_GUCLU_sinyal_esigi_ASMIYOR(self) -> None:
        """⚠ En kritik test — füzyonun neden var olduğu.

        Katman A tek başına 0.9 diyorsa bu hâlâ istatistiksel bir
        sapma. Füzyonda 0.25 × 0.9 = 0.225 eder ve uyarı eşiğini
        (0.35) aşmaz. Aşsaydı füzyon, Katman A'nın kendi alarmının
        kopyasından ibaret olurdu.
        """
        risk = self._oturt(RiskFuzyonu(), Sinyaller(anomali=0.9))
        assert risk < fusion.ESIK_UYARI_GIR

    def test_IKI_ORTA_sinyal_esigi_ASIYOR(self) -> None:
        """İkisi de tek başına yetersiz, birlikte anlamlı.

        "3σ hızlı" tek başına gürültü; "3σ hızlı VE yanındakine hızla
        yaklaşıyor" bir olaydır.
        """
        risk = self._oturt(RiskFuzyonu(), Sinyaller(anomali=0.7, saldirganlik=0.5))
        assert risk >= fusion.ESIK_UYARI_GIR

    def test_katkida_bulunan_sinyal_SAYILIYOR(self) -> None:
        """Tek sinyalli 0.4 ile üç sinyalli 0.4 aynı şey değil."""
        f = RiskFuzyonu()
        tek = f.degerlendir(
            "cam-01", 1, Sinyaller(saldirganlik=0.9), tamlik=1.0, simdi=0.0
        )
        uc = f.degerlendir(
            "cam-01", 2,
            Sinyaller(saldirganlik=0.4, anomali=0.4, kural=0.4),
            tamlik=1.0, simdi=0.0,
        )
        assert tek is not None and uc is not None
        assert tek.katkida_bulunan == 1
        assert uc.katkida_bulunan == 3

    def test_GURULTU_seviyesindeki_sinyal_katki_SAYILMIYOR(self) -> None:
        """0.05'lik bir sinyal "katkıda bulundu" sayılmamalı.

        Sayılsaydı, tek gerçek sinyalli bir an "beş sinyal birden" gibi
        görünürdü ve `katkida_bulunan` alanı yanıltıcı olurdu — oysa o
        alan tam da güveni artırmak için var.
        """
        f = RiskFuzyonu()
        sonuc = f.degerlendir(
            "cam-01", 1,
            Sinyaller(saldirganlik=0.9, anomali=0.05, kural=0.02),
            tamlik=1.0, simdi=0.0,
        )
        assert sonuc is not None
        assert sonuc.katkida_bulunan == 1


class TestGuvenilirlikKapisi:
    def test_DUSUK_TAMLIK_skorlanmiyor(self) -> None:
        f = RiskFuzyonu()
        assert (
            f.degerlendir("cam-01", 1, Sinyaller(saldirganlik=1.0), tamlik=0.1, simdi=0.0)
            is None
        )

    def test_KIMLIKSIZ_iz_skorlanmiyor(self) -> None:
        f = RiskFuzyonu()
        assert (
            f.degerlendir("cam-01", -1, Sinyaller(saldirganlik=1.0), tamlik=1.0, simdi=0.0)
            is None
        )


class TestHisterezis:
    def test_yukari_yonde_histerezis_YOK(self) -> None:
        """Ani sıçrama anında alarma çıkmalı.

        Merdiven gibi çıkmak erken uyarı avansını (K8) doğrudan yer —
        saldırganlık modülünde aynı hata bir kez yapıldı ve test
        ortaya çıkardı.
        """
        assert RiskFuzyonu._seviye(fusion.ESIK_ALARM_GIR + 0.1, "sakin") == "alarm"

    def test_asagi_yonde_histerezis_VAR(self) -> None:
        """Çıkma eşiğinin üstünde kaldıkça seviye korunuyor — panel titremesin."""
        arada = (fusion.ESIK_UYARI_CIK + fusion.ESIK_UYARI_GIR) / 2
        assert RiskFuzyonu._seviye(arada, "uyari") == "uyari"
        assert RiskFuzyonu._seviye(fusion.ESIK_UYARI_CIK - 0.01, "uyari") == "sakin"

    def test_cikma_esikleri_girme_esiklerinden_DUSUK(self) -> None:
        """Tersi olsaydı histerezis değil kararsızlık olurdu."""
        assert fusion.ESIK_UYARI_CIK < fusion.ESIK_UYARI_GIR
        assert fusion.ESIK_ALARM_CIK < fusion.ESIK_ALARM_GIR


class TestBudama:
    def test_eski_izler_temizleniyor(self) -> None:
        f = RiskFuzyonu()
        f.degerlendir("cam-01", 1, Sinyaller(saldirganlik=0.5), tamlik=1.0, simdi=0.0)
        assert f.aktif_iz == 1
        assert f.buda(simdi=1000.0) == 1
        assert f.aktif_iz == 0
