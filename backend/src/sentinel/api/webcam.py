"""Webcam yayınının panelden kontrolü.

⚠ GÜVENLİK NOTU
---------------
Bu modül bir işletim sistemi süreci başlatıyor. Böyle bir yetenek dikkatli
tasarlanmalı:

* Komut **sabit** bir argüman listesiyle çalışır — `shell=True` yok,
  kullanıcı girdisi komuta katılmaz (PLAN.md §11.1 / G09).
* Tek değişken parametre kamera indeksi; tamsayı ve dar bir aralıkla
  sınırlandırılmıştır.
* Aynı anda tek yayın olabilir.
* Her başlatma/durdurma **loglanır** — Faz 1'de denetim kaydına (G19)
  ve `operator+` rol kontrolüne bağlanacak. Şu an API kimlik doğrulaması
  olmadığı için uç nokta yalnızca 127.0.0.1'e bağlı.

Mahremiyet: kamera **kendiliğinden açılmaz.** Yalnızca açık bir istek
üzerine başlar ve istendiğinde durur.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import Any

from sentinel.config import PROJECT_ROOT
from sentinel.logging import get_logger

log = get_logger(__name__)

PUBLISH_SCRIPT = PROJECT_ROOT / "backend" / "scripts" / "publish_webcam.py"
BACKEND_DIR = PROJECT_ROOT / "backend"

MAX_DEVICE_INDEX = 8
_lock = threading.Lock()


class WebcamController:
    """Webcam yayıncı sürecini yönetir. Tek örnek (singleton) kullanılır."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._started_at: float | None = None
        self._device: int | None = None

    # ─── Durum ───────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def status(self) -> dict[str, Any]:
        if not self.running:
            # Süreç kendiliğinden ölmüşse durumu temizle
            if self._process is not None:
                code = self._process.poll()
                log.info("webcam_sureci_sonlandi", exit_code=code)
                self._reset()
            return {"running": False, "device": None, "uptime_s": None}
        return {
            "running": True,
            "device": self._device,
            "uptime_s": round(time.monotonic() - (self._started_at or 0), 1),
        }

    def _reset(self) -> None:
        self._process = None
        self._started_at = None
        self._device = None

    # ─── Kontrol ─────────────────────────────────────────────

    def start(self, device: int = 0) -> dict[str, Any]:
        if not isinstance(device, int) or not 0 <= device <= MAX_DEVICE_INDEX:
            raise ValueError(f"Geçersiz kamera indeksi: {device}")
        if not PUBLISH_SCRIPT.is_file():
            raise FileNotFoundError(f"Yayıncı betiği yok: {PUBLISH_SCRIPT}")

        with _lock:
            if self.running:
                return {"started": False, "reason": "zaten çalışıyor", **self.status()}

            # Sabit argüman listesi — kabuk yok, enjeksiyon yok
            command = [
                sys.executable,
                str(PUBLISH_SCRIPT),
                "--device",
                str(device),
            ]
            log.info("webcam_baslatiliyor", device=device)  # ileride denetim kaydına
            self._process = subprocess.Popen(  # noqa: S603 — sabit komut, kabuk yok
                command,
                cwd=str(BACKEND_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._started_at = time.monotonic()
            self._device = device

        # Sürecin ilk saniyede çökmediğini doğrula (kamera meşgul olabilir)
        time.sleep(1.5)
        if not self.running:
            self._reset()
            return {
                "started": False,
                "reason": "yayıncı başlar başlamaz kapandı — kamera başka bir "
                "uygulama tarafından kullanılıyor olabilir",
                "running": False,
            }
        return {"started": True, **self.status()}

    def stop(self) -> dict[str, Any]:
        with _lock:
            if not self.running or self._process is None:
                self._reset()
                return {"stopped": False, "reason": "çalışmıyor", "running": False}

            log.info("webcam_durduruluyor", device=self._device)
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning("webcam_zorla_kapatiliyor")
                self._process.kill()
                self._process.wait(timeout=3)
            self._reset()
        return {"stopped": True, "running": False}


controller = WebcamController()

__all__ = ["WebcamController", "controller"]
