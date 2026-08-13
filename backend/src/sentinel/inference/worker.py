"""GPU çıkarım worker'ı — KADEME 1.

Mimarideki yeri
---------------
Alım worker'larının paylaşımlı belleğe yazdığı kareleri okur, **kameralar
arası toplu (batch)** olarak modele verir, sonuçları JSON olarak
`inference.results` akışına yazar ve slotu havuza geri verir.

⚠ TEK KOPYA KURALI
------------------
Sistemde **yalnızca bir** çıkarım süreci çalışır. Sebep VRAM: her süreç
model ağırlıklarının kendi kopyasını yükler. 4 süreç × ~4.6 GB = 18 GB,
elimizde 8 GB var (PLAN.md §2.2). Ayrıca tek süreç, 20 kameradan gelen
kareleri tek batch'te işleyerek GPU verimini kat kat artırır.

Toplu işlemenin önemi
---------------------
GPU'da her çekirdek başlatmanın sabit bir maliyeti vardır. 8 kareyi tek
seferde vermek, 8 kez tek kare vermekten çok daha ucuzdur. Batch,
Valkey tüketici grubundan doğal olarak gelir: `XREADGROUP COUNT=N`.

Kullanım
--------
    uv run python -m sentinel.inference.worker
    uv run python -m sentinel.inference.worker --batch-size 8 --duration 60
    uv run python -m sentinel.inference.worker --model models/yolo26s-pose.pt
"""

from __future__ import annotations

import argparse
import json
import signal
import statistics
import sys
import time
from collections import Counter, deque
from types import FrameType

from sentinel import metrics
from sentinel.bus.shm import DEFAULT_SLOT_BYTES, FramePool, FramePoolError
from sentinel.bus.streams import FrameStream, ResultStream, SlotAllocator, connect
from sentinel.config import settings
from sentinel.inference.detector.base import Detection, Detector
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

GROUP = "inference"
_stop = False


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True
    log.info("kapatma_sinyali_alindi")


def build_detector(
    model_path: str,
    *,
    backend: str,
    device: str,
    half: bool,
    imgsz: int,
    conf: float,
) -> Detector:
    """Konfigürasyona göre dedektör örneği üretir.

    Yeni bir arka uç eklemek (RTMDet, RT-DETR) yalnızca buraya bir dal
    eklemek demektir; çağıran kod `Detector` protokolüne bağlıdır.
    """
    if backend in {"yolo26", "yolo11", "yolo"}:
        from sentinel.inference.detector.yolo import UltralyticsDetector

        return UltralyticsDetector(
            model_path,
            backend_name=backend,
            device=device,
            half=half,
            imgsz=imgsz,
            conf_threshold=conf,
        )
    raise ValueError(f"Bilinmeyen dedektör arka ucu: {backend}")


def _serialize(detections: list[Detection], *, motion: float, gate: str) -> str:
    return json.dumps(
        {
            "motion": round(motion, 5),
            "gate": gate,
            "count": len(detections),
            "detections": [d.to_dict() for d in detections],
        },
        separators=(",", ":"),
    )


class InferenceWorker:
    """Kare akışını tüketip tespit sonucu üreten worker."""

    def __init__(
        self,
        detector: Detector,
        *,
        worker_id: str = "inference-0",
        batch_size: int = 8,
        block_ms: int = 500,
    ) -> None:
        self._detector = detector
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._block_ms = block_ms

        self._client = connect()
        self._frames = FrameStream(self._client)
        self._results = ResultStream(self._client)
        self._allocator = SlotAllocator(self._client, settings.shm_slot_count)
        self._frames.ensure_group(GROUP)

        try:
            self._pool = FramePool(
                slot_count=settings.shm_slot_count, slot_bytes=DEFAULT_SLOT_BYTES
            )
        except FramePoolError as exc:
            raise SystemExit(f"HATA: {exc}") from exc

        # İstatistik
        self.processed = 0
        self.detections_total = 0
        self.batches = 0
        self.by_camera: Counter[str] = Counter()
        self.batch_sizes: deque[int] = deque(maxlen=200)
        self.infer_ms: deque[float] = deque(maxlen=500)
        self.e2e_ms: deque[float] = deque(maxlen=500)

    def warmup(self) -> None:
        self._detector.warmup(self._batch_size)

    def run(self, *, duration: float | None = None, stats_interval: float = 5.0) -> None:
        info = self._detector.info
        log.info(
            "cikarim_worker_basliyor",
            worker=self._worker_id,
            backend=info.backend,
            device=info.device,
            precision=info.precision,
            pose=info.has_pose,
            batch_size=self._batch_size,
        )
        metrics.worker_up.labels(component="inference", worker_id=self._worker_id).set(1)

        started = time.monotonic()
        last_report = started
        deadline = started + duration if duration else None

        while not _stop:
            batch = list(
                self._frames.consume(
                    GROUP, self._worker_id, count=self._batch_size, block_ms=self._block_ms
                )
            )
            if batch:
                self._run_batch(batch)

            now = time.monotonic()
            if now - last_report >= stats_interval:
                self._report(now - started)
                last_report = now
            if deadline and now >= deadline:
                break

        self._finish(time.monotonic() - started)

    # ─── İç işler ────────────────────────────────────────────

    def _run_batch(self, batch: list) -> None:  # type: ignore[type-arg]
        # Kareleri paylaşımlı bellekten oku — kopyalama yok
        images = [self._pool.read(message.ref) for message in batch]

        t0 = time.perf_counter()
        try:
            results = self._detector.detect(images)
        except Exception as exc:
            log.error("cikarim_hatasi", error=f"{type(exc).__name__}: {exc}", batch=len(batch))
            self._release(batch)
            return
        infer_s = time.perf_counter() - t0

        self.batches += 1
        self.batch_sizes.append(len(batch))
        per_frame_ms = infer_s / len(batch) * 1000.0
        self.infer_ms.append(per_frame_ms)
        metrics.inference_duration.labels(stage="detect").observe(infer_s / len(batch))
        metrics.batch_size.observe(len(batch))

        now_monotonic = time.monotonic()
        for message, detections in zip(batch, results, strict=True):
            payload = _serialize(
                detections, motion=message.motion_ratio, gate=message.gate_reason
            )
            self._results.publish(
                message.camera,
                payload,
                sequence=message.sequence,
                captured_at=message.captured_at,
            )
            self.processed += 1
            self.detections_total += len(detections)
            self.by_camera[message.camera] += 1
            metrics.detections_found.labels(cam=message.camera).inc(len(detections))
            # Uçtan uca gecikme: kare yakalandığından sonuç yazılana kadar
            latency = now_monotonic - message.captured_at
            self.e2e_ms.append(latency * 1000.0)
            metrics.end_to_end_latency.observe(latency)

        self._release(batch)

    def _release(self, batch: list) -> None:  # type: ignore[type-arg]
        """Slotları havuza geri ver ve mesajları onayla.

        Bu ikisi ATLANIRSA sistem kilitlenir: üretici boş slot bulamaz.
        Hata yolunda bile çağrılmalı (P-10).
        """
        self._allocator.release_many([m.ref.slot for m in batch])
        self._frames.ack(GROUP, *[m.message_id for m in batch])

    def _report(self, elapsed: float) -> None:
        metrics.shm_slots_free.set(self._allocator.available)
        metrics.queue_depth.labels(queue=self._frames.name).set(self._frames.depth)
        metrics.queue_depth.labels(queue=self._results.name).set(self._results.depth)
        print(f"  {self.summary(elapsed)}", flush=True)

    def summary(self, elapsed: float) -> str:
        fps = self.processed / elapsed if elapsed > 0 else 0
        avg_ms = statistics.fmean(self.infer_ms) if self.infer_ms else 0
        avg_batch = statistics.fmean(self.batch_sizes) if self.batch_sizes else 0
        avg_e2e = statistics.fmean(self.e2e_ms) if self.e2e_ms else 0
        return (
            f"{self.processed:>6} kare · {fps:5.1f} FPS · "
            f"{avg_ms:5.1f} ms/kare · batch {avg_batch:4.1f} · "
            f"{self.detections_total:>5} tespit · "
            f"gecikme {avg_e2e:5.0f} ms · "
            f"boş slot {self._allocator.available}/{settings.shm_slot_count}"
        )

    def _finish(self, elapsed: float) -> None:
        info = self._detector.info
        print()
        print(f"{'KAMERA':<16} {'KARE':>7} {'TESPİT':>8} {'FPS':>7}")
        print("-" * 42)
        for camera, count in sorted(self.by_camera.items()):
            print(f"{camera:<16} {count:>7} {'':>8} {count / elapsed:>7.2f}")
        print()
        print(f"  {self.summary(elapsed)}")
        if self.infer_ms:
            ordered = sorted(self.infer_ms)
            print(
                f"  Çıkarım ms/kare — ortalama {statistics.fmean(ordered):.2f} · "
                f"p50 {ordered[len(ordered) // 2]:.2f} · "
                f"p95 {ordered[int(len(ordered) * 0.95) - 1]:.2f}"
            )
        print(f"  Model: {info.backend} · {info.precision} · {info.device} · poz={info.has_pose}")

        metrics.worker_up.labels(component="inference", worker_id=self._worker_id).set(0)
        self._detector.close()
        self._pool.close()
        self._client.close()


# ─── CLI ──────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTINEL GPU çıkarım worker'ı")
    parser.add_argument("--model", default=None, help="Ağırlık dosyası")
    parser.add_argument("--backend", default=None, help="yolo26 | yolo11")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--no-half", action="store_true", help="FP16 yerine FP32")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--worker-id", default="inference-0")
    parser.add_argument("--metrics-port", type=int, default=9110)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--stats-interval", type=float, default=5.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    metrics.serve_metrics(args.metrics_port)

    detector = build_detector(
        args.model or str(settings.detector_weights),
        backend=args.backend or settings.detector_backend,
        device=args.device,
        half=not args.no_half,
        imgsz=args.imgsz,
        conf=args.conf if args.conf is not None else settings.detector_conf_threshold,
    )

    worker = InferenceWorker(
        detector,
        worker_id=args.worker_id,
        batch_size=args.batch_size,
    )
    worker.warmup()
    worker.run(duration=args.duration, stats_interval=args.stats_interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
