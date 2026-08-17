"""Altyapı sağlık kontrolleri.

Her bağımlı servise gerçek bir istek atar — "port açık mı" değil,
"servis gerçekten çalışıyor mu" sorusunu cevaplar. Örneğin Valkey için
PING, PostgreSQL için gerçek bir sorgu çalıştırılır.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from sentinel.config import settings
from sentinel.logging import get_logger

log = get_logger(__name__)

# İlk bağlantı (havuz oluşturma, TCP el sıkışma) soğuk başlangıçta
# yavaştır; 5 sn sağlıklı bir servisi yanlışlıkla "ölü" saymamak için
# yeterli pay bırakır. Bkz. docs/report/problems.md · P-03
_TIMEOUT = 5.0


@dataclass(slots=True)
class ServiceStatus:
    """Tek bir servisin sağlık durumu."""

    name: str
    healthy: bool
    latency_ms: float | None = None
    version: str | None = None
    detail: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "version": self.version,
            "detail": self.detail,
            **({"extra": self.extra} if self.extra else {}),
        }


class ServiceUnhealthyError(RuntimeError):
    """Servis CEVAP VERİYOR ama işlevsel değil.

    ⚠ Bu ayrım pahalıya öğrenildi (docs/report/problems.md · P-22).
    Bir servisin "ayakta" olması ile "işini yapıyor" olması aynı şey
    değildir. MediaMTX'in yönetim API'si cevap veriyordu, konteyner
    "healthy" görünüyordu, panel yeşildi — ama hiçbir kamera yayında
    değildi ve sistem saatlerce boş çalıştı.

    Bir sağlık kontrolü "bağlanabildim mi" değil, **"bu servis şu an
    işe yarıyor mu"** sorusunu cevaplamalı.
    """

    def __init__(
        self,
        detail: str,
        *,
        version: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.version = version
        self.extra = extra or {}


async def _timed(name: str, coro: Any) -> ServiceStatus:
    """Bir kontrolü süre ölçerek ve hatayı yutarak çalıştırır."""
    started = time.perf_counter()
    try:
        version, detail, extra = await asyncio.wait_for(coro, timeout=_TIMEOUT)
        return ServiceStatus(
            name=name,
            healthy=True,
            latency_ms=(time.perf_counter() - started) * 1000,
            version=version,
            detail=detail,
            extra=extra or {},
        )
    except ServiceUnhealthyError as exc:
        return ServiceStatus(
            name=name,
            healthy=False,
            latency_ms=(time.perf_counter() - started) * 1000,
            version=exc.version,
            detail=exc.detail,
            extra=exc.extra,
        )
    except TimeoutError:
        return ServiceStatus(name=name, healthy=False, detail=f"zaman aşımı (>{_TIMEOUT}s)")
    except Exception as exc:
        return ServiceStatus(name=name, healthy=False, detail=f"{type(exc).__name__}: {exc}")


# ─── Tekil kontroller ────────────────────────────────────────


async def _probe_valkey() -> tuple[str | None, str | None, dict[str, Any]]:
    client: Redis = Redis.from_url(settings.effective_valkey_url, socket_timeout=_TIMEOUT)
    try:
        await client.ping()
        info = await client.info("server")
        mem = await client.info("memory")
        version = info.get("valkey_version") or info.get("redis_version")
        used = mem.get("used_memory_human", "?")
        return str(version), f"bellek {used}", {"used_memory": used}
    finally:
        await client.aclose()


async def _probe_postgres() -> tuple[str | None, str | None, dict[str, Any]]:
    engine = create_async_engine(settings.effective_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            pg = (await conn.execute(text("SHOW server_version"))).scalar_one()
            ts = (
                await conn.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
                )
            ).scalar_one_or_none()
        return str(pg), f"TimescaleDB {ts}" if ts else "TimescaleDB YOK", {"timescaledb": ts}
    finally:
        await engine.dispose()


async def _probe_mediamtx() -> tuple[str | None, str | None, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{settings.mediamtx_api_url}/v3/paths/list")
        resp.raise_for_status()
        items = resp.json().get("items", [])
    ready = [i["name"] for i in items if i.get("ready")]
    payload = {
        "paths": [
            {
                "name": i["name"],
                "ready": bool(i.get("ready")),
                "readers": len(i.get("readers") or []),
            }
            for i in items
        ]
    }

    # ⚠ SIFIR KAMERA YAYINDA İSE SAĞLIKLI DEĞİLİZ.
    # MediaMTX ayakta ve API cevap veriyor olabilir; ama tek bir yol
    # bile `ready` değilse sisteme kare girmiyor demektir. Bunu
    # "sağlıklı" saymak, panelin yeşil görünürken sistemin boş
    # çalışmasına yol açıyordu (P-22).
    if items and not ready:
        raise ServiceUnhealthyError(
            f"0/{len(items)} yayında — sisteme kare girmiyor",
            extra=payload,
        )

    return None, f"{len(ready)}/{len(items)} yayında", payload


async def _probe_prometheus() -> tuple[str | None, str | None, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{settings.prometheus_url}/api/v1/targets")
        resp.raise_for_status()
        targets = resp.json()["data"]["activeTargets"]
    up = sum(1 for t in targets if t.get("health") == "up")
    return None, f"{up}/{len(targets)} hedef up", {"targets_up": up, "targets_total": len(targets)}


async def _probe_grafana() -> tuple[str | None, str | None, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{settings.grafana_url}/api/health")
        resp.raise_for_status()
        data = resp.json()
    return data.get("version"), f"veritabanı: {data.get('database')}", {}


# ─── Toplu kontrol ───────────────────────────────────────────


async def check_all() -> dict[str, Any]:
    """Tüm servisleri paralel kontrol eder."""
    statuses = await asyncio.gather(
        _timed("Valkey", _probe_valkey()),
        _timed("PostgreSQL", _probe_postgres()),
        _timed("MediaMTX", _probe_mediamtx()),
        _timed("Prometheus", _probe_prometheus()),
        _timed("Grafana", _probe_grafana()),
    )
    healthy = all(s.healthy for s in statuses)
    if not healthy:
        log.warning(
            "saglik_kontrolu_basarisiz",
            failing=[s.name for s in statuses if not s.healthy],
        )
    return {
        "healthy": healthy,
        "checked_at": time.time(),
        "services": [s.as_dict() for s in statuses],
    }


__all__ = ["ServiceStatus", "check_all"]
