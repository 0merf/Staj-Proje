"""SENTINEL FastAPI uygulaması.

Faz 0 kapsamı: sağlık kontrolleri, metrikler ve geliştirme durum paneli.
Kimlik doğrulama, kamera CRUD ve WebSocket katmanı sonraki fazlarda eklenecek.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from sentinel.api import cameras, health, webcam
from sentinel.api.guvenlik import Kullanici, Rol, mevcut_kullanici, rol_gerekli
from sentinel.api.routers import olaylar as olaylar_router
from sentinel.api.routers import oturum as oturum_router
from sentinel.api.ws import live as ws_live
from sentinel.api.ws.manager import broadcaster
from sentinel.config import PROJECT_ROOT, settings
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
#   /debug/trace      operator  diske dosya yazıyor
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
    Faz 1'de `operator+` rolü ve denetim kaydı zorunlu olacak (G19).
    """
    try:
        result = webcam.controller.start(device)
    except (ValueError, FileNotFoundError) as exc:
        return JSONResponse({"started": False, "reason": str(exc)}, status_code=400)
    return JSONResponse(result, status_code=200 if result.get("started") else 409)


@app.post("/api/v1/cameras/webcam/stop", tags=["cameras"])
async def webcam_stop(
    kullanici: Annotated[Kullanici, Depends(rol_gerekli(Rol.OPERATOR))],
) -> dict[str, Any]:
    """Webcam yayınını durdurur."""
    return webcam.controller.stop()


@app.get("/api/v1/system/live", tags=["system"])
async def liveness() -> dict[str, Any]:
    """Uygulamanın kendisi ayakta mı? (bağımlılıklara bakmaz)"""
    return {"status": "ok", "version": app.version, "env": settings.sentinel_env}


@app.get("/api/v1/system/config", tags=["system"])
async def public_config(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> dict[str, Any]:
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


# ─── Hata ayıklama: çizim izi ────────────────────────────────


def _safe_name(value: str, *, fallback: str = "bilinmeyen", limit: int = 32) -> str:
    """İstemciden gelen bir parçayı dosya adında kullanılabilir hâle getirir.

    Beyaz liste: yalnızca `[A-Za-z0-9_-]`. Kalan her karakter atılır,
    dolayısıyla yol ayracı (`/`, `\\`), üst dizin (`..`), sürücü harfi
    (`C:`) ve boşluk tanım gereği geçemez.

    Boş kalırsa `fallback` döner — aksi hâlde `trace_20260818-101500_.json`
    gibi adsız dosyalar birikirdi.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value)[:limit]
    return cleaned or fallback


@app.post("/api/v1/debug/trace", include_in_schema=False)
async def save_trace(
    payload: dict[str, Any],
    _: Annotated[Kullanici, Depends(rol_gerekli(Rol.OPERATOR))],
) -> dict[str, Any]:
    """Panelin kaydettiği kutu yörüngesini diske yazar.

    Neden var: "kutular takılıyor" gibi bir şikâyeti gözle teşhis etmek
    zor — göz "sıçradı" der ama "kaç piksel, ne zaman, neyle korele"
    diyemez. Panel her çizilen karede kutunun konumunu kaydediyor;
    burada dosyaya alıp sayısal olarak inceliyoruz.

    ⚠ Yalnızca geliştirme ortamında açık. Üretimde kimlik doğrulaması
    olmayan yazma uç noktası bırakılmaz (PLAN.md §11.1).

    ⚠ DOSYA ADI TEMİZLENİR (G12 — path traversal)
    ---------------------------------------------
    `camera` alanı istemciden geliyor ve doğrudan dosya adına giriyordu.
    `{"camera": "../../../etc/onemli"}` gönderen biri `benchmarks/traces`
    DIŞINA yazabilirdi. Kendi Öncelik-1 listemizde G12 tam olarak bunu
    yasaklıyor: "yol sunucuda kurulur, istemciden gelen parça yol
    ayracı içeremez".

    Beyaz liste yaklaşımı kullanılıyor (kara liste değil): yalnızca
    harf, rakam, tire ve alt çizgi geçer. Böylece `..`, `/`, `\\`, ':'
    ve sürücü harfi gibi her şey tanım gereği elenir — tek tek
    saymaya gerek kalmaz.
    """
    if settings.sentinel_env != "development":
        return {"saved": False, "reason": "yalnızca geliştirme ortamında"}

    traces = PROJECT_ROOT / "benchmarks" / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    camera = _safe_name(str(payload.get("camera", "")))
    name = f"trace_{datetime.now():%Y%m%d-%H%M%S}_{camera}.json"
    path = traces / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    log.info("cizim_izi_kaydedildi", path=str(path), samples=len(payload.get("samples", [])))
    return {"saved": True, "path": str(path.relative_to(PROJECT_ROOT))}


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
