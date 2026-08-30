"""Valkey Stream yardımcıları ve paylaşımlı bellek slot tahsisi.

Valkey'den **yalnızca meta veri** geçer. Ham kare paylaşımlı bellektedir
(bkz. `sentinel.bus.shm`). Mesaj başına ~200 bayt; saniyede ~100 mesaj.
Valkey'in kapasitesinin binde biri.

⚠ Redis DEĞİL, Valkey. `redis-py` istemcisi protokol uyumlu olduğu için
   değişmeden çalışır (LITERATUR.md §G).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from redis import Redis
from redis.exceptions import ResponseError

from sentinel.bus.shm import FREE_LIST_KEY, FrameRef
from sentinel.config import settings
from sentinel.core.preprocess import Letterbox
from sentinel.logging import get_logger

log = get_logger(__name__)


def connect(*, decode: bool = True) -> Redis:
    """Valkey bağlantısı açar (senkron istemci — worker'lar döngüseldir)."""
    return Redis.from_url(
        settings.effective_valkey_url,
        decode_responses=decode,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
        health_check_interval=30,
    )


# ══════════════════════════════════════════════════════════════
#  Slot tahsisi
# ══════════════════════════════════════════════════════════════


class SlotAllocator:
    """Paylaşımlı bellek slotlarının boş/dolu takibi.

    Boş slotlar bir Valkey listesinde durur. `acquire` listeden bir slot
    çeker (atomik `LPOP`), `release` geri koyar. Liste boşsa `acquire`
    None döner — **bu bir hata değil, geri basınç sinyalidir**: tüketici
    yetişemiyor demektir, kare atılır.
    """

    __slots__ = ("_client", "_key", "_slot_count")

    def __init__(self, client: Redis, slot_count: int, *, key: str = FREE_LIST_KEY) -> None:
        self._client = client
        self._slot_count = slot_count
        self._key = key

    def reset(self) -> None:
        """Havuzu sıfırlar: tüm slotları boş olarak işaretler.

        Yalnızca havuz sahibi (ilk ingest worker'ı) çağırmalı. Önceki
        çalışmadan kalan slotları temizler.
        """
        pipe = self._client.pipeline()
        pipe.delete(self._key)
        pipe.rpush(self._key, *range(self._slot_count))
        pipe.execute()
        log.info("slot_havuzu_sifirlandi", slots=self._slot_count)

    def acquire(self) -> int | None:
        """Boş bir slot alır. Yoksa None (geri basınç)."""
        value = self._client.lpop(self._key)
        return int(value) if value is not None else None  # type: ignore[arg-type]

    def release(self, slot: int) -> None:
        """Slotu havuza geri verir."""
        self._client.rpush(self._key, slot)

    def release_many(self, slots: list[int]) -> None:
        if slots:
            self._client.rpush(self._key, *slots)

    @property
    def available(self) -> int:
        return int(self._client.llen(self._key))  # type: ignore[arg-type]

    def sizanlari_geri_al(self, kullanimdaki: set[int]) -> list[int]:
        """Hiçbir yerde görünmeyen slotları havuza döndürür.

        ⚠ NEDEN `sahipsizleri_topla` YETMEDİ
        `XAUTOCLAIM` yalnızca AKIŞTA HÂLÂ DURAN asılı mesajları
        kurtarabiliyor. Akış sınırlı (`maxlen`) olduğu için asılı bir
        mesaj, o sırada akıştan düşmüş olabilir: `xautoclaim` onu boş
        alanlarla döndürüyor, yani **slot numarası artık bilinmiyor.**

        30.08.2026'da ölçülen durum tam olarak buydu: 48 asılı mesajın
        yalnızca 5'i kurtarılabildi, 43'ünün slotu kayıptı ve havuz
        5 slotla dönmeye devam etti.

        ⚠ ÇÖZÜM: SAYMAK YERİNE MUHASEBE
        Bir slot şu üç yerden birinde olmak ZORUNDA:
          (a) boş listede
          (b) akıştaki bir mesajın referansında
          (c) bir tüketicinin elinde (işlenmekte)

        Üçünde de olmayan slot sızmıştır. (a) ve (b) doğrudan okunuyor;
        (c) çağıran tarafından veriliyor.

        ⚠ TEK TÜKETİCİ VARSAYIMINA DAYANIYOR ve o varsayım mimari kural
        3'ün kendisi: "modeller tek süreçte tek kopya". İki çıkarım
        worker'ı olsaydı, birinin elindeki slotu diğeri sızmış sanıp
        havuza atardı ve aynı slota iki kare birden yazılırdı.
        Bu yüzden yalnızca AÇILIŞTA çağrılıyor: o an bu worker'ın
        elinde hiçbir şey yok ve ikinci bir worker varsa zaten mimari
        ihlal edilmiş demektir.
        """
        gorulen: set[int] = set()
        for ham in self._client.lrange(self._key, 0, -1):  # type: ignore[union-attr]
            try:
                gorulen.add(int(ham))
            except (TypeError, ValueError):
                continue
        gorulen |= kullanimdaki
        return [s for s in range(self._slot_count) if s not in gorulen]


# ══════════════════════════════════════════════════════════════
#  Kare meta veri akışı
# ══════════════════════════════════════════════════════════════


@dataclass(slots=True)
class FrameMessage:
    """Bir karenin meta verisi — Valkey'den geçen tek şey."""

    message_id: str
    camera: str
    sequence: int
    captured_at: float  # monotonik saat
    pts: float  # akış içi sunum zamanı
    ref: FrameRef
    motion_ratio: float
    gate_reason: str
    # Kare alım tarafında model uzayına taşındıysa (letterbox 640×640),
    # geri dönüşüm bilgisi burada. Kutular model uzayında üretiliyor;
    # operatöre gösterilmeden önce kaynak piksel uzayına taşınmaları
    # gerekiyor. None = ön işleme yapılmamış (ham kare).
    letterbox: Letterbox | None = None

    def to_fields(self) -> dict[str, str]:
        fields = {
            "cam": self.camera,
            "seq": str(self.sequence),
            "ts": f"{self.captured_at:.6f}",
            "pts": f"{self.pts:.3f}",
            "motion": f"{self.motion_ratio:.6f}",
            "gate": self.gate_reason,
            **self.ref.to_dict(),
        }
        if self.letterbox is not None:
            fields.update(self.letterbox.to_fields())
        return fields

    @classmethod
    def from_fields(cls, message_id: str, fields: dict[str, str]) -> FrameMessage:
        return cls(
            message_id=message_id,
            camera=fields["cam"],
            sequence=int(fields["seq"]),
            captured_at=float(fields["ts"]),
            pts=float(fields["pts"]),
            ref=FrameRef.from_dict(fields),
            motion_ratio=float(fields.get("motion", 0.0)),
            gate_reason=fields.get("gate", ""),
            letterbox=Letterbox.from_fields(fields),
        )

    @property
    def source_size(self) -> tuple[int, int]:
        """Kaynak karenin (genişlik, yükseklik) boyutu.

        Tarayıcı kutuları kendi görüntü alanına ölçeklemek için buna
        muhtaç. Ön işleme varsa kaynak boyut letterbox kaydında,
        yoksa karenin kendi şeklindedir.
        """
        if self.letterbox is not None:
            return (self.letterbox.source_width, self.letterbox.source_height)
        return (self.ref.width, self.ref.height)


class FrameStream:
    """`frames.ready` akışına yazma/okuma.

    Akış `MAXLEN ~ N` ile sınırlıdır: kuyruk dolduğunda **en eski kareler
    düşer**. Gerçek zamanlı sistemde 5 saniye önceki karenin değeri yoktur;
    beklemek yerine atmak doğrudur (PLAN.md §4.3).
    """

    __slots__ = ("_client", "_maxlen", "_stream")

    def __init__(
        self,
        client: Redis,
        *,
        stream: str | None = None,
        maxlen: int | None = None,
    ) -> None:
        self._client = client
        self._stream = stream or settings.stream_frames
        self._maxlen = maxlen or settings.stream_frames_maxlen

    def reset(self) -> None:
        """Akışı tamamen temizler.

        ⚠ Havuz sahibi worker açılışta bunu ÇAĞIRMALI. Sebebi:
        önceki çalışmadan kalan mesajlar artık geçersiz slot referansları
        taşır. Tüketici onları okuyup slotları "geri verirse" aynı slot
        listede iki kez görünür — iki kamera aynı slota yazar ve kareler
        birbirini ezer. (docs/report/problems.md · P-10)
        """
        self._client.delete(self._stream)
        log.info("akis_temizlendi", stream=self._stream)

    def publish(self, message: FrameMessage) -> str:
        """Meta veriyi akışa ekler, mesaj kimliğini döndürür."""
        return str(
            self._client.xadd(
                self._stream,
                message.to_fields(),  # type: ignore[arg-type]
                maxlen=self._maxlen,
                approximate=True,  # tam kırpma pahalı; ~ yeterli
            )
        )

    # ─── Tüketici grubu (GPU worker Gün 4'te kullanacak) ─────

    def ensure_group(self, group: str, *, start_id: str = "0") -> None:
        """Tüketici grubunu oluşturur (varsa sessizce geçer).

        `start_id="0"` bilinçli: grup akışın **başından** başlar.
        Varsayılan `"$"` (yalnızca yeni mesajlar) burada kilitlenmeye yol
        açar — akışta bekleyen kareler hiç okunmaz, slotları geri
        verilmez, üretici boş slot bulamaz ve sistem durur.
        Akıştaki her mesaj işlenmemiş iştir; hepsi okunmalı. (P-10)
        """
        try:
            self._client.xgroup_create(self._stream, group, id=start_id, mkstream=True)
            log.info("tuketici_grubu_olusturuldu", stream=self._stream, group=group)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def consume(
        self,
        group: str,
        consumer: str,
        *,
        count: int = 8,
        block_ms: int = 1000,
    ) -> Iterator[FrameMessage]:
        """Gruptan mesaj okur. Her mesaj gruptaki TEK bir tüketiciye gider.

        ⚠ NOGROUP'A DAYANIKLI
        Havuz sahibi (alım worker'ı) her açılışta akışı siler — bu
        zorunlu, yoksa önceki çalışmadan kalan geçersiz slot referansları
        havuzu bozar (P-10). Ama akış silinince tüketici grubu da silinir
        ve o sırada çalışan çıkarım worker'ı `NOGROUP` alıp **çöker**.

        Yani alım worker'ını yeniden başlatmak çıkarım worker'ını
        öldürüyordu. Bir bileşenin normal yeniden başlaması başka bir
        bileşeni düşürmemeli (PLAN.md §4.2 hata izolasyonu). Grubu
        sessizce yeniden kurup devam ediyoruz.
        """
        try:
            response: Any = self._client.xreadgroup(
                group, consumer, {self._stream: ">"}, count=count, block=block_ms
            )
        except ResponseError as exc:
            if "NOGROUP" not in str(exc):
                raise
            log.warning(
                "tuketici_grubu_kayboldu_yeniden_kuruluyor",
                stream=self._stream,
                group=group,
            )
            self.ensure_group(group)
            return
        if not response:
            return
        for _stream_name, entries in response:
            for message_id, fields in entries:
                yield FrameMessage.from_fields(message_id, fields)

    def ack(self, group: str, *message_ids: str) -> None:
        if message_ids:
            self._client.xack(self._stream, group, *message_ids)

    def sahipsizleri_topla(
        self, group: str, consumer: str, *, bosta_ms: int = 30_000, adet: int = 200
    ) -> list[FrameMessage]:
        """Ölmüş bir tüketicide asılı kalan mesajları geri alır.

        ⚠ BU OLMADAN BİR ÇÖKÜŞ HAVUZU KALICI OLARAK KÜÇÜLTÜYOR
        --------------------------------------------------------
        Tüketici grubunda `XREADGROUP` ile okunan her mesaj, ACK
        gelene kadar o tüketiciye **asılı (pending)** kalır. Çıkarım
        worker'ı sert kapatılırsa (kill, çökme, elektrik) elindeki
        mesajlar asılı kalır ve **onların paylaşımlı bellek slotları
        havuza geri dönmez.**

        Yeni worker `>` ile yalnızca YENİ mesajları okuduğu için o
        slotlar sonsuza dek kaybolur. 30.08.2026'da ölçüldü:

            48 slotun 48'i sızmış · boş slot 0/48 · üretim durmuş

        Ve arıza **sessiz**: alım worker'ı slot bulamayınca kareyi
        atıyor (`reason="no_slot"`), süreçlerin hepsi ayakta görünüyor,
        panel bağlı — sadece hiçbir şey işlenmiyor.

        ⚠ NEDEN `XAUTOCLAIM`
        Beklemedeki mesajları listeleyip tek tek sahiplenmek yerine tek
        atomik çağrı: hem daha az tur, hem de iki worker aynı anda
        toplamaya kalkarsa yarış durumu yok.

        ⚠ `bosta_ms` NEDEN BÜYÜK (30 sn)
        Bu eşik "bu mesajı işleyen tüketici ölmüştür" varsayımının
        gerekçesi. Kısa tutulursa, YAVAŞ ama sağ bir tüketicinin
        mesajları elinden alınır ve aynı kare iki kez işlenir. Normal
        işleme süresi milisaniyeler; 30 saniye rahat bir pay.
        """
        try:
            _sonraki, kayitlar, _silinen = self._client.xautoclaim(
                self._stream, group, consumer, min_idle_time=bosta_ms, count=adet
            )
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                return []
            raise
        cikti: list[FrameMessage] = []
        for message_id, fields in kayitlar or []:
            if not fields:
                # ⚠ Akıştan düşmüş (maxlen) ama hâlâ asılı olan kayıt:
                # `xautoclaim` bunu boş alanlarla döndürüyor. Slotu
                # bilinmediği için kurtarılamaz; ACK'lenip listeden
                # düşürülüyor, yoksa sonsuza dek toplanmaya çalışılır.
                self._client.xack(self._stream, group, message_id)
                continue
            cikti.append(FrameMessage.from_fields(message_id, fields))
        return cikti

    @property
    def depth(self) -> int:
        """Akıştaki mesaj sayısı — geri basınç göstergesi."""
        return int(self._client.xlen(self._stream))  # type: ignore[arg-type]

    def islenmemis_slotlar(self, group: str) -> set[int]:
        """Henüz İŞLENMEMİŞ mesajların işaret ettiği slot numaraları.

        Slot muhasebesinin (b) kalemi (bkz.
        `SlotAllocator.sizanlari_geri_al`).

        ⚠ "AKIŞTAKİ" DEĞİL "İŞLENMEMİŞ" — ilk sürümün hatası buydu
        `XACK` bir mesajı akıştan **SİLMİYOR**, yalnızca tüketicinin
        bekleyen listesinden çıkarıyor. Akıştan düşme ancak `maxlen`
        budamasıyla oluyor.

        Bu yüzden akışın tamamını taramak, çoktan işlenmiş ve slotu
        ÇOKTAN İADE EDİLMİŞ mesajları da "kullanımda" saymak demekti:

            akıştaki mesaj 99 · farklı slot 48 · boş slot 0/48

        99 mesaj 48 slota işaret ediyordu, yani slotlar tekrar
        kullanılmıştı. O tarama hiçbir zaman sızıntı bulamazdı —
        her slot her zaman "birinde görünüyordu".

        Doğrusu iki küme:
          · henüz TESLİM EDİLMEMİŞ mesajlar (grubun `last-delivered-id`
            değerinden sonrası)
          · TESLİM EDİLMİŞ ama ACK'lenmemiş mesajlar (bekleyenler)

        İkisi birlikte "slotu hâlâ tutulan" mesajları veriyor.
        """
        slotlar: set[int] = set()

        # (b1) Henüz teslim edilmemiş kayıtlar
        son_teslim = "0-0"
        try:
            for g in self._client.xinfo_groups(self._stream):  # type: ignore[union-attr]
                if g.get("name") == group:
                    son_teslim = str(g.get("last-delivered-id", "0-0"))
                    break
        except ResponseError:
            return slotlar

        for _mid, alanlar in self._client.xrange(  # type: ignore[union-attr]
            self._stream, min=f"({son_teslim}", max="+"
        ):
            try:
                slotlar.add(int(alanlar["slot"]))
            except (KeyError, TypeError, ValueError):
                continue

        # (b2) Teslim edilmiş ama ACK'lenmemiş (bekleyen) kayıtlar
        try:
            bekleyenler = self._client.xpending_range(
                self._stream, group, min="-", max="+", count=1000
            )
        except ResponseError:
            bekleyenler = []
        for kayit in bekleyenler or []:
            mid = kayit.get("message_id")
            if not mid:
                continue
            for _m, alanlar in self._client.xrange(  # type: ignore[union-attr]
                self._stream, min=mid, max=mid
            ):
                try:
                    slotlar.add(int(alanlar["slot"]))
                except (KeyError, TypeError, ValueError):
                    continue
        return slotlar

    @property
    def name(self) -> str:
        return self._stream


class ResultStream:
    """`inference.results` akışı — tespit sonuçları.

    Kare akışının aksine burada gerçek veri (JSON) taşınır: kutular,
    iskelet noktaları, güven skorları. Kare başına ~1-3 KB. Paylaşımlı
    belleğe gerek yok; bu veri zaten küçük ve serileştirilmiş olması
    gerekiyor (analitik ve API katmanı okuyacak).
    """

    __slots__ = ("_client", "_maxlen", "_stream")

    def __init__(
        self,
        client: Redis,
        *,
        stream: str | None = None,
        maxlen: int | None = None,
    ) -> None:
        self._client = client
        self._stream = stream or settings.stream_results
        self._maxlen = maxlen or settings.stream_results_maxlen

    def publish(self, camera: str, payload: str, *, sequence: int, captured_at: float) -> str:
        return str(
            self._client.xadd(
                self._stream,
                {
                    "cam": camera,
                    "seq": str(sequence),
                    "ts": f"{captured_at:.6f}",
                    "data": payload,
                },
                maxlen=self._maxlen,
                approximate=True,
            )
        )

    def reset(self) -> None:
        self._client.delete(self._stream)

    @property
    def depth(self) -> int:
        return int(self._client.xlen(self._stream))  # type: ignore[arg-type]

    @property
    def name(self) -> str:
        return self._stream


__all__ = ["FrameMessage", "FrameStream", "ResultStream", "SlotAllocator", "connect"]


# ─── Operatörün izlediği kameralar ────────────────────────────
# Panel hangi kutucukları AÇTIYSA onları buraya yazar; alım worker'ı
# okuyup o kameralara daha yüksek örnekleme hızı ayırır (PLAN.md §5.2).
#
# Neden Valkey: panel API sürecine bağlı, örnekleme kararı ise alım
# sürecinde veriliyor. İkisi ayrı süreç; paylaşılan tek yer Valkey.
#
# Neden TTL: panel kapanırsa ya da tarayıcı çökerse liste taze kalmamalı.
# Panel düzenli olarak yeniliyor; yenilenmezse kendiliğinden siliniyor
# ve sistem "kimse izlemiyor" moduna dönüyor.
#
# ⚠ OTURUM BAŞINA AYRI ANAHTAR — tek global küme DEĞİL
# İlk sürüm tek bir `cameras:watched` kümesi kullanıyordu ve her yazma
# `DELETE` + `SADD` yapıyordu. İki panel açıkken ikincinin `watching`
# mesajı birincininkini siliyordu: iki operatörden biri kutucuk açtığı
# anda diğerinin izlediği kameralar taban hıza düşüyordu. Sessiz bir
# hata — kimse "benim kameram yavaşladı" diye şikâyet etmeden fark
# edilmezdi.
#
# Şimdi her WS oturumu kendi anahtarını yazıyor, alım worker'ı hepsinin
# BİRLEŞİMİNİ okuyor. TTL yine oturum başına: bir panel kapanınca
# yalnızca onun anahtarı düşüyor, diğerleri etkilenmiyor.
WATCHED_PREFIX = "cameras:watched:"
WATCHED_TTL_S = 20


# ─── Tüketici kapasitesi ──────────────────────────────────────
#
# ⚠ ÜRETİCİ/TÜKETİCİ DENGESİZLİĞİ — ölçülen sorun
# 18.08.2026 ölçümü: alım 20 kamera × 4 FPS = 80 kare/sn üretiyor,
# çıkarım ~6 kare/sn tüketiyor, **karelerin %89'u atılıyor.**
#
# Atmak gecikmeyi sınırlıyor (P-25, doğru karar) ama israfı çözmüyor:
# atılan her kare için decode + BGR dönüşümü + letterbox CPU'su ZATEN
# ödenmiş oluyor. Ve BGR dönüşümü alım maliyetinin %77'si (P-09).
#
# Yani CPU'nun büyük kısmı çöpe giden kareler için harcanıyor — üstelik
# o CPU, aynı çekirdekleri paylaşan çıkarım sürecinden çalınıyor. Poz'un
# izole ölçümde 2.77 ms, boru hattında 99.8 ms sürmesinin sebebi bu
# çekişme.
#
# Çözüm: üreticiyi tüketici kapasitesine bağlamak. Tüketici kaç kare
# işleyebiliyorsa üretici o kadar üretsin.
#
# Neden Valkey: iki AYRI süreç. Paylaşılan tek yer burası — izlenen
# kamera listesiyle aynı desen.
#
# Neden TTL: çıkarım worker'ı düşerse alım sonsuza dek kısık kalmamalı.
# Anahtar tazelenmezse silinir ve sistem varsayılan hızlara döner.
CAPACITY_KEY = "pipeline:capacity"
CAPACITY_TTL_S = 20


def set_pipeline_capacity(client: Redis, frames_per_second: float) -> None:
    """Çıkarım worker'ı ölçülen tüketim hızını yayınlar."""
    client.set(CAPACITY_KEY, f"{frames_per_second:.3f}", ex=CAPACITY_TTL_S)


def get_pipeline_capacity(client: Redis) -> float | None:
    """Tüketici kapasitesi (kare/sn). Bilinmiyorsa None.

    None dönmesi bir hata değil: çıkarım worker'ı henüz açılmamış ya da
    kapanmış olabilir. O durumda alım katmanı yapılandırılmış taban
    hızlarıyla çalışmaya devam eder.
    """
    try:
        value = client.get(CAPACITY_KEY)
    except Exception:
        return None
    if value is None:
        return None
    try:
        # `decode_responses=True` ile str gelir; ham istemcide bytes
        # gelebilir. float() ikisini de kabul ediyor.
        return float(value)
    except (TypeError, ValueError):
        return None


def set_watched_cameras(client: Redis, session_id: str, cameras: list[str]) -> None:
    """Bir oturumun izlediği kameraları yayınlar.

    Args:
        session_id: WS oturumunu ayırt eden kimlik. Aynı oturumun
            tekrar tekrar yazması aynı anahtarı tazeler.
    """
    key = f"{WATCHED_PREFIX}{session_id}"
    pipe = client.pipeline()
    pipe.delete(key)
    if cameras:
        pipe.sadd(key, *cameras)
        pipe.expire(key, WATCHED_TTL_S)
    pipe.execute()


def get_watched_cameras(client: Redis) -> set[str]:
    """Tüm açık oturumların izlediği kameraların BİRLEŞİMİ.

    Hiç panel açık değilse boş küme döner ve sistem "kimse izlemiyor"
    moduna geçer.

    `SCAN` kullanılıyor, `KEYS` değil: `KEYS` sunucuyu tarama boyunca
    bloklar. Anahtar sayısı burada küçük (oturum başına bir tane) ama
    bloklayan komutu alışkanlık hâline getirmemek gerekiyor.
    """
    try:
        keys = list(client.scan_iter(match=f"{WATCHED_PREFIX}*", count=100))
        if not keys:
            return set()
        members = client.sunion(keys)
    except Exception:
        return set()
    # `decode_responses=True` ile bağlanıyoruz, yani str geliyor. Yine de
    # bytes'a karşı korunuyoruz: bu fonksiyon ham bir Redis nesnesiyle de
    # çağrılabilir (test, betik) ve orada ayar farklı olabilir.
    return {m.decode() if isinstance(m, bytes) else str(m) for m in members}
