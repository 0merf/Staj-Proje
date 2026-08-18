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

gate_decisions = Counter(
    "sentinel_gate_decisions_total",
    "Kademe 0 kararlarının dağılımı — hareket mi, periyodik yoklama mı, boşta mı",
    ["cam", "reason"],  # motion | refresh | idle | warmup
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

camera_target_fps = Gauge(
    "sentinel_camera_target_fps",
    "Kamera başına HEDEFLENEN örnekleme hızı — uyarlanabilir FPS bunu değiştirir",
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

expressions_classified = Counter(
    "sentinel_expressions_total",
    "KADEME 2b — sınıflandırılan yüz ifadesi (kullanılabilir olup olmadığıyla)",
    ["cam", "label", "usable"],
)

pose_crops = Counter(
    "sentinel_pose_crops_total",
    "KADEME 2a'ya giren kişi kırpıntısı — iskelet çıktı mı",
    ["result"],  # skeleton | empty
)

# Bir kişinin kimliğinin kaç kez değiştiğinin göstergesi (PLAN.md §6.1).
# Zamansal analizin tamamı ("bu kişi 3 saniyedir hızlanıyor") kimliğin
# kararlı kalmasına dayanır; kimlik sık değişiyorsa saldırganlık ve
# anomali modüllerinin girdisi bozulur.
#
# Ölçüm yöntemi: doğrudan "ID switch" sayılamaz — bunun için gerçek
# referans (ground truth) gerekir. Onun yerine PROXY sayıyoruz: kısa
# ömürlü izler. Bir iz birkaç kare sonra kaybolup yerine yeni kimlikli
# bir iz geliyorsa, bu büyük olasılıkla aynı kişidir.
#
# ⚠ METRİK ADI BİLEREK "switches" DEĞİL
# Önceki adı `sentinel_track_switches_total` idi ve yanlıştı: sayılan
# şey ID switch değil, KISA ÖMÜRLÜ İZ. İkisi aynı şey değil — her kısa
# iz bir switch olmayabilir (gerçek yanlış pozitif olabilir), her switch
# de kısa iz üretmeyebilir (iki uzun iz kimlik takas edebilir).
# Grafana panelinde ve raporda ad ne diyorsa o okunacağı için, adın
# ölçtüğü şeyi söylemesi gerekiyor. Gerçek ID switch / IDF1 / HOTA
# ölçümü MOT17 + TrackEval ister; o Gün 23'ün işi (PLAN.md §14.2).
short_tracks = Counter(
    "sentinel_short_tracks_total",
    "Kimlik kararsızlığı VEKİL göstergesi: kısa ömürlü (terk edilmiş) iz sayısı. "
    "Gerçek ID switch DEĞİLDİR — bkz. PLAN.md §14.2",
    ["cam"],
)

tracks_started = Counter(
    "sentinel_tracks_started_total",
    "Yeni oluşturulan iz sayısı — kararsızlık oranının paydası",
    ["cam"],
)

track_lifetime = Histogram(
    "sentinel_track_lifetime_frames",
    "Bir izin kaç kare boyunca yaşadığı — uzun ömür = kararlı kimlik",
    buckets=(1, 2, 3, 5, 8, 13, 21, 34, 55, 89),
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

# Çıkarım worker'ının ÖLÇÜLEN tüketim hızı (kare/sn).
# Alım katmanı üretimini buna göre kısıyor: atılan kare için decode +
# BGR + letterbox CPU'su zaten ödenmiş oluyor ve o CPU çıkarımdan
# çalınıyor (bkz. bus/streams.py · CAPACITY_KEY).
pipeline_capacity = Gauge(
    "sentinel_pipeline_capacity_fps",
    "Çıkarım worker'ının ölçülen tüketim hızı — üretici bunu hedefler",
)

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
    "camera_target_fps",
    "camera_up",
    "decode_duration",
    "detections_found",
    "end_to_end_latency",
    "expressions_classified",
    "frames_dropped",
    "frames_published",
    "frames_received",
    "gate_decisions",
    "gate_duration",
    "gpu_memory_used",
    "inference_duration",
    "motion_gate_ratio",
    "pipeline_capacity",
    "pose_crops",
    "queue_depth",
    "serve_metrics",
    "shm_slots_free",
    "short_tracks",
    "track_lifetime",
    "tracks_started",
    "worker_up",
]
