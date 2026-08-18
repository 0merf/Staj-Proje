"""Letterbox dönüşümü ve TERS dönüşümü.

⚠ NEDEN BU TEST ÖNCELİKLİ
-------------------------
Bu dönüşümün hatası **sessizdir.** Koordinatlar geçerli sayılar olarak
çıkar, sadece yanlış uzaya aittir. Sonuç: kutular tarayıcıda yanlış yere
çizilir ama hiçbir hata mesajı yoktur, hiçbir şey çökmez. Gün 8'de bu
riski fark edip 2240 tespit üzerinde elle doğrulamıştık; bu dosya o
doğrulamayı tekrarlanabilir hâle getiriyor.

Ana özellik (property) şudur: **gidiş-dönüş kayıpsız olmalı.**
Kaynak karedeki bir kutu → model uzayına taşınır → geri getirilir →
başladığı yere (yuvarlama payıyla) dönmelidir.
"""

from __future__ import annotations

import numpy as np
import pytest

from sentinel.core.preprocess import INPUT_SIZE, PAD_COLOR, Letterbox, letterbox, slot_bytes


def _frame(width: int, height: int) -> np.ndarray:
    """Sabit değerli BGR kare — dolgu ile içeriği ayırt edebilmek için."""
    return np.full((height, width, 3), 200, dtype=np.uint8)


# Kamera çiftliğinde gerçekten görülen çözünürlükler (P-18 doğrulaması
# üç farklı kaynak boyut raporlamıştı) + uç durumlar.
SIZES = [
    (1280, 720),  # tipik
    (960, 720),
    (900, 720),
    (720, 1280),  # dikey — dolgu yatayda olmalı
    (640, 640),   # zaten kare — dolgu sıfır
    (100, 3000),  # aşırı ince — en-boy oranı uç durumu
]


@pytest.mark.parametrize(("width", "height"), SIZES)
def test_letterbox_ciktisi_her_zaman_kare_ve_dogru_tip(width: int, height: int) -> None:
    """Batch'e girecek her kare AYNI şekilde olmak zorunda.

    GPU'ya verilen tensör tek parça; kameralar farklı çözünürlükte
    olduğu için hepsi aynı kare tuvale oturtulmalı.
    """
    out, _box = letterbox(_frame(width, height))
    assert out.shape == (INPUT_SIZE, INPUT_SIZE, 3)
    assert out.dtype == np.uint8


@pytest.mark.parametrize(("width", "height"), SIZES)
def test_en_boy_orani_korunuyor(width: int, height: int) -> None:
    """Sıkıştırma DEĞİL dolgulama.

    Bu ders P-14'te pahalıya öğrenildi: kırpıntıları kareye
    sıkıştırdığımızda iskelet başarısı %88 yerine %47 çıkmıştı.
    Aynı hata tam kare için yapılırsa model insan şeklini göremez.
    """
    _out, box = letterbox(_frame(width, height))
    olcekli_genislik = width * box.scale
    olcekli_yukseklik = height * box.scale

    # Ölçeklenmiş boyutlar tuvale sığmalı
    assert olcekli_genislik <= INPUT_SIZE + 1
    assert olcekli_yukseklik <= INPUT_SIZE + 1
    # En az bir kenar tuvali doldurmalı, yoksa gereksiz küçültme var
    assert max(olcekli_genislik, olcekli_yukseklik) >= INPUT_SIZE - 1
    # Oran korunmuş mu
    assert olcekli_genislik / olcekli_yukseklik == pytest.approx(width / height, rel=1e-2)


def test_dolgu_notr_gri_ve_icerik_ortalanmis() -> None:
    """Dolgu rengi Ultralytics'in kullandığı 114 olmalı.

    Model bu tonu "içerik değil" olarak görmeye alışkın. Siyah (0)
    dolgu gerçek bir karanlık bölge gibi görünürdü.
    """
    out, box = letterbox(_frame(1280, 720))

    # 1280×720 yatay → dolgu üstte ve altta
    assert box.pad_y > 0
    assert box.pad_x == 0
    assert out[0, 0].tolist() == [PAD_COLOR] * 3          # üst dolgu
    assert out[INPUT_SIZE - 1, 0].tolist() == [PAD_COLOR] * 3  # alt dolgu
    assert out[INPUT_SIZE // 2, INPUT_SIZE // 2].tolist() == [200] * 3  # içerik


@pytest.mark.parametrize(("width", "height"), SIZES)
def test_gidis_donus_kutuyu_baslangic_yerine_getiriyor(width: int, height: int) -> None:
    """⚠ ASIL TEST — sessiz hatayı yakalayan budur.

    Kaynak kutu → model uzayı → geri. Başladığı yere dönmeli.
    Bu tutmazsa kutular tarayıcıda yanlış yere çizilir ve HİÇBİR
    hata mesajı çıkmaz.
    """
    _out, box = letterbox(_frame(width, height))

    # Karenin farklı bölgelerinden kutular (sol üst, orta, sağ alt)
    kaynak_kutular = [
        (0.0, 0.0, width / 4, height / 4),
        (width / 3, height / 3, 2 * width / 3, 2 * height / 3),
        (width * 0.7, height * 0.7, float(width), float(height)),
    ]

    for x1, y1, x2, y2 in kaynak_kutular:
        # Kaynak → model uzayı (letterbox'ın uyguladığı dönüşümün aynısı)
        mx1 = x1 * box.scale + box.pad_x
        my1 = y1 * box.scale + box.pad_y
        mx2 = x2 * box.scale + box.pad_x
        my2 = y2 * box.scale + box.pad_y

        # Model uzayı → kaynak (üretimde kullanılan ters dönüşüm)
        geri = box.to_source_box(mx1, my1, mx2, my2)

        assert geri[0] == pytest.approx(x1, abs=1.0)
        assert geri[1] == pytest.approx(y1, abs=1.0)
        assert geri[2] == pytest.approx(x2, abs=1.0)
        assert geri[3] == pytest.approx(y2, abs=1.0)


def test_ters_donusum_kaynak_sinirlarina_kirpiyor() -> None:
    """Model dolgu alanına taşan bir kutu üretirse negatif koordinat olurdu.

    Dolgu gri bir bölge ve model orada bir şey "görebilir". Kırpma
    olmasa tarayıcıya negatif x/y giderdi.
    """
    _out, box = letterbox(_frame(1280, 720))

    # Tuvalin tam köşeleri — 1280×720'de üst/alt dolgu bölgesi
    x1, y1, x2, y2 = box.to_source_box(0.0, 0.0, float(INPUT_SIZE), float(INPUT_SIZE))
    assert 0.0 <= x1 <= 1280
    assert 0.0 <= y1 <= 720
    assert 0.0 <= x2 <= 1280
    assert 0.0 <= y2 <= 720


def test_hiz_donusumune_dolgu_EKLENMEZ() -> None:
    """Hız bir FARK — sabit kayma sadeleşir, yalnızca ölçek kalır.

    Buraya dolgu payı eklenseydi hız vektörü sistematik olarak yanlış
    olur ve tarayıcıdaki ara değerleme kutuları kaydırırdı.
    """
    _out, box = letterbox(_frame(1280, 720))
    assert box.pad_y > 0  # bu karede dolgu gerçekten var

    model_uzayinda_hiz = 100.0
    kaynakta = box.to_source_length(model_uzayinda_hiz)

    assert kaynakta == pytest.approx(model_uzayinda_hiz / box.scale)
    # Dolgu eklenmiş olsaydı sonuç bundan farklı çıkardı
    assert kaynakta != pytest.approx((model_uzayinda_hiz - box.pad_y) / box.scale)


def test_valkey_alanlarina_yazip_geri_okuma() -> None:
    """Letterbox kaydı Valkey'den düz string olarak geçiyor.

    Alan adı ya da tip dönüşümü bozulursa kutular yine sessizce yanlış
    yere çizilir — `from_fields` None dönerse ters dönüşüm hiç yapılmaz.
    """
    _out, box = letterbox(_frame(960, 720))

    geri = Letterbox.from_fields(box.to_fields())
    assert geri is not None
    assert geri.source_width == box.source_width
    assert geri.source_height == box.source_height
    assert geri.pad_x == box.pad_x
    assert geri.pad_y == box.pad_y
    assert geri.scale == pytest.approx(box.scale, rel=1e-5)


def test_on_islemesiz_eski_mesaj_None_donuyor() -> None:
    """Ön işleme yapılmamış (eski sürüm) mesajlar bozulmamalı.

    `letterbox` alanı yoksa ters dönüşüm atlanmalı, patlamamalı.
    """
    assert Letterbox.from_fields({"cam": "cam-01", "seq": "5"}) is None


def test_slot_boyutu_letterbox_ciktisiyla_uyusuyor() -> None:
    """Paylaşımlı bellek slotu kareyi tam almalı.

    Uyuşmazsa `FramePool.write` "kare slota sığmıyor" diye patlar ya da
    daha kötüsü, slot büyükse bellek boşa gider (48 slot × fark).
    """
    out, _box = letterbox(_frame(1280, 720))
    assert out.nbytes == slot_bytes()
