"""Prometheus metrikleri.

Tanım listesi PLAN.md §13.1'dedir. Buradaki her metriğin bir amacı var;
"her ihtimale karşı" metrik toplamıyoruz — her biri bir soruyu cevaplıyor.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ─── Alım katmanı ─────────────────────────────────────────────

camera_up = Gauge(
    "sentinel_camera_up",
    "Kamera akışı okunabiliyor mu (1/0)",
    ["cam"],
)

frames_received = Counter(
    "sentinel_frames_received_total",
    "Akıştan çözülüp örneklenen kare sayısı",
    ["cam"],
)

frames_published = Counter(
    "sentinel_frames_published_total",
    "Kademe 0'ı geçip çıkarım kuyruğuna yazılan kare sayısı",
    ["cam"],
)

frames_dropped = Counter(
    "sentinel_frames_dropped_total",
    "Atılan kare sayısı — sebebiyle birlikte",
    ["cam", "reason"],  # gate_idle | no_slot | publish_error
)

motion_gate_ratio = Gauge(
    "sentinel_motion_gate_pass_ratio",
    "Kademe 0'ı geçen karelerin oranı (kayan pencere)",
    ["cam"],
)

decode_duration = Histogram(
    "sentinel_decode_duration_seconds",
    "Kare başına çözme + BGR dönüşüm süresi",
    ["cam"],
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25),
)

gate_duration = Histogram(
    "sentinel_gate_duration_seconds",
    "Kademe 0 hareket filtresi süresi",
    ["cam"],
    buckets=(0.0005, 0.001, 0.002, 0.005, 0.01, 0.025),
)

camera_fps = Gauge(
    "sentinel_camera_fps",
    "Kamera başına gerçekleşen örnekleme hızı",
    ["cam"],
)

# ─── Çıkarım katmanı ──────────────────────────────────────────

inference_duration = Histogram(
    "sentinel_inference_duration_seconds",
    "Kare başına model çıkarım süresi (batch içinde amortize)",
    ["stage"],  # detect | pose | emotion | action
    buckets=(0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

batch_size = Histogram(
    "sentinel_batch_size",
    "GPU'ya verilen batch boyutu — büyük batch daha verimli",
    buckets=(1, 2, 4, 6, 8, 12, 16, 24, 32),
)

detections_found = Counter(
    "sentinel_detections_total",
    "Tespit edilen kişi sayısı",
    ["cam"],
)

end_to_end_latency = Histogram(
    "sentinel_end_to_end_latency_seconds",
    "Kare yakalanmasından sonucun yazılmasına kadar geçen süre (K3 kriteri)",
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
)

gpu_memory_used = Gauge(
    "sentinel_gpu_memory_used_bytes",
    "Kullanılan VRAM",
)

# ─── Boru hattı sağlığı ───────────────────────────────────────

queue_depth = Gauge(
    "sentinel_queue_depth",
    "Kuyruktaki mesaj sayısı — geri basınç göstergesi",
    ["queue"],
)

shm_slots_free = Gauge(
    "sentinel_shm_slots_free",
    "Paylaşımlı bellek havuzundaki boş slot sayısı",
)

worker_up = Gauge(
    "sentinel_worker_up",
    "Worker çalışıyor mu (1/0)",
    ["component", "worker_id"],
)


def serve_metrics(port: int) -> None:
    """Prometheus'un kazıyacağı /metrics uç noktasını açar."""
    start_http_server(port)


__all__ = [
    "batch_size",
    "camera_fps",
    "camera_up",
    "decode_duration",
    "detections_found",
    "end_to_end_latency",
    "frames_dropped",
    "frames_published",
    "frames_received",
    "gate_duration",
    "gpu_memory_used",
    "inference_duration",
    "motion_gate_ratio",
    "queue_depth",
    "serve_metrics",
    "shm_slots_free",
    "worker_up",
]
