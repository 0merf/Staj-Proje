"""SENTINEL FastAPI uygulaması.

Faz 0 kapsamı: sağlık kontrolleri, metrikler ve geliştirme durum paneli.
Kimlik doğrulama, kamera CRUD ve WebSocket katmanı sonraki fazlarda eklenecek.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from sentinel.api import cameras, health, webcam
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
# ⚠ Bu WebSocket'i KAPSAMAZ. WS için Origin başlığı elle doğrulanacak
#   (PLAN.md §11.1 / G06) — Faz 1'de eklenecek.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Sağlık ve durum ─────────────────────────────────────────


@app.get("/api/v1/system/health", tags=["system"])
async def system_health() -> JSONResponse:
    """Tüm altyapı servislerinin gerçek sağlık durumu."""
    result = await health.check_all()
    return JSONResponse(result, status_code=200 if result["healthy"] else 503)


app.include_router(ws_live.router)


@app.get("/api/v1/system/ws-stats", tags=["system"])
async def ws_stats() -> dict[str, Any]:
    """WebSocket yayıncı istatistikleri."""
    return broadcaster.stats()


@app.get("/api/v1/cameras", tags=["cameras"])
async def list_cameras() -> dict[str, Any]:
    """Tanımlı tüm kameralar + anlık yayın durumu.

    Not: MediaMTX yalnızca AKTİF yolları listeler; regex ile tanımlı
    cam-02…cam-20 biri bağlanana kadar görünmez. Bu uç nokta tanımlı
    listeyi kamera çiftliği manifestinden alıp durumla birleştirir.
    """
    return await cameras.list_cameras()


@app.get("/api/v1/cameras/webcam", tags=["cameras"])
async def webcam_status() -> dict[str, Any]:
    """Webcam yayını çalışıyor mu?"""
    return webcam.controller.status()


@app.post("/api/v1/cameras/webcam/start", tags=["cameras"])
async def webcam_start(device: int = 0) -> JSONResponse:
    """Webcam yayınını başlatır (cam-21-live).

    ⚠ Kamera yalnızca bu çağrıyla açılır — kendiliğinden açılmaz.
    Faz 1'de `operator+` rolü ve denetim kaydı zorunlu olacak (G19).
    """
    try:
        result = webcam.controller.start(device)
    except (ValueError, FileNotFoundError) as exc:
        return JSONResponse({"started": False, "reason": str(exc)}, status_code=400)
    return JSONResponse(result, status_code=200 if result.get("started") else 409)


@app.post("/api/v1/cameras/webcam/stop", tags=["cameras"])
async def webcam_stop() -> dict[str, Any]:
    """Webcam yayınını durdurur."""
    return webcam.controller.stop()


@app.get("/api/v1/system/live", tags=["system"])
async def liveness() -> dict[str, Any]:
    """Uygulamanın kendisi ayakta mı? (bağımlılıklara bakmaz)"""
    return {"status": "ok", "version": app.version, "env": settings.sentinel_env}


@app.get("/api/v1/system/config", tags=["system"])
async def public_config() -> dict[str, Any]:
    """Arayüzün ihtiyaç duyduğu, sır İÇERMEYEN ayarlar."""
    return {
        "env": settings.sentinel_env,
        "camera_count": settings.camera_count,
        "target_fps": settings.target_fps,
        "motion_gate_enabled": settings.motion_gate_enabled,
        "privacy_blur_default": settings.privacy_blur_default,
        "urls": {
            "webrtc": settings.mediamtx_webrtc_url,
            "grafana": settings.grafana_url,
            "prometheus": settings.prometheus_url,
        },
    }


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrik uç noktası."""
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
