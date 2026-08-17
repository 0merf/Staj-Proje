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

    @property
    def depth(self) -> int:
        """Akıştaki mesaj sayısı — geri basınç göstergesi."""
        return int(self._client.xlen(self._stream))  # type: ignore[arg-type]

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
WATCHED_KEY = "cameras:watched"
WATCHED_TTL_S = 20


def set_watched_cameras(client: Redis, cameras: list[str]) -> None:
    """Operatörün şu an izlediği kameraları yayınlar."""
    pipe = client.pipeline()
    pipe.delete(WATCHED_KEY)
    if cameras:
        pipe.sadd(WATCHED_KEY, *cameras)
        pipe.expire(WATCHED_KEY, WATCHED_TTL_S)
    pipe.execute()


def get_watched_cameras(client: Redis) -> set[str]:
    """İzlenen kamera kümesi. Panel kapalıysa boş döner."""
    try:
        members = client.smembers(WATCHED_KEY)
    except Exception:
        return set()
    return {m.decode() if isinstance(m, bytes) else str(m) for m in members}  # type: ignore[union-attr]
