"""Canlı sonuç WebSocket uç noktası.

⚠ GÜVENLİK — WebSocket CORS'a UYMAZ (PLAN.md §11.1 / G06)
---------------------------------------------------------
Tarayıcının "farklı origin'den istek atamazsın" kuralı `fetch`/XHR için
geçerlidir; WebSocket el sıkışması bu kuralın **dışındadır**. Kötü niyetli
bir sayfa, kullanıcının tarayıcısından bizim sunucumuza WS açabilir ve
tüm kamera akışını dinleyebilir. `CORSMiddleware` bunu engellemez.

Bu yüzden `Origin` başlığı **elle** beyaz listeye karşı doğrulanır.
Origin yoksa (tarayıcı dışı istemci) reddedilir.

Protokol
--------
    → (bağlan)              Origin doğrulanır, yoksa 1008 ile kapatılır
    ← hello                 sunucu bilgisi
    → subscribe {cameras}   istemci abone olmak istediği kameraları söyler
    ← subscribed {cameras}  SUNUCU YETKİ KONTROLÜ YAPAR, izinsizleri çıkarır
    ← frame …               sürekli sonuç akışı
    → ping / ← pong         canlılık

Faz 1'de eklenecek: JWT ile kimlik doğrulama ve `user_camera_access`
tablosuna göre kamera bazlı yetki (G05/G07). Şu an tüm kameralar açık.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from sentinel.api.ws.manager import Client, broadcaster
from sentinel.config import settings
from sentinel.logging import get_logger

log = get_logger(__name__)
router = APIRouter()

CLOSE_POLICY_VIOLATION = 1008
MAX_SUBSCRIPTIONS = 64
IDLE_TIMEOUT_S = 120.0


def _same_origin(origin: str, host_header: str | None) -> bool:
    """İstek, sayfayı sunan sunucunun kendisinden mi geliyor?

    Panel API ile aynı sunucudan servis ediliyor. Bu durumda `Origin`
    başlığı `Host` başlığıyla aynıdır ve bağlantı **tanımı gereği**
    güvenilirdir — aynı köken politikasının koruduğu şey zaten budur.

    Bu kontrol olmadan beyaz listeye kendi adresimizi elle eklemek
    gerekirdi; adres değişince (farklı port, farklı makine) sessizce
    kırılırdı. Bkz. docs/report/problems.md · P-11
    """
    if not host_header:
        return False
    candidate = urlsplit(origin)
    # Host başlığı "127.0.0.1:8001" biçiminde, şema içermez
    origin_authority = candidate.netloc.lower()
    return origin_authority == host_header.strip().lower()


def origin_allowed(origin: str | None, host_header: str | None = None) -> bool:
    """`Origin` başlığını doğrular.

    İki koşuldan biri sağlanmalı:
      1. Aynı köken (panel API ile aynı sunucudan geliyor), veya
      2. Beyaz listede (ayrı geliştirme sunucusundan gelen React SPA)

    Karşılaştırma şema+host+port düzeyinde yapılır; yol ve sorgu
    dikkate alınmaz. Origin başlığı yoksa reddedilir — tarayıcı her
    zaman gönderir; göndermeyen istemci tarayıcı değildir.
    """
    if not origin:
        return False
    try:
        candidate = urlsplit(origin)
    except ValueError:
        return False

    if _same_origin(origin, host_header):
        return True

    for allowed in settings.origins:
        reference = urlsplit(allowed)
        if (candidate.scheme, candidate.hostname, candidate.port) == (
            reference.scheme,
            reference.hostname,
            reference.port,
        ):
            return True
    return False


def authorize_cameras(requested: list[str]) -> list[str]:
    """İstemcinin istediği kameralardan izin verilenleri döndürür.

    ⚠ İstemcinin gönderdiği listeye ASLA olduğu gibi güvenilmez (G07).
    Şu an kimlik doğrulama yok, bu yüzden yalnızca biçim doğrulaması
    yapılıyor. Faz 1'de `user_camera_access` sorgusu buraya girecek.
    """
    clean: list[str] = []
    for name in requested[:MAX_SUBSCRIPTIONS]:
        if isinstance(name, str) and 1 <= len(name) <= 64 and name.replace("-", "").isalnum():
            clean.append(name)
    return clean


async def _sender(client: Client) -> None:
    """İstemcinin kuyruğundaki mesajları sokete yazar."""
    while True:
        payload = await client.queue.get()
        await client.websocket.send_text(payload)


async def _receiver(client: Client) -> None:
    """İstemciden gelen kontrol mesajlarını işler."""
    while True:
        raw = await asyncio.wait_for(client.websocket.receive_text(), timeout=IDLE_TIMEOUT_S)
        try:
            message: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            continue

        kind = message.get("type")
        if kind == "subscribe":
            requested = message.get("cameras") or []
            allowed = authorize_cameras(requested if isinstance(requested, list) else [])
            client.cameras = set(allowed)
            await client.websocket.send_text(
                json.dumps({"type": "subscribed", "cameras": allowed}, separators=(",", ":"))
            )
        elif kind == "watching":
            # Panel hangi kutucukları AÇTIĞINI bildiriyor. Bu bilgi
            # örnekleme hızını yönlendiriyor: operatörün baktığı kamera
            # daha sık analiz edilir (PLAN.md §5.2).
            #
            # ⚠ Yetki kontrolünden geçiyor — istemci izinsiz bir kamerayı
            # "izliyorum" diye bildirip kaynak yönlendiremesin.
            requested = message.get("cameras") or []
            watched = authorize_cameras(requested if isinstance(requested, list) else [])
            _publish_watched(watched)
        elif kind == "ping":
            await client.websocket.send_text(json.dumps({"type": "pong", "ts": time.time()}))



# ─── İzlenen kameraların yayınlanması ────────────────────────

_watch_client: Any = None


def _publish_watched(cameras: list[str]) -> None:
    """İzlenen kamera listesini alım worker'ının okuyacağı yere yazar.

    Hata yutuluyor: bu bir optimizasyon sinyali, kritik yol değil.
    Valkey erişilemezse sistem varsayılan hızlarla çalışmaya devam eder.
    """
    global _watch_client
    try:
        if _watch_client is None:
            from sentinel.bus.streams import connect

            _watch_client = connect()
        from sentinel.bus.streams import set_watched_cameras

        set_watched_cameras(_watch_client, cameras)
    except Exception as exc:  # pragma: no cover
        log.debug("izlenen_kamera_yayinlanamadi", error=str(exc))

@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    host_header = websocket.headers.get("host")
    if not origin_allowed(origin, host_header):
        # Bağlantıyı KABUL ETMEDEN reddet — el sıkışma tamamlanmasın
        log.warning("ws_origin_reddedildi", origin=origin or "(yok)", host=host_header)
        await websocket.close(code=CLOSE_POLICY_VIOLATION, reason="origin not allowed")
        return

    await websocket.accept()
    client = Client(websocket=websocket)
    broadcaster.add(client)

    await websocket.send_text(
        json.dumps(
            {
                "type": "hello",
                "server_time": time.time(),
                "note": "Boş abonelik = tüm kameralar. Video bu kanaldan GELMEZ.",
            },
            separators=(",", ":"),
        )
    )

    sender = asyncio.create_task(_sender(client), name="ws-sender")
    receiver = asyncio.create_task(_receiver(client), name="ws-receiver")
    try:
        done, pending = await asyncio.wait(
            {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, TimeoutError):
                task.result()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("ws_hatasi", error=f"{type(exc).__name__}: {exc}")
    finally:
        sender.cancel()
        receiver.cancel()
        broadcaster.remove(client)
        if websocket.client_state is not WebSocketState.DISCONNECTED:
            with contextlib.suppress(RuntimeError):
                await websocket.close()


__all__ = ["authorize_cameras", "origin_allowed", "router"]
