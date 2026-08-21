"""WebSocket bağlantı yöneticisi ve sonuç yayıncısı.

Mimarideki yeri
---------------
`inference.results` akışını **tek bir okuyucu** takip eder ve sonuçları
abone WebSocket istemcilerine dağıtır. Her istemcinin kendi Valkey
bağlantısını açması israf olurdu: 10 operatör = 10 okuyucu = 10 kat yük.

⚠ VİDEO BU KANALDAN GEÇMEZ
--------------------------
Buradan yalnızca **meta veri** gider: kutular, iskelet noktaları, risk
skorları (~1-3 KB/mesaj). Video WHEP/WebRTC ile ayrı gelir, kutuları
tarayıcı canvas'ta çizer. Sunucuda videoya çizim yapmak NVENC oturum
limitine takılır ve GPU'yu tüketir (PLAN.md §9.2).

Geri basınç
-----------
Her istemcinin **sınırlı** bir kuyruğu var. Yavaş bir istemci (ağı kötü,
sekmesi arka planda) yayıncıyı bloklayamaz: kuyruğu dolduğunda **en eski
mesaj düşer**. Gerçek zamanlı görüntülemede eski kare değersizdir.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from redis.asyncio import Redis

from sentinel.config import settings
from sentinel.logging import get_logger

log = get_logger(__name__)

# İstemci başına kuyruk sınırı. 50 mesaj ≈ 12 kamera × 1 saniyelik veri.
CLIENT_QUEUE_MAX = 50
# Valkey'den tek seferde okunacak mesaj sayısı
READ_COUNT = 64
READ_BLOCK_MS = 500

# Analitik worker'ın anomali yazdığı akış (analytics/worker.py).
EVENT_STREAM = "analytics.events"


# eq=False: dataclass varsayılan olarak __eq__ üretir, bu da __hash__'i
# None yapar ve nesne set'e konulamaz. Her istemci kendine özgüdür;
# kimlik tabanlı hash (nesne adresi) doğru davranıştır.
@dataclass(eq=False)
class Client:
    """Bağlı bir WebSocket istemcisi."""

    websocket: WebSocket
    # Oturumu ayırt eden kimlik. İzlenen kamera listesi bununla
    # yazılıyor; iki panel açıkken biri diğerinin listesini ezmesin
    # (bkz. bus/streams.py · WATCHED_PREFIX).
    session_id: str = field(default_factory=lambda: uuid4().hex[:16])
    cameras: set[str] = field(default_factory=set)
    queue: asyncio.Queue[str] = field(
        default_factory=lambda: asyncio.Queue(maxsize=CLIENT_QUEUE_MAX)
    )
    dropped: int = 0

    def wants(self, camera: str) -> bool:
        """Boş abonelik = hepsini istiyor."""
        return not self.cameras or camera in self.cameras

    def offer(self, payload: str) -> None:
        """Mesajı kuyruğa koyar; doluysa en eskiyi atar.

        ⚠ Burada `await queue.put()` KULLANILMAZ. Yavaş bir istemci
        yayıncıyı bekletirse tüm diğer istemciler de gecikir.
        """
        try:
            self.queue.put_nowait(payload)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()  # en eskiyi at
            with contextlib.suppress(asyncio.QueueFull):
                self.queue.put_nowait(payload)
            self.dropped += 1


class ResultBroadcaster:
    """`inference.results` akışını okur ve istemcilere dağıtır."""

    def __init__(self) -> None:
        self._clients: set[Client] = set()
        self._task: asyncio.Task[None] | None = None
        self._redis: Redis | None = None
        self._last_id = "$"  # yalnızca yeni sonuçlar — canlı görüntüleme
        self._last_event_id = "$"  # anomaliler de yalnızca yeniden itibaren
        self.alerts_sent = 0
        self.messages_read = 0
        self.messages_sent = 0

    # ─── Yaşam döngüsü ───────────────────────────────────────

    async def start(self) -> None:
        if self._task is not None:
            return
        self._redis = Redis.from_url(settings.effective_valkey_url, decode_responses=True)
        self._task = asyncio.create_task(self._pump(), name="result-broadcaster")
        log.info("yayinci_basladi", stream=settings.stream_results)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        log.info("yayinci_durdu")

    # ─── Abonelik ────────────────────────────────────────────

    def add(self, client: Client) -> None:
        self._clients.add(client)
        log.info("ws_istemci_baglandi", total=len(self._clients))

    def remove(self, client: Client) -> None:
        self._clients.discard(client)
        log.info("ws_istemci_ayrildi", total=len(self._clients), dropped=client.dropped)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ─── Okuma döngüsü ───────────────────────────────────────

    async def _pump(self) -> None:
        """Akışı okuyup istemcilere dağıtan sonsuz döngü.

        ⚠ İKİ AKIŞ, TEK OKUYUCU
        `inference.results` (kutular, saniyede onlarca) ve
        `analytics.events` (anomaliler, seyrek) aynı `XREAD` çağrısında
        okunuyor. Ayrı iki döngü kurmak iki bağlantı, iki bekleme ve
        iki kod yolu demekti; Valkey tek çağrıda birden çok akış
        okuyabiliyor.

        Anomali akışı **seyrek** — dakikada birkaç mesaj. Kendi başına
        bir döngü açmak, çoğu zaman boşta bekleyen bir görev olurdu.
        """
        assert self._redis is not None
        stream = settings.stream_results

        while True:
            try:
                response = await self._redis.xread(
                    {stream: self._last_id, EVENT_STREAM: self._last_event_id},
                    count=READ_COUNT,
                    block=READ_BLOCK_MS,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("yayinci_okuma_hatasi", error=f"{type(exc).__name__}: {exc}")
                await asyncio.sleep(1.0)
                continue

            if not response:
                continue

            # ⚠ `Any`'ye düşürülüyor: `redis-py`'nin `xread` dönüş tipi
            # `decode_responses` ayarına göre değişen çok kollu bir
            # birleşim ve statik olarak daraltılamıyor. Tipi burada
            # zorlamak okunmayan bir `cast` yığını üretirdi; yapı zaten
            # açılırken doğrulanıyor ve bozuk mesaj yakalanıyor.
            girdiler: Any = response
            for stream_name, entries in girdiler:
                # ⚠ Hangi akıştan geldiğini AYIRMAK şart: ikisinin
                # mesaj biçimi ve son-okunan imleci farklı. Karışırsa
                # anomali "kare" gibi gönderilir ve panel onu çizmeye
                # çalışır.
                anomali_mi = str(stream_name) == EVENT_STREAM
                for message_id, fields in entries:
                    if anomali_mi:
                        self._last_event_id = message_id
                        self._dispatch_alert(fields)
                    else:
                        self._last_id = message_id
                        self.messages_read += 1
                        self._dispatch(fields)

    def _dispatch(self, fields: dict[str, str]) -> None:
        """Tek bir sonucu ilgili istemcilere dağıtır."""
        if not self._clients:
            return

        camera = fields.get("cam", "")
        try:
            captured_at = float(fields.get("ts", 0.0))
            data = json.loads(fields.get("data", "{}"))

            # ⚠ `lat` BURADA YENİDEN HESAPLANIYOR
            # Çıkarım worker'ı `lat`'ı kendi publish anında yazıyordu,
            # yani ölçüm "yakalanma → çıkarım sonucu yazıldı" arasını
            # kapsıyordu. İçermediği kısım: Valkey'e yazma, buraya
            # okunma, istemci kuyruğu, soket, ağ.
            #
            # Tarayıcı bu değerle `yakalanma ≈ varış − lat` hesabı
            # yapıyor (frontend/src/lib/sync.ts). Eksik ölçülen gecikme,
            # yakalanma anını olduğundan GEÇ gösteriyor ve kutular
            # sistematik olarak biraz ileri kayıyordu.
            #
            # Yayın anında ölçmek kalan payı da kapsıyor. Geriye yalnızca
            # soket + ağ süresi kalıyor ki o da tarayıcının kendi
            # ölçtüğü video gecikmesiyle aynı yolu paylaşıyor.
            if captured_at > 0:
                data["lat"] = round((time.time() - captured_at) * 1000.0)

            payload = json.dumps(
                {
                    "type": "frame",
                    "cam": camera,
                    "seq": int(fields.get("seq", 0)),
                    "ts": captured_at,
                    **data,
                },
                separators=(",", ":"),
            )
        except (ValueError, TypeError) as exc:
            log.warning("bozuk_sonuc_mesaji", error=str(exc), cam=camera)
            return

        for client in self._clients:
            if client.wants(camera):
                client.offer(payload)
                self.messages_sent += 1

    def _dispatch_alert(self, fields: dict[str, str]) -> None:
        """Anomaliyi abone istemcilere `alert` olarak gönderir.

        ⚠ Anomali ABONELİK FİLTRESİNE TAKILMAZ.
        Kare mesajları yalnızca abone olunan kameralara gider (panelde
        20 kutucuk için 20 akış boşuna taşınmasın). Ama alarm başkadır:
        operatör cam-03'ü açmamışsa bile orada biri düştüyse BUNU
        GÖRMELİ. Gözetim sisteminin varlık sebebi tam olarak bu —
        kimsenin bakmadığı kamerada olanı bildirmek.
        """
        camera = fields.get("cam", "")
        try:
            payload = json.dumps(
                {
                    "type": "alert",
                    "ts": float(fields.get("ts", 0.0)),
                    **json.loads(fields.get("data", "{}")),
                },
                separators=(",", ":"),
            )
        except (ValueError, TypeError) as exc:
            log.warning("bozuk_anomali_mesaji", error=str(exc), cam=camera)
            return

        for client in self._clients:
            client.offer(payload)
            self.alerts_sent += 1
        log.info("anomali_yayinlandi", cam=camera, tur=fields.get("type"))

    def stats(self) -> dict[str, Any]:
        return {
            "clients": len(self._clients),
            "messages_read": self.messages_read,
            "messages_sent": self.messages_sent,
            "alerts_sent": self.alerts_sent,
            "dropped_total": sum(c.dropped for c in self._clients),
        }


broadcaster = ResultBroadcaster()

__all__ = ["CLIENT_QUEUE_MAX", "Client", "ResultBroadcaster", "broadcaster"]
