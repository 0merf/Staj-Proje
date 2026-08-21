"""Valkey akışı ve slot havuzu — entegrasyon testleri.

Çalıştırma:
    docker compose up -d valkey
    uv run pytest tests/integration -q

⚠ NEDEN ENTEGRASYON, SAHTE (mock) DEĞİL
---------------------------------------
Buradaki davranışların tamamı **Valkey'in kendi semantiğinden** doğuyor:
tüketici grubunun akış silinince kaybolması, `LPOP`'un atomikliği,
`MAXLEN ~` yaklaşık kırpması. Sahte bir istemci bunları taklit edemez —
zaten taklit edersek test ettiğimiz şey kendi varsayımlarımız olur,
gerçek davranış değil.

P-20 tam olarak böyle bir hataydı: iki bileşen tek başına doğruydu,
**etkileşimleri** yanlıştı. Sahte istemciyle asla yakalanamazdı.
"""

from __future__ import annotations

import uuid

import pytest
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from sentinel.bus.shm import FrameRef
from sentinel.bus.streams import (
    FrameMessage,
    FrameStream,
    SlotAllocator,
    connect,
    get_watched_cameras,
    set_watched_cameras,
)
from sentinel.core.preprocess import Letterbox

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Redis:
    """Valkey bağlantısı. Ayakta değilse test atlanır, KIRMIZI olmaz."""
    try:
        c = connect()
        c.ping()
    except (RedisConnectionError, OSError) as exc:
        pytest.skip(f"Valkey erişilemiyor ({exc}) — `docker compose up -d valkey`")
    return c


@pytest.fixture
def stream(client: Redis) -> FrameStream:
    """Her test kendi akışını kullanır — birbirlerini bozmasınlar."""
    name = f"test.frames.{uuid.uuid4().hex[:8]}"
    s = FrameStream(client, stream=name, maxlen=64)
    yield s
    client.delete(name)


def _mesaj(camera: str = "cam-01", sequence: int = 1) -> FrameMessage:
    return FrameMessage(
        message_id="",
        camera=camera,
        sequence=sequence,
        captured_at=1_755_000_000.5,
        pts=12.25,
        ref=FrameRef(slot=3, height=640, width=640, channels=3),
        motion_ratio=0.042,
        gate_reason="motion",
        letterbox=Letterbox(
            source_width=1280, source_height=720, scale=0.5, pad_x=0, pad_y=140
        ),
    )


# ══════════════════════════════════════════════════════════════
#  Mesaj gidiş-dönüşü
# ══════════════════════════════════════════════════════════════


def test_mesaj_alanlari_kayipsiz_gidip_geliyor(stream: FrameStream) -> None:
    """Valkey Stream alanları DÜZ STRING olmak zorunda.

    Tip dönüşümü bozulursa hata sessizdir: `float("0.5")` çalışır ama
    yanlış alan adı `KeyError` yerine varsayılan değer döndürebilir ve
    kutular yanlış yere çizilir.
    """
    gonderilen = _mesaj()
    stream.publish(gonderilen)
    stream.ensure_group("g1")

    gelen = list(stream.consume("g1", "c1", count=1, block_ms=500))
    assert len(gelen) == 1
    m = gelen[0]

    assert m.camera == gonderilen.camera
    assert m.sequence == gonderilen.sequence
    assert m.captured_at == pytest.approx(gonderilen.captured_at, abs=1e-5)
    assert m.gate_reason == gonderilen.gate_reason
    assert m.ref.slot == gonderilen.ref.slot
    assert m.letterbox is not None
    assert m.letterbox.pad_y == 140
    # Kaynak boyut tarayıcının ölçekleme için muhtaç olduğu bilgi
    assert m.source_size == (1280, 720)


# ══════════════════════════════════════════════════════════════
#  P-20 GERİLEMESİ — hata izolasyonu
# ══════════════════════════════════════════════════════════════


def test_P20_GERILEMESI_akis_silinince_tuketici_COKMUYOR(stream: FrameStream) -> None:
    """⚠ Alım worker'ını yeniden başlatmak çıkarım worker'ını öldürüyordu.

    İki DOĞRU kararın çarpışması:
      1. Havuz sahibi açılışta akışı SİLMEK ZORUNDA (P-10) — yoksa eski
         mesajlardaki geçersiz slot referansları havuzu bozar.
      2. Çıkarım worker'ı akıştan tüketici grubuyla okuyor.

    Valkey'de akışı silmek TÜKETİCİ GRUPLARINI DA siler. Yani (1) her
    yapıldığında (2) ayaklarının altındaki zemini kaybediyordu ve
    `NOGROUP` ile çöküyordu.

    Bir bileşenin NORMAL yeniden başlaması diğerini düşürmemeli
    (PLAN.md §4.2 hata izolasyonu).
    """
    stream.ensure_group("inference")
    stream.publish(_mesaj())
    assert len(list(stream.consume("inference", "w1", count=8, block_ms=200))) == 1

    # Alım worker'ının açılışta yaptığı şey: akışı sıfırla
    stream.reset()

    # ⚠ Kritik an: burada eskiden `NOGROUP` fırlıyor ve worker çöküyordu
    ilk = list(stream.consume("inference", "w1", count=8, block_ms=200))
    assert ilk == [], "grup kaybolduğunda boş dönmeli, patlamamalı"

    # Ve devam edebilmeli — grup sessizce yeniden kurulmuş olmalı
    stream.publish(_mesaj(sequence=2))
    ikinci = list(stream.consume("inference", "w1", count=8, block_ms=500))
    assert len(ikinci) == 1
    assert ikinci[0].sequence == 2


def test_grup_iki_kez_kurulunca_hata_vermiyor(stream: FrameStream) -> None:
    """`BUSYGROUP` yutulmalı — worker yeniden başlatılabilir olmalı."""
    stream.ensure_group("g")
    stream.ensure_group("g")  # patlamamalı


def test_grup_akisin_BASINDAN_basliyor(stream: FrameStream) -> None:
    """⚠ `start_id="0"` bilinçli, varsayılan `"$"` kilitlenmeye yol açar.

    `"$"` yalnızca YENİ mesajları verir. Akışta bekleyen kareler hiç
    okunmaz → slotları geri verilmez → üretici boş slot bulamaz →
    sistem durur (P-10).
    """
    stream.publish(_mesaj(sequence=7))
    stream.ensure_group("sonradan")  # grup mesajdan SONRA kuruluyor

    gelen = list(stream.consume("sonradan", "c", count=8, block_ms=500))
    assert len(gelen) == 1, "gruptan önce yazılmış mesaj da okunmalı"
    assert gelen[0].sequence == 7


def test_ayni_mesaj_iki_tuketiciye_GITMIYOR(stream: FrameStream) -> None:
    """Tüketici grubu iş paylaştırır, yayın yapmaz.

    Aynı kare iki kez işlenirse slot iki kez serbest bırakılır ve havuz
    bozulur — iki kamera aynı slota yazar (P-10 ile aynı sonuç).
    """
    stream.ensure_group("g")
    for i in range(4):
        stream.publish(_mesaj(sequence=i))

    a = list(stream.consume("g", "w1", count=2, block_ms=300))
    b = list(stream.consume("g", "w2", count=2, block_ms=300))

    assert len(a) == 2 and len(b) == 2
    assert {m.sequence for m in a}.isdisjoint({m.sequence for m in b})


def test_kuyruk_SINIRLI_sinirsiz_buyumuyor(stream: FrameStream) -> None:
    """G13 — sınırsız kuyruk = RAM patlaması.

    `MAXLEN ~` yaklaşık kırpar (tam kırpma pahalı), o yüzden tam
    eşitlik değil üst sınır kontrol ediliyor.
    """
    for i in range(400):
        stream.publish(_mesaj(sequence=i))
    assert stream.depth < 400, "akış sınırlanmalıydı"


# ══════════════════════════════════════════════════════════════
#  Slot havuzu — geri basınç
# ══════════════════════════════════════════════════════════════


def test_slot_bitince_None_donuyor_bu_bir_HATA_DEGIL(client: Redis) -> None:
    """Boş slot yoksa `acquire()` None döner — geri basınç sinyali.

    Bu tasarımın bedava getirdiği şey: tüketici yavaşlarsa üretici
    kareyi ATAR. Sınırsız kuyruk yerine kontrollü kare kaybı.
    """
    key = f"test.slots.{uuid.uuid4().hex[:8]}"
    havuz = SlotAllocator(client, slot_count=3, key=key)
    try:
        havuz.reset()
        assert havuz.available == 3

        alinan = [havuz.acquire() for _ in range(3)]
        assert sorted(x for x in alinan if x is not None) == [0, 1, 2]
        assert havuz.available == 0

        # ⚠ Havuz boş — hata değil, geri basınç
        assert havuz.acquire() is None

        havuz.release_many([s for s in alinan if s is not None])
        assert havuz.available == 3
    finally:
        client.delete(key)


def test_ayni_slot_iki_kez_dagitilmiyor(client: Redis) -> None:
    """`LPOP` atomik olmalı — iki kamera aynı slota yazarsa kareler birbirini ezer."""
    key = f"test.slots.{uuid.uuid4().hex[:8]}"
    havuz = SlotAllocator(client, slot_count=20, key=key)
    try:
        havuz.reset()
        alinan = [havuz.acquire() for _ in range(20)]
        assert len(set(alinan)) == 20, "her slot yalnızca bir kez dağıtılmalı"
    finally:
        client.delete(key)


# ══════════════════════════════════════════════════════════════
#  İzlenen kameralar — oturum yalıtımı
# ══════════════════════════════════════════════════════════════


def test_iki_panel_birbirinin_listesini_EZMIYOR(client: Redis) -> None:
    """⚠ Kod incelemesinde bulunan hata (B6).

    Önceki sürüm tek global anahtar kullanıp her yazmada `DELETE`
    yapıyordu: iki panel açıkken ikincinin `watching` mesajı
    birincininkini siliyordu. Sessiz bir hata — kimse "benim kameram
    yavaşladı" demeden fark edilmezdi.
    """
    a, b = f"oturum-a-{uuid.uuid4().hex[:6]}", f"oturum-b-{uuid.uuid4().hex[:6]}"
    try:
        set_watched_cameras(client, a, ["cam-01", "cam-02"])
        set_watched_cameras(client, b, ["cam-09"])

        hepsi = get_watched_cameras(client)
        assert {"cam-01", "cam-02", "cam-09"} <= hepsi, (
            "iki oturumun kameraları BİRLİKTE görünmeli"
        )
    finally:
        client.delete(f"cameras:watched:{a}", f"cameras:watched:{b}")


def test_oturum_kendi_listesini_guncelleyebiliyor(client: Redis) -> None:
    """Panel kutucuk kapatınca liste küçülmeli."""
    s = f"oturum-{uuid.uuid4().hex[:6]}"
    try:
        set_watched_cameras(client, s, ["cam-01", "cam-02"])
        set_watched_cameras(client, s, ["cam-01"])

        kalan = get_watched_cameras(client)
        assert "cam-01" in kalan
        assert "cam-02" not in kalan
    finally:
        client.delete(f"cameras:watched:{s}")


def test_bos_liste_yazinca_oturum_temizleniyor(client: Redis) -> None:
    """Panel tüm kutucukları kapatınca kamera taban hıza dönmeli.

    ⚠ KENDİ ANAHTARINA bakıyor, birleşime DEĞİL.
    İlk sürüm `get_watched_cameras()` (tüm oturumların birleşimi) ile
    kontrol ediyordu ve sistem CANLIYKEN kırılıyordu: açık bir panel
    aynı kamerayı izliyorsa birleşimde o kamera duruyor ve test haklı
    olarak başarısız oluyor.

    Test ettiğimiz şey "bu oturum kendi listesini temizleyebiliyor mu";
    başkasının ne izlediği bu testin konusu değil. Yalıtımı bozan test,
    gerçek bir hata yokken kırmızı yanar ve zamanla görmezden gelinir.
    """
    s = f"oturum-{uuid.uuid4().hex[:6]}"
    anahtar = f"cameras:watched:{s}"
    try:
        set_watched_cameras(client, s, ["cam-05"])
        assert client.smembers(anahtar) == {"cam-05"}

        set_watched_cameras(client, s, [])
        assert not client.exists(anahtar), "boş liste yazılınca anahtar silinmeli"
    finally:
        client.delete(anahtar)
