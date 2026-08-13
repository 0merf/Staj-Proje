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
    "camera_fps",
    "camera_up",
    "decode_duration",
    "frames_dropped",
    "frames_published",
    "frames_received",
    "gate_duration",
    "motion_gate_ratio",
    "queue_depth",
    "serve_metrics",
    "shm_slots_free",
    "worker_up",
]
