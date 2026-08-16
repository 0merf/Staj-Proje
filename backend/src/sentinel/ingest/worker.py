"""Alım (ingest) worker'ı.

Sorumluluğu
-----------
Atanan kameraları RTSP'den okur, Kademe 0 hareket filtresinden geçirir,
geçen kareleri paylaşımlı belleğe yazar ve Valkey'e **yalnızca meta veri**
yayınlar. Ham kare asla kuyruktan geçmez (PLAN.md §4.2).

Neden iş parçacığı (thread), süreç (process) değil
--------------------------------------------------
Python'da CPU-yoğun iş için genelde süreç önerilir çünkü GIL paralelliği
engeller. Ama burada durum farklı: **PyAV ve OpenCV, C kodunda çalışırken
GIL'i bırakır.** Kare çözme ve renk dönüşümü süresinin neredeyse tamamı
GIL dışında geçiyor. Bu yüzden iş parçacıkları gerçekten paralel koşar.

İş parçacığı seçmenin somut faydası: `FramePool` nesnesi tek bir kez
oluşturulup tüm kameralarca paylaşılabiliyor. Süreç kullansaydık her
süreç havuza ayrı bağlanacak, slot sahipliği karmaşıklaşacaktı.

Ölçüm bu kararı doğruladı mı? `--stats` çıktısındaki toplam FPS ile
kamera sayısını karşılaştır: ölçekleniyorsa karar doğru.

Kullanım
--------
    uv run python -m sentinel.ingest.worker --cameras cam-01 cam-02
    uv run python -m sentinel.ingest.worker --all --duration 60
    uv run python -m sentinel.ingest.worker --all --owner --metrics-port 9101
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from types import FrameType

from sentinel import metrics
from sentinel.bus.shm import FramePool, FramePoolError
from sentinel.bus.streams import FrameMessage, FrameStream, SlotAllocator, connect
from sentinel.config import settings
from sentinel.core import preprocess
from sentinel.ingest.decoder import RtspDecoder, StreamClosedError, rtsp_url
from sentinel.ingest.motion_gate import MotionGate
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

_shutdown = threading.Event()


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    log.info("kapatma_sinyali_alindi")
    _shutdown.set()


@dataclass(slots=True)
class CameraStats:
    """Tek kameranın çalışma istatistikleri."""

    camera: str
    received: int = 0
    published: int = 0
    dropped_gate: int = 0
    dropped_no_slot: int = 0
    reconnects: int = 0
    started_at: float = field(default_factory=time.monotonic)
    recent_gate: deque[bool] = field(default_factory=lambda: deque(maxlen=100))

    @property
    def fps(self) -> float:
        elapsed = time.monotonic() - self.started_at
        return self.received / elapsed if elapsed > 0 else 0.0

    @property
    def pass_ratio(self) -> float:
        if not self.recent_gate:
            return 0.0
        return sum(self.recent_gate) / len(self.recent_gate)


class CameraTask:
    """Tek bir kamerayı okuyan iş parçacığı gövdesi."""

    def __init__(
        self,
        camera: str,
        pool: FramePool,
        allocator: SlotAllocator,
        stream: FrameStream,
        *,
        target_fps: float,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.camera = camera
        self.stats = CameraStats(camera=camera)
        self._pool = pool
        self._allocator = allocator
        self._stream = stream
        self._target_fps = target_fps
        self._reconnect_delay = reconnect_delay
        self._gate = MotionGate(
            threshold=settings.motion_threshold,
            refresh_interval_s=float(settings.motion_refresh_interval_s),
        )
        self._url = rtsp_url(settings.mediamtx_host, settings.mediamtx_rtsp_port, camera)

    def run(self) -> None:
        """Kamera düşerse yeniden bağlanarak sonsuza dek okur."""
        while not _shutdown.is_set():
            try:
                metrics.camera_up.labels(cam=self.camera).set(1)
                self._read_stream()
            except StreamClosedError as exc:
                log.warning("akis_koptu", camera=self.camera, error=str(exc))
            except Exception as exc:
                log.error("kamera_hatasi", camera=self.camera, error=f"{type(exc).__name__}: {exc}")

            metrics.camera_up.labels(cam=self.camera).set(0)
            if _shutdown.is_set():
                break

            self.stats.reconnects += 1
            log.info("yeniden_baglaniliyor", camera=self.camera, delay=self._reconnect_delay)
            _shutdown.wait(self._reconnect_delay)

    def _read_stream(self) -> None:
        with RtspDecoder(self._url, camera_id=self.camera, target_fps=self._target_fps) as decoder:
            last = time.perf_counter()
            for frame in decoder.frames():
                if _shutdown.is_set():
                    return

                now = time.perf_counter()
                metrics.decode_duration.labels(cam=self.camera).observe(now - last)
                self.stats.received += 1
                metrics.frames_received.labels(cam=self.camera).inc()

                self._process(frame)

                metrics.camera_fps.labels(cam=self.camera).set(self.stats.fps)
                metrics.motion_gate_ratio.labels(cam=self.camera).set(self.stats.pass_ratio)
                last = time.perf_counter()

    def _process(self, frame: object) -> None:
        image = frame.image  # type: ignore[attr-defined]
        decision = self._gate.evaluate(image, frame.timestamp)  # type: ignore[attr-defined]
        metrics.gate_duration.labels(cam=self.camera).observe(decision.elapsed_ms / 1000.0)
        self.stats.recent_gate.append(decision.process)

        if not decision.process:
            self.stats.dropped_gate += 1
            metrics.frames_dropped.labels(cam=self.camera, reason="gate_idle").inc()
            return

        # Geri basınç: boş slot yoksa kareyi AT, bekleme.
        slot = self._allocator.acquire()
        if slot is None:
            self.stats.dropped_no_slot += 1
            metrics.frames_dropped.labels(cam=self.camera, reason="no_slot").inc()
            return

        try:
            # ─── MODEL GİRDİSİ HAZIRLIĞI ────────────────────
            # Kare paylaşımlı belleğe HAM değil, model uzayında yazılır
            # (640×640 letterbox). Bu iş bilinçli olarak BURADA yapılıyor:
            # burası 20 kamera iş parçacığına dağılıyor ve `cv2.resize`
            # GIL'i bıraktığı için gerçekten paralel koşuyor. Aynı işi
            # TEK süreç olan çıkarım worker'ında yapmak seri kalır ve
            # hiçbir şey kazandırmaz (ölçüldü: net kazanç ~0).
            # Ölçüm ve gerekçe: core/preprocess.py modül başlığı.
            prepared, box = preprocess.letterbox(image)
            ref = self._pool.write(slot, prepared)
            self._stream.publish(
                FrameMessage(
                    message_id="",
                    camera=self.camera,
                    sequence=frame.sequence,  # type: ignore[attr-defined]
                    captured_at=frame.timestamp,  # type: ignore[attr-defined]
                    pts=frame.pts_seconds,  # type: ignore[attr-defined]
                    ref=ref,
                    motion_ratio=decision.foreground_ratio,
                    gate_reason=decision.reason.value,
                    letterbox=box,
                )
            )
        except Exception:
            # Yayınlayamadıysak slotu geri ver, yoksa havuz sızar
            self._allocator.release(slot)
            self.stats.dropped_no_slot += 1
            metrics.frames_dropped.labels(cam=self.camera, reason="publish_error").inc()
            raise
        else:
            self.stats.published += 1
            metrics.frames_published.labels(cam=self.camera).inc()


class IngestWorker:
    """Bir grup kamerayı yöneten worker."""

    def __init__(
        self,
        cameras: list[str],
        *,
        worker_id: str = "ingest-0",
        own_pool: bool = False,
        target_fps: float | None = None,
    ) -> None:
        self.cameras = cameras
        self.worker_id = worker_id
        self._own_pool = own_pool
        self._target_fps = target_fps if target_fps is not None else float(settings.target_fps)
        self._client = connect()
        self._allocator = SlotAllocator(self._client, settings.shm_slot_count)
        self._stream = FrameStream(self._client)
        self._tasks: list[CameraTask] = []
        self._threads: list[threading.Thread] = []

        try:
            self._pool = FramePool(
                slot_count=settings.shm_slot_count,
                slot_bytes=preprocess.slot_bytes(),
                create=own_pool,
            )
        except FramePoolError:
            if own_pool:
                raise
            log.info("havuz_yok_olusturuluyor")
            self._pool = FramePool(
                slot_count=settings.shm_slot_count,
                slot_bytes=preprocess.slot_bytes(),
                create=True,
            )
            self._own_pool = True

        if self._own_pool:
            # SIRA ÖNEMLİ: önce akışı temizle, sonra slotları dağıt.
            # Ters sırada, eski mesajları okuyan bir tüketici slotları
            # ikinci kez serbest bırakır ve havuz bozulur (P-10).
            self._stream.reset()
            self._allocator.reset()

    def start(self) -> None:
        log.info(
            "ingest_worker_basliyor",
            worker=self.worker_id,
            cameras=len(self.cameras),
            target_fps=self._target_fps,
            pool_mb=round(self._pool.total_bytes / 1024**2, 1),
            slots=self._pool.slot_count,
        )
        metrics.worker_up.labels(component="ingest", worker_id=self.worker_id).set(1)

        for camera in self.cameras:
            task = CameraTask(
                camera,
                self._pool,
                self._allocator,
                self._stream,
                target_fps=self._target_fps,
            )
            thread = threading.Thread(target=task.run, name=f"cam:{camera}", daemon=True)
            self._tasks.append(task)
            self._threads.append(thread)
            thread.start()

    def stop(self) -> None:
        _shutdown.set()
        for thread in self._threads:
            thread.join(timeout=5.0)
        metrics.worker_up.labels(component="ingest", worker_id=self.worker_id).set(0)
        self._pool.close()
        self._client.close()
        log.info("ingest_worker_durdu", worker=self.worker_id)

    def update_pipeline_metrics(self) -> None:
        metrics.shm_slots_free.set(self._allocator.available)
        metrics.queue_depth.labels(queue=self._stream.name).set(self._stream.depth)

    def summary(self) -> str:
        total_recv = sum(t.stats.received for t in self._tasks)
        total_pub = sum(t.stats.published for t in self._tasks)
        total_gate = sum(t.stats.dropped_gate for t in self._tasks)
        total_slot = sum(t.stats.dropped_no_slot for t in self._tasks)
        total_fps = sum(t.stats.fps for t in self._tasks)
        alive = sum(1 for t in self._threads if t.is_alive())
        return (
            f"{alive}/{len(self._tasks)} kamera · "
            f"{total_fps:5.1f} FPS toplam · "
            f"alınan {total_recv} · yayınlanan {total_pub} · "
            f"elenen {total_gate} · slot yok {total_slot} · "
            f"boş slot {self._allocator.available}/{settings.shm_slot_count} · "
            f"kuyruk {self._stream.depth}"
        )

    def per_camera_table(self) -> str:
        lines = [f"{'KAMERA':<16} {'FPS':>6} {'ALINAN':>8} {'YAYIN':>8} {'ELENEN':>8} {'GEÇEN%':>7}"]
        lines.append("-" * len(lines[0]))
        for task in sorted(self._tasks, key=lambda t: t.camera):
            s = task.stats
            lines.append(
                f"{s.camera:<16} {s.fps:>6.2f} {s.received:>8} {s.published:>8} "
                f"{s.dropped_gate:>8} {s.pass_ratio * 100:>6.1f}%"
            )
        return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────


def _resolve_cameras(args: argparse.Namespace) -> list[str]:
    if args.all:
        return [f"cam-{i:02d}" for i in range(1, settings.camera_count + 1)]
    if args.cameras:
        return list(args.cameras)
    return ["cam-test-motion"]


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTINEL alım worker'ı")
    parser.add_argument("--cameras", nargs="*", help="Okunacak kameralar")
    parser.add_argument("--all", action="store_true", help=f"cam-01..cam-{settings.camera_count}")
    parser.add_argument("--worker-id", default="ingest-0")
    parser.add_argument("--owner", action="store_true", help="Paylaşımlı bellek havuzunu bu worker oluştursun")
    parser.add_argument("--fps", type=float, default=None, help="Hedef örnekleme FPS'i")
    parser.add_argument("--metrics-port", type=int, default=9101)
    parser.add_argument("--duration", type=float, default=None, help="N saniye sonra dur (test)")
    parser.add_argument("--stats-interval", type=float, default=5.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    cameras = _resolve_cameras(args)
    metrics.serve_metrics(args.metrics_port)
    log.info("metrik_sunucusu", port=args.metrics_port)

    worker = IngestWorker(
        cameras,
        worker_id=args.worker_id,
        own_pool=args.owner,
        target_fps=args.fps,
    )
    worker.start()

    deadline = time.monotonic() + args.duration if args.duration else None
    try:
        while not _shutdown.is_set():
            _shutdown.wait(args.stats_interval)
            worker.update_pipeline_metrics()
            print(f"  {worker.summary()}", flush=True)
            if deadline and time.monotonic() >= deadline:
                break
    finally:
        print()
        print(worker.per_camera_table())
        print()
        print(f"  {worker.summary()}")
        worker.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
