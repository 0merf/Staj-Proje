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


def akis(
    kareler: list[tuple[float, list[tuple[int, float, bool, bool]]]],
    esikler: object | None = None,
) -> list:
    """Sahneyi KARE KARE besler — canlı worker'ın yaptığı gibi.

    ⚠ NEDEN `sahne` YETMİYOR
    `sahne` tüm kareleri depoya yükleyip skorlayıcıyı BİR KEZ çağırıyor.
    Skor üstel hareketli ortalamayla yumuşatıldığı için (EMA_ALFA=0.4)
    tek çağrıda ham değerin ancak %40'ı görünür — skor hiç oturmaz.

    Bu, bir regresyon testini sessizce işe yaramaz hâle getirmişti:
    "yan yana geçen iki yaya" senaryosu eski ayarla 0.178 ölçülüyordu ve
    testi geçiyordu, oysa aynı senaryonun oturmuş değeri 0.44 — dikkat
    eşiğinin üstünde. Test yeşildi ama hatayı görmüyordu.

    Ders: zamansal yumuşatması olan bir sistemi tek adımda test etmek,
    sistemi test etmemektir.
    """
    depo = PencereDeposu()
    skorlayici = (
        TirmanmaSkorlayici(esikler)  # type: ignore[arg-type]
        if esikler is not None
        else TirmanmaSkorlayici()
    )
    son: list = []
    for ts, kisiler in kareler:
        for tid, x, kol, bakis in kisiler:
            kp = iskelet(x, kol_yukari=kol, bakis_sag=bakis)
            k = kutu(x)
            depo.ekle(
                "cam-01",
                tid,
                Ornek(
                    ts=ts, bbox=k, kp=kp,
                    olcek=sk.govde_boyu(kp, k), ayak=sk.ayak_noktasi(k),
                ),
            )
        pencereler = depo.kamera_pencereleri("cam-01")
        son = skorlayici.degerlendir(
            "cam-01",
            [cikar(p) for p in pencereler.values()],
            pair.kamera_ciftleri(pencereler),
            ts,
        )
    return son


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

    def test_YAN_YANA_GECEN_iki_yaya_DIKKAT_bile_vermiyor(self) -> None:
        """⚠ REGRESYON — 26.08.2026'da üretimde patlayan senaryo bu.

        Ölçüm: **26.4 yanlış alarm/kamera-saat**, hedef ≤3 (K7). Kırılımda
        en büyük kalem saldırganlıktı ve tek başına Oxford caddesinde
        (cam-09) 10 dakikada 12 uyarı çıkıyordu. Orada kavga yok; sadece
        yaya trafiği var.

        Sebep testle değil ölçümle bulundu
        (`benchmarks/features_20260826-175748.json`): hiçbir bileşenin
        ölü bölgesi yoktu, sıradan bir yaya bileşenlerin çoğunu yarıdan
        fazla dolduruyordu ve toplam 0.55'i (uyarı) aşıyordu.

        Bu test o senaryoyu sabitliyor: iki kişi birbirine doğru NORMAL
        hızda yürüyor, yan yana geçiyorlar, kolları yürüyüş temposunda
        sallanıyor. Kavga yok — **dikkat seviyesi bile çıkmamalı.**

        Testin sabitlediği şey bir sayı değil, bir ilke: normal davranış
        kanıt değildir.
        """
        from sentinel.analytics.aggression import ESIK_DIKKAT_GIR

        # Ölçülen normal yaya: gövde hızı p50 = 0.30 gövde/sn.
        # Gövde boyu ~160 px olduğuna göre kare başına (0.25 sn)
        # ~12 px. İkisi karşılıklı geliyor → kapanma ~24 px/kare.
        kareler = []
        sol, sag = 380.0, 560.0
        for i, ts in enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]):
            # Kollar yürüyüş temposunda: her karede yön değiştirmiyor,
            # iki karede bir — gerçek yürüyüş bileği böyle salınır.
            kol = (i // 2) % 2 == 1
            kareler.append((ts, [(1, sol, kol, True), (2, sag, kol, False)]))
            sol += 12.0
            sag -= 12.0
        # ⚠ Kare kare besleniyor: EMA'nın oturması şart (bkz. `akis`).
        skorlar = akis(kareler)
        assert skorlar

        en_yuksek = max(s.skor for s in skorlar)
        assert en_yuksek < ESIK_DIKKAT_GIR, (
            "sıradan yürüyen iki yaya dikkat eşiğini bile aşmamalı, "
            f"skor={en_yuksek:.3f} eşik={ESIK_DIKKAT_GIR}"
        )

    def test_ETKILESIM_KAPISI_yalniz_kisiyi_bastiriyor(self) -> None:
        """Kapı açık/kapalı aynı sahnede kıyaslanıyor.

        Yalnız bir kişinin şiddetli hareketi kapı açıkken belirgin
        biçimde daha düşük skor almalı. Kapının VARLIK sebebi bu;
        kapatılırsa test kırmızıya döner ve sebep görünür olur.
        """
        from dataclasses import replace

        from sentinel.analytics.aggression import VARSAYILAN

        kareler = [
            (ts, [(1, 400.0, i % 2 == 1, True)])
            for i, ts in enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25])
        ]
        acik = akis(kareler, VARSAYILAN)
        kapali = akis(kareler, replace(VARSAYILAN, etkilesim_kapisi=False))

        assert acik and kapali
        assert acik[0].skor < kapali[0].skor, (
            "etkileşim kapısı yalnız kişinin skorunu düşürmeliydi"
        )
        assert acik[0].bilesenler["etkilesim"] == 0.0, (
            "çifti olmayan kişide etkileşim sıfır olmalı"
        )


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
