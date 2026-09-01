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

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from sentinel.api.guvenlik import token_coz
from sentinel.api.ws.manager import Client, broadcaster
from sentinel.config import get_settings, settings
from sentinel.logging import get_logger

log = get_logger(__name__)
router = APIRouter()

CLOSE_POLICY_VIOLATION = 1008
MAX_SUBSCRIPTIONS = 64
IDLE_TIMEOUT_S = 120.0


def _same_origin(origin: str, host_header: str | None, scheme: str | None = None) -> bool:
    """İstek, sayfayı sunan sunucunun kendisinden mi geliyor?

    Panel API ile aynı sunucudan servis ediliyor. Bu durumda `Origin`
    başlığı `Host` başlığıyla aynıdır ve bağlantı **tanımı gereği**
    güvenilirdir — aynı köken politikasının koruduğu şey zaten budur.

    Bu kontrol olmadan beyaz listeye kendi adresimizi elle eklemek
    gerekirdi; adres değişince (farklı port, farklı makine) sessizce
    kırılırdı. Bkz. docs/report/problems.md · P-11

    ⚠ ŞEMA DA KARŞILAŞTIRILIYOR
    ---------------------------
    `Host` başlığı yalnızca "127.0.0.1:8001" taşır, şema içermez.
    İlk sürüm bu yüzden yalnızca host:port karşılaştırıyordu ve
    `Origin: https://127.0.0.1:8001` ile `Host: 127.0.0.1:8001`
    eşleşiyordu — oysa http ile https AYRI kökenlerdir.

    Pratikte sömürülmesi zor (aynı host:port'ta iki şema aynı anda
    duramaz) ama aynı köken politikasının tanımı üç bileşenlidir:
    şema + host + port. İkisini kontrol edip üçüncüsünü atlamak,
    kontrolün adını yanlış koymak olurdu.

    Şema `Host`'tan gelmiyor; bağlantının KENDİ şemasından türetiliyor
    (`ws` → `http`, `wss` → `https`). Çağıran taraf veriyor.
    """
    if not host_header:
        return False
    candidate = _parts(origin)
    if candidate is None:
        return False
    origin_scheme, origin_host, origin_port = candidate

    # netloc'u yeniden kurmak yerine host+port'u Host başlığıyla kıyaslıyoruz;
    # böylece "127.0.0.1:8001" ile "127.0.0.1:8001" karşılaştırması
    # kullanıcı adı/parola gibi ekleri olan bozuk Origin'lerde de doğru kalır.
    authority = origin_host or ""
    if origin_port is not None:
        authority = f"{authority}:{origin_port}"
    if authority != host_header.strip().lower():
        return False

    # Şema bilinmiyorsa (eski çağrılar, testler) host eşleşmesiyle yetin.
    return scheme is None or origin_scheme == scheme


def origin_allowed(
    origin: str | None,
    host_header: str | None = None,
    scheme: str | None = None,
) -> bool:
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

    if _same_origin(origin, host_header, scheme):
        return True

    candidate = _parts(origin)
    if candidate is None:
        return False

    for allowed in settings.origins:
        reference = _parts(allowed)
        if reference is not None and candidate == reference:
            return True
    return False


def _parts(url: str) -> tuple[str, str | None, int | None] | None:
    """URL'yi (şema, host, port) üçlüsüne ayırır; ayrıştırılamazsa None.

    ⚠ `urlsplit` TEMBEL ÇALIŞIR — bu bir tuzak
    -----------------------------------------
    İlk sürüm şöyleydi:

        try:
            candidate = urlsplit(origin)
        except ValueError:
            return False
        ...
        candidate.port          # ← ValueError BURADA fırlıyor

    `urlsplit` çağrısı bozuk girdide bile hata vermiyor; ayrıştırmayı
    alan erişimine erteliyor. `.port` ise portu tam sayıya çeviremezse
    `ValueError` atıyor. Yani `try` bloğu yanlış yeri sarmalıyordu ve
    hata `for` döngüsünün içinde, korumasız fırlıyordu.

    Somut etki: `Origin: http://:::` başlığıyla gelen bir bağlantı
    WebSocket işleyicisini çökertiyordu. Kimlik doğrulaması GEREKMEYEN,
    el sıkışma TAMAMLANMADAN tetiklenebilen bir hata yolu — yani dışarıdan
    ulaşılabilir. Bu testle yakalandı (tests/unit/test_ws_guvenlik.py).

    Ders: bir kütüphane çağrısını `try` içine almak, o çağrının ürettiği
    NESNEYİ kullanmanın da güvenli olduğu anlamına gelmiyor.
    """
    try:
        parsed = urlsplit(url)
        return (parsed.scheme, parsed.hostname, parsed.port)
    except ValueError:
        return None


def _tanimli_kameralar() -> frozenset[str]:
    """Sistemde TANIMLI kamera adları.

    ⚠ MediaMTX'e sorulmuyor, yapılandırmadan üretiliyor. MediaMTX'e
    sormak, bir dış servisin döndürdüğü listeyi yetki kararına temel
    yapmak olurdu; o servis ele geçirilirse yetki sınırı da gider.
    Yapılandırma bizim kontrolümüzde.
    """
    n = get_settings().camera_count
    # ⚠ `cam-21-live` adı MediaMTX yapılandırmasında sabit
    # (infra/mediamtx/mediamtx.yml · `source: publisher`) ve
    # `scripts/publish_webcam.py` onu kullanıyor. Buraya elle yazmak
    # bir kopya — ama alternatifi MediaMTX'e sormaktı ve bir dış
    # servisin cevabını yetki kararına temel yapmak daha kötü.
    return frozenset([f"cam-{i:02d}" for i in range(1, n + 1)] + ["cam-21-live"])


def authorize_cameras(requested: list[str]) -> list[str]:
    """İstemcinin istediği kameralardan izin verilenleri döndürür (G07).

    ⚠ İSTEMCİNİN GÖNDERDİĞİ LİSTEYE ASLA GÜVENİLMEZ
    WebSocket'te istemci istediği mesajı gönderebilir; abonelik listesi
    bir İSTEK, bir bildirim değil.

    ⚠ 01.09.2026 — BİÇİM DOĞRULAMASI YETMİYORDU
    Önceki sürüm yalnızca "harf-rakam-tire, 1-64 karakter" diye
    bakıyordu; `cam-99` ya da `admin-panel` gibi var olmayan adlar
    geçiyordu. Tek başına ciddi bir açık değil (olmayan kameradan veri
    akmaz) ama yetki kontrolünün ilkesi ihlal ediliyordu: **beyaz liste
    kara listeye yeğlenir.** Bilinen iyileri saymak, kötüleri tahmin
    etmekten güvenlidir.

    Ayrıca sessiz bir hata kaynağıydı: yazım hatası yapan bir istemci
    "abone oldum" cevabı alıp hiç veri görmüyordu.

    ⚠ AÇIK İŞ — G05 (kamera bazlı yetki)
    Burada henüz KULLANICIYA göre kısıt yok: her doğrulanmış kullanıcı
    tüm kameralara abone olabiliyor. PLAN §11.1 G05 bir
    `user_camera_access` tablosu istiyor (hassas alanlar kısıtlansın).
    Tablo yok, bu yüzden kısıt da yok — ve bu eksik raporda böyle
    yazılacak, "yapıldı" diye değil.
    """
    tanimli = _tanimli_kameralar()
    clean: list[str] = []
    for name in requested[:MAX_SUBSCRIPTIONS]:
        if not isinstance(name, str):
            continue
        if name in tanimli:
            clean.append(name)
        else:
            log.debug("bilinmeyen_kamera_abonelik_reddedildi", istenen=name[:64])
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
            # Oturum kimliğiyle yazılıyor: iki panel birbirinin
            # listesini ezmesin (bkz. bus/streams.py · WATCHED_PREFIX)
            _publish_watched(client.session_id, watched)
        elif kind == "ping":
            await client.websocket.send_text(json.dumps({"type": "pong", "ts": time.time()}))



# ─── İzlenen kameraların yayınlanması ────────────────────────

_watch_client: Any = None


def _publish_watched(session_id: str, cameras: list[str]) -> None:
    """İzlenen kamera listesini alım worker'ının okuyacağı yere yazar.

    Oturum kimliğiyle yazılır — iki panel açıkken biri diğerinin
    listesini silmesin (bkz. bus/streams.py · WATCHED_PREFIX).

    Hata yutuluyor: bu bir optimizasyon sinyali, kritik yol değil.
    Valkey erişilemezse sistem varsayılan hızlarla çalışmaya devam eder.
    """
    global _watch_client
    try:
        if _watch_client is None:
            from sentinel.bus.streams import connect

            _watch_client = connect()
        from sentinel.bus.streams import set_watched_cameras

        set_watched_cameras(_watch_client, session_id, cameras)
    except Exception as exc:  # pragma: no cover
        log.debug("izlenen_kamera_yayinlanamadi", error=str(exc))

@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    host_header = websocket.headers.get("host")
    # Bağlantının kendi şeması: ws → sayfa http'den, wss → https'den
    # servis ediliyor demektir. Aynı köken karşılaştırması şemayı da
    # kapsasın diye geçiliyor (bkz. _same_origin).
    scheme = "https" if websocket.url.scheme == "wss" else "http"
    if not origin_allowed(origin, host_header, scheme):
        # Bağlantıyı KABUL ETMEDEN reddet — el sıkışma tamamlanmasın
        log.warning("ws_origin_reddedildi", origin=origin or "(yok)", host=host_header)
        await websocket.close(code=CLOSE_POLICY_VIOLATION, reason="origin not allowed")
        return

    # ⚠ ORIGIN DOĞRULAMASI KİMLİK DOĞRULAMASI DEĞİL
    # `Origin` yalnızca "bu istek hangi sayfadan geldi" der; tarayıcı
    # dışı bir istemci onu istediği gibi yazabilir. Kimin bağlandığını
    # ancak token söyler.
    #
    # ⚠ TOKEN ÇEREZDEN OKUNUYOR, başlıktan değil. Tarayıcının WebSocket
    # API'si özel başlık eklemeye izin vermiyor; çerez ise el sıkışmada
    # kendiliğinden gidiyor. Bu yüzden erişim tokenı `httponly` çerez
    # olarak da veriliyor (routers/oturum.py · _cerez_koy).
    #
    # ⚠ 1008 (policy violation) ile kapatılıyor, kabul edilmeden.
    # Kabul edip sonra kapatmak, kimliksiz istemciye bir an için de
    # olsa açık bir kanal vermek demekti.
    token = websocket.cookies.get("sentinel_token")
    if not token:
        log.warning("ws_kimliksiz_reddedildi", origin=origin or "(yok)")
        await websocket.close(code=CLOSE_POLICY_VIOLATION, reason="authentication required")
        return
    try:
        govde = token_coz(token)
    except HTTPException:
        log.warning("ws_gecersiz_token", origin=origin or "(yok)")
        await websocket.close(code=CLOSE_POLICY_VIOLATION, reason="invalid token")
        return

    await websocket.accept()
    log.info("ws_baglandi", kullanici=govde.get("sub"), rol=govde.get("rol"))
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
