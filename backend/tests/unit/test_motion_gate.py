"""KADEME 0 hareket filtresi kararları.

⚠ NEDEN ÖNEMLİ
--------------
Bu filtre 20 kamerayı tek GPU'da döndürebilmemizin sebebi. İki yönde de
bozulabilir ve **her iki bozulma da sessizdir**:

  · Fazla geçirirse → GPU bütçesi patlar, sistem yetişemez
  · Fazla elerse    → olaylar hiç görülmez (en tehlikelisi)

İkincisi özellikle sinsi: sistem "sağlıklı" görünür, FPS iyidir, hiçbir
hata çıkmaz — sadece kavgayı kaçırmıştır.
"""

from __future__ import annotations

import numpy as np
import pytest

from sentinel.ingest.motion_gate import GateReason, MotionGate

WARMUP = 5
BOYUT = (720, 1280, 3)


def _sabit(deger: int = 40) -> np.ndarray:
    """Tamamen düz kare — hareket yok."""
    return np.full(BOYUT, deger, dtype=np.uint8)


def _hareketli(offset: int) -> np.ndarray:
    """Karenin ortasında yer değiştiren parlak bir dikdörtgen."""
    kare = _sabit()
    x = 100 + offset * 40
    kare[300:500, x : x + 200] = 250
    return kare


def _isit(gate: MotionGate, ts_baslangic: float = 0.0) -> float:
    """Arka plan modelini oturtur, ısınma karelerini tüketir.

    MOG2 ilk karelerde her şeyi ön plan sanar; `warmup_frames` bu yüzden
    var. Testler ısınma SONRASI davranışa bakmalı.
    """
    ts = ts_baslangic
    for _ in range(WARMUP + 15):
        gate.evaluate(_sabit(), ts)
        ts += 0.25
    return ts


@pytest.fixture
def gate() -> MotionGate:
    return MotionGate(threshold=0.005, refresh_interval_s=5.0, warmup_frames=WARMUP)


def test_isinma_sirasinda_HER_KARE_geciyor(gate: MotionGate) -> None:
    """Arka plan modeli öğrenene kadar eleme yapılmamalı.

    Bu sırada elemek, sistemin ilk saniyelerinde gerçek olayları
    kaçırmak demek olurdu.
    """
    for i in range(WARMUP):
        karar = gate.evaluate(_sabit(), i * 0.25)
        assert karar.process
        assert karar.reason is GateReason.WARMUP


def test_duragan_sahne_ELENIYOR(gate: MotionGate) -> None:
    """Filtrenin varlık sebebi.

    `cam-test-static` tam olarak bunu doğrulamak için var (PLAN §5.1).
    """
    ts = _isit(gate)

    kararlar = []
    for _ in range(10):
        ts += 0.25  # yenileme aralığından (5 sn) kısa
        kararlar.append(gate.evaluate(_sabit(), ts))

    elenen = [k for k in kararlar if k.reason is GateReason.IDLE]
    assert len(elenen) >= 8, "durağan sahnede karelerin çoğu elenmeliydi"
    assert all(not k.process for k in elenen)


def test_hareket_GECIRILIYOR(gate: MotionGate) -> None:
    """Elemenin öbür yüzü: gerçek hareket kaçırılmamalı."""
    ts = _isit(gate)

    gecen = 0
    for offset in range(1, 8):
        ts += 0.25
        karar = gate.evaluate(_hareketli(offset), ts)
        if karar.reason is GateReason.MOTION:
            gecen += 1

    assert gecen >= 5, "hareket eden nesne filtreyi geçmeliydi"


def test_zorunlu_yenileme_karesi_geliyor(gate: MotionGate) -> None:
    """⚠ Kadrajda hareketsiz duran kişi kaybolmasın diye.

    Oturan/bekleyen biri arka plana karışır ve filtre onu eler; takip
    kimliği kaybolur ve kişi "yok olur". N saniyede bir zorunlu tam
    analiz bunu önler.
    """
    ts = _isit(gate)

    # Yenileme aralığından uzun bir sessizlik
    ts += 6.0
    karar = gate.evaluate(_sabit(), ts)

    assert karar.process
    assert karar.reason is GateReason.REFRESH


def test_yenileme_gecince_sayac_sifirlaniyor(gate: MotionGate) -> None:
    """Yenileme karesi geçtikten hemen sonra tekrar yenileme olmamalı.

    Olsaydı filtre etkisiz kalır, her kare "yenileme" diye geçerdi.
    """
    ts = _isit(gate)

    ts += 6.0
    assert gate.evaluate(_sabit(), ts).reason is GateReason.REFRESH

    ts += 0.25
    assert gate.evaluate(_sabit(), ts).reason is GateReason.IDLE


def test_esik_yukseltilince_daha_cok_eleniyor() -> None:
    """Eşik gerçekten bir kontrol düğmesi mi, yoksa süs mü?

    Aynı görüntü dizisi iki farklı eşikten geçiriliyor — tek değişen
    parametre. (P-27'deki kontrollü deney deseni.)
    """
    kareler = [_hareketli(i) for i in range(1, 9)]

    def gecen_sayisi(esik: float) -> int:
        g = MotionGate(threshold=esik, refresh_interval_s=999.0, warmup_frames=WARMUP)
        ts = _isit(g)
        n = 0
        for kare in kareler:
            ts += 0.25
            if g.evaluate(kare, ts).reason is GateReason.MOTION:
                n += 1
        return n

    assert gecen_sayisi(0.001) >= gecen_sayisi(0.5)


def test_on_plan_orani_gecerli_araliktan_cikmiyor(gate: MotionGate) -> None:
    """Oran bir yüzde; 0-1 dışına çıkarsa eşik karşılaştırması anlamsızlaşır."""
    ts = _isit(gate)
    for offset in range(1, 5):
        ts += 0.25
        karar = gate.evaluate(_hareketli(offset), ts)
        assert 0.0 <= karar.foreground_ratio <= 1.0


def test_kaynak_cozunurlugu_karari_degistirmiyor() -> None:
    """Filtre 320×180'e küçültüyor; kaynak boyut sonucu etkilememeli.

    Kameralar farklı çözünürlükte (1280×720, 960×720, 900×720) ve
    hepsinin aynı eşikle çalışması gerekiyor.
    """
    sonuclar = []
    for genislik, yukseklik in [(1280, 720), (960, 720), (640, 360)]:
        g = MotionGate(threshold=0.005, refresh_interval_s=999.0, warmup_frames=WARMUP)
        ts = 0.0
        for _ in range(WARMUP + 15):
            g.evaluate(np.full((yukseklik, genislik, 3), 40, dtype=np.uint8), ts)
            ts += 0.25
        ts += 0.25
        sonuclar.append(
            g.evaluate(np.full((yukseklik, genislik, 3), 40, dtype=np.uint8), ts).reason
        )

    assert len(set(sonuclar)) == 1, f"çözünürlüğe göre karar değişti: {sonuclar}"


def test_her_kamera_KENDI_durumunu_tutuyor() -> None:
    """Filtre durumlu — iki kamera aynı örneği paylaşamaz.

    Paylaşsalardı bir kameranın arka planı diğerininkini bozardı ve
    ikisi de yanlış karar verirdi.
    """
    a = MotionGate(warmup_frames=WARMUP)
    b = MotionGate(warmup_frames=WARMUP)

    for i in range(WARMUP + 3):
        a.evaluate(_sabit(), i * 0.25)

    assert a.frames_seen > b.frames_seen
    assert b.frames_seen == 0
