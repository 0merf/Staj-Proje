"""Saldırganlık tırmanma skoru — PLAN.md §6.5.

⚠ NEDEN BU TESTLER KRİTİK
-------------------------
Bu skor operatöre "burada kavga çıkıyor olabilir" dedirtiyor. Yanlış
olduğunda iki yönde de pahalı:

  · fazla duyarlı → operatör alarmları kapatır, sistem işe yaramaz
  · fazla sağır   → gerçek olay kaçar, sistemin varlık sebebi kalmaz

Ve hata SESSİZDİR: skor üretilir, makul görünür, sadece yanlış sebeple
yükselmiştir.

Bu yüzden testler "skor yükseliyor mu" diye bakmıyor — **doğru sebeple**
yükseliyor mu diye bakıyor. En önemlisi ayrımlar:

    hızlı bilek AMA yalnız      → egzersiz, skor DÜŞÜK olmalı
    hızlı bilek + yakın + dönük → kavga örüntüsü, skor YÜKSEK
"""

from __future__ import annotations

import numpy as np
import pytest

from sentinel.analytics.aggression import (
    ESIK_UYARI_GIR,
    TirmanmaSkorlayici,
)
from sentinel.analytics.features import pair
from sentinel.analytics.features import skeleton as sk
from sentinel.analytics.features.person import cikar
from sentinel.analytics.features.window import Ornek, PencereDeposu

W, H = 1280.0, 720.0


def iskelet(x: float, *, kol_yukari: bool = False, bakis_sag: bool = True) -> np.ndarray:
    """Belirli bir x konumunda duran kişi.

    `bakis_sag`: burun omuz merkezinin sağında → sağa dönük.
    Karşılıklı bakış testinde iki kişiyi birbirine döndürmek için.
    """
    kp = np.zeros((17, 3), dtype=np.float64)
    kp[:, 2] = 0.9
    yerler = {
        sk.BURUN: (x + (8 if bakis_sag else -8), 300),
        sk.SOL_OMUZ: (x - 15, 320),
        sk.SAG_OMUZ: (x + 15, 320),
        sk.SOL_DIRSEK: (x - 20, 350),
        sk.SAG_DIRSEK: (x + 20, 350),
        sk.SOL_BILEK: (x - 22, 290 if kol_yukari else 380),
        sk.SAG_BILEK: (x + 22, 380),
        sk.SOL_KALCA: (x - 10, 390),
        sk.SAG_KALCA: (x + 10, 390),
        sk.SOL_AYAK: (x - 12, 460),
        sk.SAG_AYAK: (x + 12, 460),
    }
    for i, (px, py) in yerler.items():
        kp[i][0], kp[i][1] = px, py
    return kp


def kutu(x: float) -> tuple[float, float, float, float]:
    return (x - 25, 300.0, x + 25, 460.0)


def sahne(
    kareler: list[tuple[float, list[tuple[int, float, bool, bool]]]],
) -> tuple[list, list]:
    """Zaman serisi bir sahne kurar.

    Her kare: (ts, [(track_id, x, kol_yukari, bakis_sag), ...])
    Dönen: (kişi özellikleri, çift özellikleri) — son kareye ait.
    """
    depo = PencereDeposu()
    for ts, kisiler in kareler:
        for tid, x, kol, bakis in kisiler:
            kp = iskelet(x, kol_yukari=kol, bakis_sag=bakis)
            k = kutu(x)
            depo.ekle(
                "cam-01",
                tid,
                Ornek(
                    ts=ts,
                    bbox=k,
                    kp=kp,
                    olcek=sk.govde_boyu(kp, k),
                    ayak=sk.ayak_noktasi(k),
                ),
            )
    pencereler = depo.kamera_pencereleri("cam-01")
    return (
        [cikar(p) for p in pencereler.values()],
        pair.kamera_ciftleri(pencereler),
    )


# ══════════════════════════════════════════════════════════════
#  ⭐ Asıl ayrım: yalnız mı, etkileşimde mi?
# ══════════════════════════════════════════════════════════════


class TestYalnizVsEtkilesim:
    def test_YALNIZ_kisi_hizli_bilek_ALARM_VERMIYOR(self) -> None:
        """⚠ En kritik test.

        Hızlı bilek hareketi tek başına saldırganlık değildir: egzersiz,
        el sallama, oyun aynı sinyali verir. Bu test tutmazsa sistem
        spor salonunda alarm yağdırır.
        """
        kisiler, ciftler = sahne(
            [
                (0.00, [(1, 400.0, False, True)]),
                (0.25, [(1, 400.0, True, True)]),
                (0.50, [(1, 400.0, False, True)]),
                (0.75, [(1, 400.0, True, True)]),
                (1.00, [(1, 400.0, False, True)]),
                (1.25, [(1, 400.0, True, True)]),
            ]
        )
        assert ciftler == [], "yalnız kişide çift olmamalı"

        skorlar = TirmanmaSkorlayici().degerlendir("cam-01", kisiler, ciftler, 1.25)
        assert skorlar
        assert skorlar[0].skor < ESIK_UYARI_GIR, (
            f"yalnız kişi uyarı eşiğini aşmamalı, skor={skorlar[0].skor:.2f}"
        )
        # Yakınlık bileşeni SIFIR olmalı — kimse yok
        assert skorlar[0].bilesenler["yakinlik"] == 0.0

    def test_YAKIN_ve_KARSILIKLI_kisilerde_skor_YUKSEK(self) -> None:
        """Aynı bilek hareketi, bu sefer karşısında biri var.

        İkisi birbirine dönük (biri sağa, diğeri sola bakıyor) ve yakın.
        Skor yalnız hâline göre belirgin yüksek olmalı.
        """
        # İki kişi yan yana, ~50 px = ~0.24 gövde boyu
        kareler = []
        for i, ts in enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25]):
            kol = i % 2 == 1
            kareler.append(
                (ts, [(1, 400.0, kol, True), (2, 455.0, kol, False)])
            )
        kisiler, ciftler = sahne(kareler)

        assert ciftler, "yakın iki kişide çift üretilmeliydi"
        skorlar = TirmanmaSkorlayici().degerlendir("cam-01", kisiler, ciftler, 1.25)
        assert skorlar

        en_yuksek = max(s.skor for s in skorlar)
        # Yalnız hâlle karşılaştır
        yalniz_kisiler, yalniz_ciftler = sahne(
            [(ts, [(1, 400.0, i % 2 == 1, True)]) for i, ts in
             enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25])]
        )
        yalniz = TirmanmaSkorlayici().degerlendir(
            "cam-01", yalniz_kisiler, yalniz_ciftler, 1.25
        )
        assert en_yuksek > yalniz[0].skor, (
            "etkileşimli sahne yalnız sahneden yüksek skor almalıydı"
        )
        assert any(s.karsi_taraf is not None for s in skorlar)


# ══════════════════════════════════════════════════════════════
#  Çift özellikleri
# ══════════════════════════════════════════════════════════════


class TestCiftOzellikleri:
    def test_UZAK_cift_hic_hesaplanmiyor(self) -> None:
        """⚠ Kombinatorik patlama koruması.

        17 kişilik sahnede 136 çift var. Uzak çiftler bilgi taşımıyor
        ve hesaplanmaları israf.
        """
        _kisiler, ciftler = sahne(
            [
                (0.0, [(1, 100.0, False, True), (2, 1200.0, False, False)]),
                (0.25, [(1, 100.0, False, True), (2, 1200.0, False, False)]),
            ]
        )
        assert ciftler == []

    def test_YAKLASMA_hizi_NEGATIF_olmali(self) -> None:
        """Negatif = yaklaşıyor. Tırmanmanın en erken sinyali."""
        _kisiler, ciftler = sahne(
            [
                (0.00, [(1, 300.0, False, True), (2, 800.0, False, False)]),
                (0.25, [(1, 320.0, False, True), (2, 760.0, False, False)]),
                (0.50, [(1, 350.0, False, True), (2, 700.0, False, False)]),
                (0.75, [(1, 380.0, False, True), (2, 640.0, False, False)]),
            ]
        )
        assert ciftler
        assert ciftler[0].yaklasma_hizi is not None
        assert ciftler[0].yaklasma_hizi < 0, "yaklaşan çiftte hız negatif olmalı"

    def test_UZAKLASMA_hizi_POZITIF(self) -> None:
        _kisiler, ciftler = sahne(
            [
                (0.00, [(1, 400.0, False, True), (2, 460.0, False, False)]),
                (0.25, [(1, 380.0, False, True), (2, 500.0, False, False)]),
                (0.50, [(1, 350.0, False, True), (2, 560.0, False, False)]),
            ]
        )
        assert ciftler
        assert ciftler[0].yaklasma_hizi is not None
        assert ciftler[0].yaklasma_hizi > 0

    def test_mesafe_GOVDE_BOYUNA_normalize(self) -> None:
        """⚠ Aynı gerçek mesafe, farklı uzaklıkta aynı sayıyı vermeli.

        Piksel kullansaydık kameraya yakın herkes "temas hâlinde"
        görünürdü.
        """
        mesafeler = []
        for olcek in (1.0, 2.0):
            depo = PencereDeposu()
            for ts in (0.0, 0.25):
                for tid, x in ((1, 400.0 * olcek), (2, 460.0 * olcek)):
                    kp = iskelet(x) * np.array([olcek, olcek, 1.0])
                    k = tuple(v * olcek for v in kutu(x / olcek))
                    depo.ekle(
                        "cam-01",
                        tid,
                        Ornek(
                            ts=ts,
                            bbox=k,  # type: ignore[arg-type]
                            kp=kp,
                            olcek=sk.govde_boyu(kp, k),  # type: ignore[arg-type]
                            ayak=sk.ayak_noktasi(k),  # type: ignore[arg-type]
                        ),
                    )
            c = pair.kamera_ciftleri(depo.kamera_pencereleri("cam-01"))
            assert c
            mesafeler.append(c[0].mesafe)

        assert mesafeler[0] == pytest.approx(mesafeler[1], rel=0.15)


# ══════════════════════════════════════════════════════════════
#  Histerezis ve zamansal davranış
# ══════════════════════════════════════════════════════════════


class TestHisterezis:
    def test_seviye_TITREMIYOR(self) -> None:
        """⚠ Girme ve çıkma eşikleri farklı olmasa panel titrerdi.

        Skor eşiğin hemen altına inince seviye HEMEN düşmemeli.
        """
        s = TirmanmaSkorlayici()
        # ⚠ YUKARI YÖNDE HİSTEREZİS YOK: skor bir anda yükselirse
        # seviye de anında yükselmeli. Merdiven gibi çıkmak erken
        # uyarı avansını (K8) doğrudan yerdi.
        assert s._seviye(0.60, "sakin") == "uyari"
        assert s._seviye(0.90, "sakin") == "alarm", "ani sıçrama anında alarm olmalı"
        # 0.45: uyarıdan çıkma eşiği 0.40, hâlâ uyarıda kalmalı
        assert s._seviye(0.45, "uyari") == "uyari"
        # 0.30: çıkma eşiğinin altı → düşüyor
        assert s._seviye(0.30, "uyari") == "dikkat"

    def test_dusuk_tamlik_skorlanmiyor(self) -> None:
        """Saldırganlık iddiası ciddi; iki örnekten üretilmemeli."""
        kisiler, ciftler = sahne(
            [(0.0, [(1, 400.0, False, True), (2, 455.0, False, False)])]
        )
        skorlar = TirmanmaSkorlayici().degerlendir("cam-01", kisiler, ciftler, 0.0)
        assert skorlar == []

    def test_eski_izler_budaniyor(self) -> None:
        s = TirmanmaSkorlayici()
        kisiler, ciftler = sahne(
            [
                (ts, [(1, 400.0, i % 2 == 1, True), (2, 455.0, i % 2 == 1, False)])
                for i, ts in enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25])
            ]
        )
        s.degerlendir("cam-01", kisiler, ciftler, 1.25)
        assert s.aktif_iz > 0
        assert s.buda(simdi=1000.0) > 0
        assert s.aktif_iz == 0


def test_bilesenler_TOPLAM_skoru_aciklamali() -> None:
    """⚠ Açıklanabilirlik: operatör "neden" sorusunun cevabını görmeli.

    Bileşenler eksikse alarm bir kara kutu olur ve operatör güvenmez.
    """
    kisiler, ciftler = sahne(
        [
            (ts, [(1, 400.0, i % 2 == 1, True), (2, 455.0, i % 2 == 1, False)])
            for i, ts in enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25])
        ]
    )
    skorlar = TirmanmaSkorlayici().degerlendir("cam-01", kisiler, ciftler, 1.25)
    assert skorlar
    b = skorlar[0].bilesenler
    for ad in ("yakinlik", "bilek", "yaklasma", "enerji", "durus"):
        assert ad in b, f"{ad} bileşeni eksik"
        assert 0.0 <= b[ad] <= 1.0
