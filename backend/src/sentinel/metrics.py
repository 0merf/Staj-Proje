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

# ⚠⚠ 09.09.2026 — ESKİ ADI `decode_duration`'DI VE YANLIŞ ŞEYİ ÖLÇÜYORDU
#
# Eski kod (`ingest/worker.py`):
#
#     last = time.perf_counter()          # önceki karenin İŞİ BİTTİĞİNDE
#     for frame in decoder.frames():
#         now = time.perf_counter()       # yeni kare GELDİĞİNDE
#         decode_duration.observe(now - last)
#
# Aradaki süre çözme işi değil, **bir sonraki karenin gelmesini
# bekleme** süresiydi — ve o bekleme hedef FPS'in belirlediği kare
# aralığıyla (2.75 FPS'te ~360 ms) tanımlıydı. Yani metrik, adının
# söylediği şeyi değil, kendi ayarımızı ölçüyordu. Kovaların tavanı
# 0.25 sn olduğu için de neredeyse her gözlem `+Inf`'e düşüyordu.
#
# ⭐ Aralığın kendisi işe yarar bir sayı — sadece adı yanlıştı. Dürüst
# adıyla bırakıldı.
frame_interval = Histogram(
    "sentinel_frame_interval_seconds",
    "Kareler arası duvar saati aralığı — BEKLEME dâhil, iş DEĞİL "
    "(örnekleme temposunu gösterir)",
    ["cam"],
    buckets=(0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0, 2.0),
)

# ⭐⭐ ASIL İŞİ ÖLÇEN METRİKLER — duvar saati DEĞİL, CPU ZAMANI (P-58/P-60)
#
# Neden duvar saati olmaz: `container.decode()` ağdan veri beklerken
# BLOKE oluyor. Onu `perf_counter` ile ölçmek, hatayı bir kat aşağıda
# tekrarlamak olurdu — yine beklemeyi ölçerdik.
#
# `time.thread_time()` yalnızca O İŞ PARÇACIĞININ harcadığı CPU'yu
# sayar; bloke geçen süre sayılmaz. Kamera başına bir iş parçacığı
# olduğu için tam da istediğimiz şey.
#
# ⚠ NEDEN HISTOGRAM DEĞİL COUNTER: Windows'ta `GetThreadTimes`
# çözünürlüğü ~15.6 ms. Kare başına ~2 ms'lik bir işi tek tek ölçmek
# çoğunlukla 0 verirdi. Ama sayaç MONOTON birikiyor; kare sınırlarında
# okunan farkların toplamı teleskoplanıp `son − ilk` oluyor. Yani
# TOPLAM doğru, yalnızca dağılım ölçülemiyor. Kare başına maliyet
# `frames_received` ile bölünerek elde edilir.
decode_cpu_seconds = Counter(
    "sentinel_decode_cpu_seconds_total",
    "H.264 çözmede harcanan İŞ PARÇACIĞI CPU zamanı "
    "(örnekleme sonucu atılan kareler dâhil — decode bedeli yine ödenir)",
    ["cam"],
)

bgr_cpu_seconds = Counter(
    "sentinel_bgr_cpu_seconds_total",
    "BGR renk dönüşümünde harcanan İŞ PARÇACIĞI CPU zamanı "
    "(yalnızca örneklenen kareler)",
    ["cam"],
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

# ⚠ 03.09.2026 — BU İKİ METRİK TANIMLIYDI AMA HİÇ DOLDURULMUYORDU
# `gpu_memory_used` Gün 1'den beri tanımlıydı ve hiçbir yerde `.set()`
# çağrılmıyordu; yani Prometheus'ta sürekli 0 duruyordu. Sonucu K4
# ölçümünde ortaya çıktı: dayanıklılık koşusu "VRAM: None" yazdı.
#
# Etkisi gözlemden büyük: PLAN §13.2 dört Grafana panosu tanımlıyor ve
# bunlardan **GPU panosu** tam olarak bu iki metriğe dayanıyordu.
# Metrik olmayınca pano da kurulamadı — ve panonun yokluğu, metriğin
# eksikliğinden daha görünürdü. Yani eksik, görünür bir belirti
# üretmediği için 17 gün fark edilmedi.
gpu_memory_used = Gauge(
    "sentinel_gpu_memory_used_bytes",
    "Ayrılmış VRAM (PyTorch ayırıcısının rezerve ettiği)",
)

gpu_utilization = Gauge(
    "sentinel_gpu_utilization",
    "GPU çekirdek kullanımı (0-100). ⚠ P-33: DÜŞÜK OLMASI 'ucuz' DEMEK "
    "DEĞİL — bu sayı görev döngüsünü ölçer, çağrı maliyetini değil",
)

# ─── Analitik katmanı ─────────────────────────────────────────

# Tespit edilen anomaliler. `type` ve `severity` etiketleri PLAN §8.1'deki
# `events` tablosuyla AYNI değerleri kullanıyor — metrik ile veritabanı
# ayrışırsa Grafana'daki sayı ile rapordaki sayı tutmaz.
anomalies_total = Counter(
    "sentinel_anomalies_total",
    "Kural tabanlı anomali tespitleri (KATMAN B)",
    ["cam", "type", "severity"],
)

# Füzyon katmanının ürettiği anlık risk skoru — kamera başına AZAMİ.
# ⚠ PLAN §13.1'de tanımlıydı, 03.09.2026'ya kadar kodda yoktu.
# Eksikliği görünmezdi çünkü alarmlar zaten sayılıyordu; ama alarm
# EŞİĞİ GEÇEN riski gösterir, bu gauge eşiğin ALTINDAKİNİ de gösterir.
# Fark operasyonel: "sistem sessiz" ile "sistem sessiz ama risk
# tırmanıyor" arasındaki ayrım tam olarak erken uyarının konusu (K8).
# ⭐ Öğrenilmiş saldırganlık modelinin kamera başına çıktısı (P-56).
# ⚠ `risk_score`dan AYRI: o füzyon sonrası birleşik risk, bu ham model
# olasılığı. İkisini tek gauge'da toplamak, modelin mi füzyonun mu
# konuştuğunu ayırt edilemez yapardı — P-40'ta panelin kare yerine
# kişi sayması tam bu tür bir karışıklıktı.
# ⚠⚠ MODELİN GERÇEK ÜRETİM MALİYETİ (P-57)
#
# Sentetik benchmark iki kez yanlış sonuç verdi:
#   1. pencereyi 814 kareye şişirdi → 24.84 ms (58× abartı)
#   2. düzeltilince 0.79 ms dedi → ama A/B ölçümü modelin 10.6
#      ÇEKİRDEK yediğini gösterdi (246× eksik tahmin)
#
# ⭐ Ders: sentetik ölçüm, üretimin girdi dağılımını taklit edemiyor.
# Bu histogram maliyeti GERÇEK veriyle, GERÇEK kamera sayısıyla ve
# GERÇEK kişi yoğunluğuyla ölçüyor.
aggression_model_duration = Histogram(
    "sentinel_aggression_model_duration_seconds",
    "Saldirganlik modeli asama suresi (besle / degerlendir)",
    ["asama"],
    buckets=(0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0),
)

aggression_model_score = Gauge(
    "sentinel_aggression_model_score",
    "Ogrenilmis saldirganlik modelinin kamera basina olasiligi (0-1)",
    ["cam"],
)

# ⭐⭐ FÜZYONUN HER SİNYALİ AYRI AYRI — "hangi sinyal karara katkı
# veriyor" sorusunun tek gözlemlenebilir cevabı (P-72).
#
# ⚠ NEDEN GEREKLİ: `risk_score` yalnızca BİRLEŞİK skoru gösteriyor.
# Bir sinyal hiç ateşlemiyorsa (P-43'te ifade tam olarak buydu,
# P-52'de kuralların %60'ı) birleşik skora bakarak anlaşılmıyor.
#
# Şartname üç yetenek istiyor (anomali · duygu · saldırganlık) ve
# üçünün de KARARA katıldığını göstermenin yolu bu gauge.
fusion_signal = Gauge(
    "sentinel_fusion_signal",
    "Füzyona giren ham sinyallerin kamera başına AZAMİ değeri "
    "— hangi sinyalin gerçekten katkı verdiğini gösterir",
    ["cam", "signal"],
)

risk_score = Gauge(
    "sentinel_risk_score",
    "Füzyon risk skoru — kameradaki azami (0-1). Eşiğin altını da gösterir",
    ["cam"],
)

# ⚠ BASTIRILAN ALARM SAYISI — K7'nin canlı kanıtı
# `analytics/worker.py` bu sayacı (`fuzyon_bastirilan`) zaten tutuyordu
# ama Prometheus'a hiç vermiyordu. Yani "tek sinyalli riski yayınlama"
# kuralının kaç alarmı önlediği yalnızca worker kapanırken loga
# düşüyordu. K7 anlatısının en güçlü sayısı dışarı çıkmıyordu.
false_alarm_suppressed = Counter(
    "sentinel_false_alarm_suppressed_total",
    "Kural gereği yayınlanmayan alarm — sebebiyle birlikte",
    ["reason"],  # tek_sinyal | dusuk_tamlik | sogumada
)

# ⚠ ÜRETİLEN ile YAZILAN alarm sayısı AYRI ölçülüyor.
# İkisi ayrışırsa veritabanı yolu tıkanmış demektir — ve bu, sistem
# dışarıdan sağlıklı görünürken sessizce olur: panel canlı alarmları
# göstermeye devam eder, yalnızca geçmiş birikmez.
# `sentinel_anomalies_total` - `sentinel_olaylar_yazildi_total` farkı
# tam olarak kaybedilen alarm geçmişidir.
olaylar_yazildi = Counter(
    "sentinel_olaylar_yazildi_total",
    "Veritabanına kalıcı yazılan olay sayısı",
)

# ⚠ Klip sayısı ciddi olay sayısından AZ olabilir ve bu normaldir:
# kayıt kapalıysa (varsayılan) hiç klip üretilmez. Sıfır klip, bozuk
# bir klip yazıcısı değil KAPALI bir kayıt anlamına gelebilir —
# ikisini ayırt etmek için `MEDIAMTX_RECORD` değerine bakılmalı.
klipler_uretildi = Counter(
    "sentinel_klipler_uretildi_total",
    "Olay klibi olarak kesilen video sayısı",
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

# ⚠⚠ 09.09.2026 — AÇIKLAMASI YANLIŞTI: BU GERİ BASINÇ GÖSTERGESİ DEĞİL
#
# Değer `XLEN`, yani akışta TUTULAN kayıt sayısı. Ama `XACK` bir kaydı
# akıştan **silmiyor** (bunu `streams.py:365` zaten yazıyordu); kayıtlar
# ancak `MAXLEN` budamasıyla düşüyor. Sonuç: akış birkaç saniye içinde
# tavana çakılıyor ve orada kalıyor — tüketici ister yetişsin ister
# yetişmesin.
#
# Ölçüldü (09.09, sağlıklı sistem, hiçbir birikme yok):
#
#     inference.results : 5001   ⬅ ayar tam 5000, yani TAVAN + 1
#     frames.ready      :   86
#
# 5001 sayısı bir birikme değil, yalnızca "akış dolu" demek. Bu metriğe
# bakıp "kuyruk şişmiş" demek yanlış olurdu.
#
# ⭐ Bilgi kodda ZATEN VARDI — `streams.py`'daki yorum XACK'in silmediğini
# açıkça yazıyor. Eksik olan, o bilginin metriğin AÇIKLAMASINA
# taşınmasıydı. Doğru bilgi yanlış yerde durunca yanlış bilgiyle aynı
# sonucu veriyor.
queue_depth = Gauge(
    "sentinel_queue_depth",
    "Akışta TUTULAN kayıt sayısı (XLEN). ⚠ Geri basınç göstergesi DEĞİL: "
    "XACK kaydı silmez, akış MAXLEN tavanına çakılır. Birikme için "
    "`sentinel_consumer_lag` kullanın",
    ["queue"],
)

# ⭐ ASIL GERİ BASINÇ GÖSTERGESİ — tüketici grubunun GECİKMESİ
#
# `XINFO GROUPS` her grup için `lag` veriyor: akışa yazılmış ama o
# gruba HENÜZ TESLİM EDİLMEMİŞ kayıt sayısı. `XLEN`'in aksine tüketici
# yetiştikçe sıfıra iniyor, geri kaldıkça büyüyor — yani gerçekten
# birikmeyi ölçüyor.
#
# ⚠ Neden gerekti: bir ölçümde alım 2.77 FPS yayınlarken çıkarım 1.42
# FPS analiz ediyordu ve aradaki kareler HİÇBİR metrikte görünmüyordu
# (P-60). `frames_dropped` alım tarafını sayıyor, `XLEN` tavana çakılı.
# Birikmenin görülebileceği tek yer buydu ve ölçülmüyordu.
consumer_lag = Gauge(
    "sentinel_consumer_lag",
    "Tüketici grubuna henüz teslim edilmemiş kayıt sayısı — GERÇEK birikme",
    ["queue", "group"],
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


# ─── API ve güvenlik ──────────────────────────────────────────
#
# ⚠ 03.09.2026 — PLAN §13.2'NİN "GÜVENLİK PANOSU" KURULAMIYORDU
# Dört Grafana panosundan biri güvenlik panosu: başarısız girişler,
# yetki reddi, dışa aktarma hacmi. Üçünün de metriği yoktu.
#
# Bu, gözetim sistemi için sıradan bir eksik değil: G20 hesap
# kilitleme ve G28 "başarısız giriş serisi uyarısı" ikisi de bu
# sayaca dayanıyor. Kilitleme kodda VARDI (`routers/oturum.py`), ama
# kilidin kaç kez devreye girdiğini kimse göremiyordu. Çalışan ama
# gözlemlenemeyen bir savunma, ilk sessiz arızasına kadar çalışır.

http_requests = Counter(
    "sentinel_http_requests_total",
    "HTTP istekleri — yöntem, yol şablonu ve durum koduna göre",
    ["method", "path", "status"],
)

ws_connections_active = Gauge(
    "sentinel_ws_connections_active",
    "Açık WebSocket bağlantısı sayısı",
)

auth_failures = Counter(
    "sentinel_auth_failures_total",
    "Kimlik/yetki reddi — sebebiyle. G20 ve G28'in gözlem tabanı",
    ["reason"],  # kimlik_hatali | kilitli | token_gecersiz | yetkisiz | ws_kimliksiz
)


def serve_metrics(port: int) -> None:
    """Prometheus'un kazıyacağı /metrics uç noktasını açar."""
    start_http_server(port)


__all__ = [
    "anomalies_total",
    "auth_failures",
    "batch_size",
    "bgr_cpu_seconds",
    "camera_fps",
    "camera_target_fps",
    "camera_up",
    "decode_cpu_seconds",
    "detections_found",
    "end_to_end_latency",
    "expressions_classified",
    "false_alarm_suppressed",
    "frame_interval",
    "frames_dropped",
    "frames_published",
    "frames_received",
    "fusion_signal",
    "gate_decisions",
    "gate_duration",
    "gpu_memory_used",
    "gpu_utilization",
    "http_requests",
    "inference_duration",
    "klipler_uretildi",
    "motion_gate_ratio",
    "olaylar_yazildi",
    "pipeline_capacity",
    "pose_crops",
    "queue_depth",
    "risk_score",
    "serve_metrics",
    "shm_slots_free",
    "short_tracks",
    "track_lifetime",
    "tracks_started",
    "worker_up",
    "ws_connections_active",
]
