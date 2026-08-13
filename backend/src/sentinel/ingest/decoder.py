"""RTSP akışından kare okuma (PyAV).

Neden PyAV, neden `subprocess` ile ffmpeg değil
-----------------------------------------------
PyAV, FFmpeg'in C kütüphanelerine doğrudan bağlanır. Kabuğa (shell)
hiç çıkmadığımız için kamera URL'sinden komut enjeksiyonu riski YOKTUR
(PLAN.md §11.1 / G09). Ayrıca kareyi bellekten alırız — boru üzerinden
ham bayt kopyalamaya gerek kalmaz.

Kare örnekleme hakkında dürüst bir not
--------------------------------------
H.264 kareler arası kodlamalıdır: 4. kareyi çözmek için önceki kareleri
de çözmek gerekir. Yani "25 FPS'ten 4 FPS'e düşürmek" decode maliyetini
düşürmez — sadece pahalı YZ modellerine giden kare sayısını düşürür.
Decode yükünü azaltmanın yolu donanımsal çözücüdür (NVDEC).
Ölçümler Gün 3'te yapılacak; şimdilik CPU decode ile başlıyoruz.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from types import TracebackType

import av
import av.error
import numpy as np

from sentinel.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class DecodedFrame:
    """Çözülmüş ve örneklenmiş bir kare."""

    camera_id: str
    sequence: int
    timestamp: float  # monotonik saat (saniye)
    pts_seconds: float  # akış içindeki sunum zamanı
    image: np.ndarray  # BGR, (H, W, 3) uint8


class StreamClosedError(RuntimeError):
    """Akış beklenmedik şekilde kapandı."""


class RtspDecoder:
    """Tek bir RTSP akışını okur ve hedef FPS'e örnekler.

    Kullanım:
        with RtspDecoder("rtsp://…/cam-01", camera_id="cam-01") as dec:
            for frame in dec.frames():
                ...
    """

    def __init__(
        self,
        url: str,
        *,
        camera_id: str,
        target_fps: float = 4.0,
        timeout_s: float = 10.0,
        transport: str = "tcp",
    ) -> None:
        """
        Args:
            url: RTSP adresi.
            camera_id: Metriklerde ve mesajlarda kullanılacak kimlik.
            target_fps: Saniyede kaç kare *örnekleneceği* (decode değil).
            timeout_s: Soket zaman aşımı.
            transport: "tcp" önerilir — UDP'de kare kaybı sessizce olur.
        """
        self._url = url
        self._camera_id = camera_id
        self._interval = 1.0 / target_fps if target_fps > 0 else 0.0
        self._timeout_us = str(int(timeout_s * 1_000_000))
        self._transport = transport
        self._container: av.container.InputContainer | None = None
        self._sequence = 0
        self._decoded = 0

    # ─── Bağlam yöneticisi ───────────────────────────────────

    def __enter__(self) -> RtspDecoder:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def open(self) -> None:
        options = {
            "rtsp_transport": self._transport,
            "timeout": self._timeout_us,  # soket zaman aşımı (mikrosaniye)
            "max_delay": "500000",
            "fflags": "nobuffer",
            "flags": "low_delay",
        }
        self._container = av.open(self._url, options=options, timeout=None)
        stream = self._container.streams.video[0]
        # Kare atlamak yerine ÇÖZÜP atıyoruz; thread'li çözme CPU'yu daha iyi kullanır.
        stream.thread_type = "AUTO"
        log.info(
            "akis_acildi",
            camera=self._camera_id,
            codec=stream.codec_context.name,
            width=stream.codec_context.width,
            height=stream.codec_context.height,
            avg_fps=float(stream.average_rate or 0),
        )

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
            self._container = None
            log.info("akis_kapandi", camera=self._camera_id, decoded=self._decoded)

    # ─── Kare üretimi ────────────────────────────────────────

    def frames(self, *, max_frames: int | None = None) -> Iterator[DecodedFrame]:
        """Hedef FPS'e örneklenmiş kareleri üretir.

        Args:
            max_frames: Bu kadar kare ürettikten sonra durur (test için).
        """
        if self._container is None:
            raise StreamClosedError("open() çağrılmadı")

        stream = self._container.streams.video[0]
        time_base = float(stream.time_base or 0) or 1 / 25
        next_emit = 0.0
        emitted = 0

        try:
            for frame in self._container.decode(stream):
                self._decoded += 1
                pts_s = float(frame.pts * time_base) if frame.pts is not None else 0.0

                # Örnekleme: hedef aralık dolmadıysa kareyi at.
                # (Decode maliyeti yine ödendi — yukarıdaki nota bakınız.)
                if self._interval > 0 and pts_s < next_emit:
                    continue
                next_emit = pts_s + self._interval

                self._sequence += 1
                emitted += 1
                yield DecodedFrame(
                    camera_id=self._camera_id,
                    sequence=self._sequence,
                    timestamp=time.monotonic(),
                    pts_seconds=pts_s,
                    image=frame.to_ndarray(format="bgr24"),
                )

                if max_frames is not None and emitted >= max_frames:
                    return
        except av.error.EOFError:
            log.info("akis_bitti", camera=self._camera_id)
        except av.error.FFmpegError as exc:
            raise StreamClosedError(f"{self._camera_id}: {exc}") from exc

    # ─── İstatistik ──────────────────────────────────────────

    @property
    def decoded_count(self) -> int:
        """Çözülen toplam kare (örneklenen değil) — decode yükünün ölçüsü."""
        return self._decoded

    @property
    def emitted_count(self) -> int:
        return self._sequence


def rtsp_url(host: str, port: int, path: str) -> str:
    """RTSP adresi kurar."""
    return f"rtsp://{host}:{port}/{path}"


__all__ = ["DecodedFrame", "RtspDecoder", "StreamClosedError", "rtsp_url"]
