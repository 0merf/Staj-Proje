"""SENTINEL FastAPI uygulaması.

Kapsam: kimlik doğrulama + RBAC, kamera envanteri, canlı sonuç
WebSocket'i, olay geçmişi, sağlık kontrolleri, Prometheus metrikleri
ve React SPA servisi.

⚠ 03.09.2026 — BU BAŞLIK 17 GÜN BAYAT KALDI
Önceki hâli şuydu: *"Faz 0 kapsamı: sağlık kontrolleri, metrikler ve
geliştirme durum paneli. Kimlik doğrulama, kamera CRUD ve WebSocket
katmanı sonraki fazlarda eklenecek."*

Üçü de eklendi (Gün 5 WebSocket, Gün 16 kimlik doğrulama) ama dosyanın
başındaki cümle Faz 0'da kalmıştı. Mimari kural 0: belgede yazan ile
kodda olan aynı olmalı. Bir docstring kodun belgesidir ve bayat bir
docstring, kodu yeni okuyan birini doğrudan yanlış yönlendirir —
"burada kimlik doğrulaması yok" diye okuyup korumasız bir uç eklemek
tam olarak bu şekilde olur.

Uç noktaların yetki tablosu aşağıda, `system_health` üstünde.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from sentinel import metrics
from sentinel.api import cameras, health, webcam
from sentinel.api.guvenlik import Kullanici, Rol, mevcut_kullanici, rol_gerekli
from sentinel.api.routers import olaylar as olaylar_router
from sentinel.api.routers import oturum as oturum_router
from sentinel.api.ws import live as ws_live
from sentinel.api.ws.manager import broadcaster
from sentinel.config import settings
from sentinel.logging import configure_logging, get_logger

STATIC_DIR = Path(__file__).parent / "static"

configure_logging(settings.log_level, json_output=settings.sentinel_env == "production")
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log.info(
        "sentinel_baslatiliyor",
        env=settings.sentinel_env,
        port=settings.api_port,
        camera_count=settings.camera_count,
        target_fps=settings.target_fps,
    )
    # Sonuç yayıncısı: inference.results akışını TEK okuyucu takip eder,
    # WebSocket istemcilerine dağıtır (api/ws/manager.py)
    await broadcaster.start()

    # ⚠ Kullanıcı ve denetim tabloları AÇILIŞTA kuruluyor (idempotent).
    # Elle migration gerektiren bir sistem, bir bileşen yeniden
    # başladığında sessizce çalışmaz duruma gelir.
    #
    # ⚠ Başarısızlık API'yi DURDURMUYOR: veritabanı geçici olarak
    # erişilemezse panelin video ve canlı analiz yolu çalışmaya devam
    # etmeli. Giriş uçları o sırada 503 dönecek — ki doğrusu da bu.
    try:
        from sentinel.db import kullanicilar
        from sentinel.db.engine import motor

        async with motor().begin() as baglanti:
            await kullanicilar.semayi_kur(baglanti)
        log.info("kullanici_semasi_hazir")
    except Exception as exc:
        log.error(
            "kullanici_semasi_kurulamadi",
            error=f"{type(exc).__name__}: {exc}",
            etki="giris uclari calismayacak",
        )

    yield
    await broadcaster.stop()
    log.info("sentinel_kapatiliyor")


app = FastAPI(
    title="SENTINEL API",
    description="Çok kameralı akıllı gözetim sistemi",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# CORS — yalnızca beyaz listedeki origin'ler
# ⚠ Bu WebSocket'i KAPSAMAZ. WS el sıkışması CORS'a uymaz; `Origin`
#   başlığı orada ELLE doğrulanıyor (`api/ws/live.py · origin_allowed`,
#   PLAN.md §11.1 / G06). Bu ayrımı bilmemek yaygın bir açık kaynağı:
#   CORS ayarlandı diye WebSocket'in de korunduğu sanılıyor.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def _istek_olc(request: Any, call_next: Any) -> Any:
    """Her isteği sayar (PLAN §13.1 · `sentinel_http_requests_total`).

    ⚠ YOL ŞABLONU KULLANILIYOR, HAM YOL DEĞİL
    `/api/v1/events?camera=cam-03` gibi bir yolu olduğu gibi etiket
    yapmak, Prometheus'ta **kardinalite patlaması** demek: her farklı
    sorgu yeni bir zaman serisi üretir ve bir süre sonra Prometheus'u
    dize etiketleriyle boğar. FastAPI'nin eşleştirdiği rota şablonu
    (`/api/v1/events`) sabit sayıda seri üretiyor.

    ⚠ Eşleşmeyen istekler (404) tek bir "bilinmeyen" etiketinde
    toplanıyor — aksi hâlde rastgele yol deneyen bir tarayıcı
    (saldırgan ya da bot) metrik deposunu şişirebilirdi. Bu, ölçüm
    ucunun kendisinin bir saldırı yüzeyi olduğu az bilinen bir durum.
    """
    yanit = await call_next(request)
    rota = request.scope.get("route")
    yol = getattr(rota, "path", None) or "bilinmeyen"
    metrics.http_requests.labels(
        method=request.method, path=yol, status=str(yanit.status_code)
    ).inc()
    return yanit


# ─── Sağlık ve durum ─────────────────────────────────────────


# ⚠ HANGİ UÇ NEDEN KORUNUYOR — karar tablosu
#
#   /system/live      AÇIK      canlılık probu; yalnızca "ayaktayım" der.
#                               `start_all.ps1` bununla doğruluyor ve
#                               izleme sistemleri kimlik taşımaz.
#   /metrics          AÇIK      Prometheus kazıyor. 127.0.0.1'e bağlı;
#                               dışa açılırsa Caddy'de korunacak (PLAN §10).
#   /system/health    viewer    servis sürümlerini ve iç durumu sızdırıyor
#   /system/config    viewer    kamera sayısı, FPS, iç yapılandırma
#   /cameras          viewer    kamera listesi
#   /events*          viewer    olay geçmişi
#   /cameras/webcam/* OPERATOR  ⚠ YENİ bir kamera açıyor — mahremiyet
#                               açısından okumaktan tamamen farklı
#   /auth/denetim     admin     kimin ne zaman çalıştığını gösteriyor
@app.get("/api/v1/system/health", tags=["system"])
async def system_health(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> JSONResponse:
    """Tüm altyapı servislerinin gerçek sağlık durumu."""
    result = await health.check_all()
    return JSONResponse(result, status_code=200 if result["healthy"] else 503)


app.include_router(ws_live.router)
# Olay geçmişi — canlı WebSocket'in kalıcı karşılığı
app.include_router(oturum_router.router)
app.include_router(olaylar_router.router)


@app.get("/api/v1/system/ws-stats", tags=["system"])
async def ws_stats(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> dict[str, Any]:
    """WebSocket yayıncı istatistikleri."""
    return broadcaster.stats()


@app.get("/api/v1/cameras", tags=["cameras"])
async def list_cameras(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
    include_test: bool = False,
) -> dict[str, Any]:
    """Tanımlı tüm kameralar + anlık yayın durumu.

    Varsayılan olarak **20 çiftlik kamerası + 1 canlı webcam** döner.
    Sentetik test yolları (`cam-test-*`) kamera değil test aparatıdır ve
    listeye girmez; `?include_test=true` ile görülebilirler.

    Not: MediaMTX yalnızca AKTİF yolları listeler; regex ile tanımlı
    cam-02…cam-20 biri bağlanana kadar görünmez. Bu uç nokta tanımlı
    listeyi kamera çiftliği manifestinden alıp durumla birleştirir.
    """
    return await cameras.list_cameras(include_test=include_test)


@app.get("/api/v1/cameras/webcam", tags=["cameras"])
async def webcam_status(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> dict[str, Any]:
    """Webcam yayını çalışıyor mu?"""
    return webcam.controller.status()


@app.post("/api/v1/cameras/webcam/start", tags=["cameras"])
async def webcam_start(
    kullanici: Annotated[Kullanici, Depends(rol_gerekli(Rol.OPERATOR))],
    device: int = 0,
) -> JSONResponse:
    """Webcam yayınını başlatır (cam-21-live).

    ⚠ Kamera yalnızca bu çağrıyla açılır — kendiliğinden açılmaz.

    ⚠ 03.09.2026 — DENETİM KAYDI BURADA EKSİKTİ (G19)
    `operator` rolü Gün 16'da zorunlu kılınmıştı ama yanındaki not
    hâlâ *"Faz 1'de rol ve denetim kaydı zorunlu olacak"* diyordu.
    Rol gelmişti, **denetim kaydı gelmemişti** — ve not bayat olduğu
    için eksik görünmez hâle gelmişti.

    Bu, denetim izinin en çok gerektiği eylem: sistemdeki diğer her uç
    var olan bir görüntüyü OKUYOR, bu uç **yeni bir kamera açıyor.**
    PLAN §11.1/G19 zaten "kamera görüntüleme" için denetim istiyordu;
    kamera AÇMA, okumadan daha ağır bir eylem.

    ⚠ Denetim kaydı sonuçtan BAĞIMSIZ yazılıyor (`basarili` alanıyla).
    Başarısız bir açma denemesi de kayda değer: niyet gerçekleşmiş
    olmasa da beyan edilmiştir.
    """
    try:
        result = webcam.controller.start(device)
    except (ValueError, FileNotFoundError) as exc:
        await _denetim("webcam_baslat", kullanici, basarili=False,
                       ayrinti={"device": device, "hata": str(exc)[:200]})
        return JSONResponse({"started": False, "reason": str(exc)}, status_code=400)
    await _denetim(
        "webcam_baslat", kullanici,
        basarili=bool(result.get("started")),
        ayrinti={"device": device},
    )
    return JSONResponse(result, status_code=200 if result.get("started") else 409)


@app.post("/api/v1/cameras/webcam/stop", tags=["cameras"])
async def webcam_stop(
    kullanici: Annotated[Kullanici, Depends(rol_gerekli(Rol.OPERATOR))],
) -> dict[str, Any]:
    """Webcam yayınını durdurur. Denetime yazılır (G19)."""
    sonuc = webcam.controller.stop()
    await _denetim("webcam_durdur", kullanici, basarili=True)
    return sonuc


async def _denetim(
    eylem: str,
    kullanici: Kullanici,
    *,
    basarili: bool = True,
    ayrinti: dict[str, Any] | None = None,
) -> None:
    """Denetim izine yazar — hata isteği DÜŞÜRMEZ.

    ⚠ Bu takas bilinçli ve tartışmalı olduğu için yazılıyor:
    denetim kaydı yazılamazsa istek yine de işleniyor. Alternatif,
    veritabanı erişilemezken kamera açmayı tümden engellemekti.

    Yüksek güvenlikli bir kurulumda doğru seçim TERSİ olurdu:
    "denetlenemeyen eylem yapılamaz". Bu bir staj/demo kurulumu ve
    veritabanı arızasının tüm operasyonu durdurması orantısız —
    ama karar raporda böyle, gerekçesiyle yazılacak. Sessizce
    "denetim var" demek olmaz.
    """
    try:
        from sentinel.db import kullanicilar as depo

        await depo.denetim_yaz(
            eylem,
            kullanici_adi=kullanici.kullanici_adi,
            basarili=basarili,
            ayrinti=ayrinti,
        )
    except Exception as exc:  # pragma: no cover
        log.error("denetim_yazilamadi", eylem=eylem, error=f"{type(exc).__name__}: {exc}")


@app.get("/api/v1/system/live", tags=["system"])
async def liveness() -> dict[str, Any]:
    """Uygulamanın kendisi ayakta mı? (bağımlılıklara bakmaz)"""
    return {"status": "ok", "version": app.version, "env": settings.sentinel_env}


@app.get("/api/v1/system/config", tags=["system"])
async def public_config(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> dict[str, Any]:
    """Arayüzün ihtiyaç duyduğu, sır İÇERMEYEN ayarlar.

    ⚠ 03.09.2026 — `privacy_blur_default` BU YANITTAN ÇIKARILDI
    Bu alan `true` dönüyordu ve sistemde hiçbir bulanıklaştırma yoktu;
    ön yüz de alanı hiç okumuyordu. Yani API, yapmadığı bir şeyi
    yaptığını beyan ediyordu — en kötü tür hata, çünkü kimse
    kontrol etmeye gerek duymaz. Yüz bulanıklaştırma bu staj
    kapsamının dışında (bkz. config.py ve raporun kapsam bölümü).
    """
    return {
        "env": settings.sentinel_env,
        "camera_count": settings.camera_count,
        "target_fps": settings.target_fps,
        "motion_gate_enabled": settings.motion_gate_enabled,
        "urls": {
            "webrtc": settings.mediamtx_webrtc_url,
            "grafana": settings.grafana_url,
            "prometheus": settings.prometheus_url,
        },
    }


@app.get("/metrics", include_in_schema=False)
async def metrik_ucu() -> Response:
    """Prometheus metrik uç noktası.

    ⚠ Fonksiyon adı `metrics` DEĞİL: `sentinel.metrics` modülü bu
    dosyaya `metrics` adıyla aktarılıyor ve aynı adı kullanmak modülü
    gölgeliyordu. Yol (`/metrics`) değişmedi — yalnızca Python adı.
    """
    if not settings.metrics_enabled:
        return Response(status_code=404)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ─── Geliştirme durum paneli ─────────────────────────────────


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    """Geliştirme durum paneli.

    Bu tek dosyalık panel, React arayüzü hazır olana kadar sistemin
    gözle doğrulanmasını sağladı. React SPA (Gün 10) devreye girdikten
    sonra da **kasten duruyor**: React derlemesi bozulduğunda ya da
    Node ortamı yokken sistemi doğrulayabilmek için bağımsız bir
    yedek gerekiyor. Çok az bakım istiyor.
    """
    return FileResponse(STATIC_DIR / "index.html")


# ─── React SPA ───────────────────────────────────────────────
# `cd frontend && npm run build` çıktısı buraya derleniyor.
# Geliştirme sırasında Vite sunucusu (127.0.0.1:5173) kullanılır;
# burası derlenmiş sürümü Node olmadan servis eder.
_SPA_DIR = STATIC_DIR / "app"
if (_SPA_DIR / "index.html").is_file():
    app.mount("/app", StaticFiles(directory=_SPA_DIR, html=True), name="spa")
else:
    @app.get("/app", include_in_schema=False)
    async def spa_missing() -> Response:
        return Response(
            "React arayüzü henüz derlenmedi.\n"
            "  cd frontend && npm install && npm run build\n"
            "Geliştirme için: cd frontend && npm run dev  →  http://127.0.0.1:5173",
            media_type="text/plain; charset=utf-8",
            status_code=503,
        )
