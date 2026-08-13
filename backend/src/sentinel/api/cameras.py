"""Kamera envanteri.

MediaMTX'in `/v3/paths/list` uç noktası yalnızca **o an aktif** yolları
döndürür. Kamera çiftliği regex yolu (`~^cam-(0[1-9]|1[0-9]|20)$`)
kullandığı için cam-02…cam-20 ancak biri bağlandığında listede belirir.
Bu yüzden "tanımlı kamera listesi" ayrı bir kaynaktan gelmeli.

Şimdilik kaynak: `data/videos/manifest.json` (kamera çiftliği betiğinin
çıktısı). Faz 1'de bu liste PostgreSQL'deki `cameras` tablosuna taşınacak;
arayüz sözleşmesi aynı kalacağı için ön yüz etkilenmeyecek.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from sentinel.config import PROJECT_ROOT, settings
from sentinel.logging import get_logger

log = get_logger(__name__)

FARM_MANIFEST = PROJECT_ROOT / "data" / "videos" / "manifest.json"

# Çiftlik dışındaki sabit yollar (mediamtx.yml'de elle tanımlı)
STATIC_PATHS: list[dict[str, str]] = [
    {"name": "cam-test-motion", "label": "Test — hareketli desen", "kind": "synthetic"},
    {"name": "cam-test-chaos", "label": "Test — piksel gürültüsü", "kind": "synthetic"},
    {"name": "cam-test-static", "label": "Test — tamamen durağan", "kind": "synthetic"},
    {"name": "cam-21-live", "label": "Kamera 21 — canlı webcam", "kind": "webcam"},
]


@dataclass(slots=True)
class Camera:
    """Bir kameranın tanımı + anlık durumu."""

    name: str
    label: str
    kind: str  # "farm" | "synthetic" | "webcam"
    ready: bool = False
    readers: int = 0
    source: str | None = None
    duration_s: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "ready": self.ready,
            "readers": self.readers,
            "source": self.source,
            "duration_s": self.duration_s,
            **({"extra": self.extra} if self.extra else {}),
        }


def _load_farm() -> list[Camera]:
    """Kamera çiftliği manifestini okur."""
    if not FARM_MANIFEST.is_file():
        return []
    try:
        entries = json.loads(FARM_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("ciftlik_manifesti_okunamadi", error=str(exc))
        return []

    cameras: list[Camera] = []
    for entry in entries:
        name = entry.get("camera")
        if not name:
            continue
        cameras.append(
            Camera(
                name=name,
                label=str(entry.get("label") or name),
                kind="farm",
                source=str(entry.get("source") or ""),
                duration_s=entry.get("duration_s"),
            )
        )
    return cameras


async def _runtime_state() -> dict[str, dict[str, Any]]:
    """MediaMTX'ten anlık yol durumlarını çeker."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.mediamtx_api_url}/v3/paths/list")
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception as exc:
        log.warning("mediamtx_durumu_alinamadi", error=str(exc))
        return {}

    return {
        item["name"]: {
            "ready": bool(item.get("ready")),
            "readers": len(item.get("readers") or []),
        }
        for item in items
        if not item["name"].startswith("~")  # regex kalıbının kendisi kamera değil
    }


async def list_cameras() -> dict[str, Any]:
    """Tanımlı tüm kameralar + anlık yayın durumları."""
    cameras = _load_farm()
    cameras += [
        Camera(name=p["name"], label=p["label"], kind=p["kind"]) for p in STATIC_PATHS
    ]

    state = await _runtime_state()
    known = {c.name for c in cameras}

    for camera in cameras:
        current = state.get(camera.name)
        if current:
            camera.ready = current["ready"]
            camera.readers = current["readers"]

    # MediaMTX'te olup manifestte olmayan yollar (elle eklenmiş olabilir)
    for name, current in state.items():
        if name not in known:
            cameras.append(
                Camera(
                    name=name,
                    label=name,
                    kind="unknown",
                    ready=current["ready"],
                    readers=current["readers"],
                )
            )

    cameras.sort(key=lambda c: (c.kind != "farm", c.name))
    ready = sum(1 for c in cameras if c.ready)
    return {
        "total": len(cameras),
        "ready": ready,
        "cameras": [c.as_dict() for c in cameras],
    }


__all__ = ["Camera", "list_cameras"]
