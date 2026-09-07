"""Uygulama konfigürasyonu.

Tüm ayarlar proje kökündeki .env dosyasından okunur ve Pydantic ile
doğrulanır. Eksik/yanlış tipte bir ayar varsa uygulama AÇILIŞTA hata
verir — çalışma anında sürpriz olmaz.

⚠ Sırlar asla koda gömülmez (PLAN.md §11.1 / G15).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/sentinel/config.py -> ../../..
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """SENTINEL çalışma zamanı ayarları."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # .env'de tanımlanmamış anahtarlar varsa patlama
        case_sensitive=False,
    )

    # ─── Genel ────────────────────────────────────────────────
    sentinel_env: Literal["development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    tz: str = "Europe/Istanbul"

    api_host: str = "127.0.0.1"
    api_port: int = 8001

    # ─── PostgreSQL ───────────────────────────────────────────
    # ⚠ Servis adresleri "localhost" DEĞİL "127.0.0.1" olmalı.
    #   Docker portları yalnızca IPv4'e bağlı; Windows'ta "localhost"
    #   önce ::1 (IPv6) dener ve ~2 sn gecikme yaşatır.
    #   Bkz. docs/report/problems.md · P-03
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433
    postgres_user: str = "sentinel"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "sentinel"
    database_url: str = ""

    # ─── Valkey ───────────────────────────────────────────────
    valkey_host: str = "127.0.0.1"
    valkey_port: int = 6379
    valkey_password: SecretStr = SecretStr("")
    valkey_url: str = ""

    stream_frames: str = "frames.ready"
    stream_results: str = "inference.results"
    stream_frames_maxlen: int = 200
    stream_results_maxlen: int = 5000

    # ─── MediaMTX ─────────────────────────────────────────────
    mediamtx_host: str = "127.0.0.1"
    # ⚠ AYNI SERVİS, İKİ FARKLI İZLEYİCİ — konteynerleştirmede ortaya çıktı
    #
    # `mediamtx_host` SUNUCUNUN gördüğü adres: RTSP okuma ve yönetim
    # API'si buradan geçiyor. Docker içinde bu `mediamtx` (servis adı).
    #
    # `mediamtx_public_host` ise TARAYICININ gördüğü adres: WHEP video
    # akışını tarayıcı doğrudan çekiyor (mimari kural 2 — video sunucu
    # üzerinden geçmiyor). Tarayıcı Docker ağının dışında olduğu için
    # `mediamtx` adını çözemez; onun için `127.0.0.1` gerekiyor.
    #
    # Tek bir ayarla ikisini birden karşılamak imkânsız ve bu ayrım
    # konteynerleştirmeden önce görünmüyordu: her şey aynı makinede
    # koşarken iki adres de `127.0.0.1` idi.
    #
    # Boş bırakılırsa `mediamtx_host` kullanılıyor (yerel geliştirme).
    mediamtx_public_host: str = ""
    mediamtx_rtsp_port: int = 8554
    mediamtx_webrtc_port: int = 8889
    mediamtx_api_port: int = 9997

    # ─── Gözlemlenebilirlik ───────────────────────────────────
    prometheus_port: int = 9090
    grafana_port: int = 3000
    metrics_enabled: bool = True

    # ─── Güvenlik ─────────────────────────────────────────────
    jwt_secret_key: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    allowed_origins: str = "http://localhost:5173"
    rate_limit_login_per_minute: int = 5
    max_ws_connections_per_user: int = 4

    # ─── Boru hattı ───────────────────────────────────────────
    camera_count: int = 20
    target_fps: int = 4
    # ⚠ HENÜZ KULLANILMIYOR — risk skoru üretilmeye başlayınca (Gün 15,
    #   analytics katmanı) `_adapt_rate` içine girecek. PLAN §5.2.
    target_fps_high_risk: int = 8
    target_fps_idle: int = 1
    # ⚠ ÖLÜ AYAR — mimari değişti, silinmedi ki sapma görünür kalsın.
    #   PLAN §4.1 "4 × Ingest Worker (her biri ~5 kamera)" diyordu.
    #   Gerçekleşen: TEK süreç + kamera başına bir thread. Gerekçe
    #   ingest/worker.py modül başlığında (PyAV/OpenCV GIL'i bırakıyor,
    #   FramePool tek nesne olarak paylaşılabiliyor).
    #   Bedeli: PLAN §4.2'nin "bir worker düşer, diğerleri etkilenmez"
    #   faydası kayboldu; yerine kamera başına try/except + yeniden
    #   bağlanma döngüsü kondu.
    ingest_worker_count: int = 4
    # ⚠ HENÜZ KULLANILMIYOR — klip kaynağı olarak RAM halka tamponu
    #   yerine MediaMTX sürekli kaydı seçildi (YOL-HARITASI.md §2).
    #   Ayar, kayıt segmentlerinden kesilecek olay ÖNCESİ süreyi
    #   tanımlamak için Gün 19'da klip yazıcıda kullanılacak.
    ring_buffer_seconds: int = 30
    shm_slot_count: int = 128

    # Uyarlanabilir FPS (PLAN §5.2): hareketsiz kamerayı 4 FPS
    # örneklemek boşa iş — kareler Kademe 0'da eleniyor ama renk
    # dönüşümü maliyeti ödenmiş oluyor. O CPU kalabalık kameralara.
    adaptive_fps_enabled: bool = True
    adaptive_idle_after_s: float = 30.0

    # ⚠ KAPASİTE GÜDÜMLÜ GERİ BASINÇ — VARSAYILAN KAPALI
    #
    # Fikir doğruydu, UYGULAMASI HATALIYDI ve sistemi bozdu.
    #
    # Amaç: alım 80 kare/sn üretirken çıkarım ~10 tüketiyordu ve
    # karelerin çoğu atılıyordu; atılan kare için decode + BGR +
    # letterbox CPU'su zaten ödenmiş oluyordu. Üretimi tüketime
    # bağlamak istedik.
    #
    # HATA: kod "kaç kare İŞLİYORUM"u kapasite sandı. Oysa işlenen kare
    # sayısı, üretilen kare sayısının bir FONKSİYONU. Üretimi kısınca
    # işlenen kare azaldı → kapasite düşük ölçüldü → daha çok kıstı →
    # aşağı doğru sarmal. Sistem kamera başına 1 FPS tabanına çakıldı
    # (sabah 4 FPS'te çalışıyordu) ve panelde kutular 4 kat seyrek
    # güncellenmeye başladı: "kutu yok" şikâyetinin sebebi bu.
    #
    # Ölçülen bedel: örnekleme 4.0 → 1.0 FPS/kamera, buna karşılık
    # tüketim yalnızca ~10 → 8.9 FPS. Yani kısıtlama hiçbir şey
    # kazandırmadı, sadece her kamerayı körleştirdi.
    #
    # DOĞRU TASARIM (yapılmadı): çıktıyı değil DOYGUNLUĞU ölçmek.
    # Tıkanma kontrolünün (TCP gibi) mantığı: kuyruk boşalıyorken hızı
    # ARTIR, kuyruk birikiyorken AZALT. "Şu an kaç kare işledim" bir
    # kapasite ölçüsü değil; kuyruk derinliğinin YÖNÜ ise doğrudan
    # doygunluk sinyali.
    #
    # Kod duruyor ve açılabiliyor — ama yeniden tasarlanmadan
    # açılmamalı.
    capacity_backpressure_enabled: bool = False

    # OPERATÖRÜN İZLEDİĞİ KAMERAYA ÖNCELİK (PLAN.md §5.2)
    # Panelde 7 kutucuk açıkken 20 kamerayı eşit hızda analiz etmek,
    # bütçenin dörtte üçünü kimsenin bakmadığı yere harcamaktı.
    # Açık kameralar daha sık analiz edilir; kapalılar taban hızda
    # kalıp alarm üretmeye devam eder.
    target_fps_watched: int = 10
    # ⚠ Toplam bütçe olmadan bu ayar tehlikeli: 20 kutucuk birden
    # açılırsa üretim tüketimi ikiye katlar, kuyruk dolar, gecikme
    # geri gelir (P-16 / P-25 ile aynı tuzak). İzlenen kameralar bu
    # toplamı paylaşır.
    watched_fps_budget: float = 40.0

    # Çıkarım worker'ı bu yaştan eski kareleri İŞLEMEDEN atar.
    # Gecikmeyi sınırlayan tek mekanizma budur: kuyrukta bekleyen kare
    # eskir ve değersizleşir, ama işlenmeye devam ederse TAZE kareyi de
    # geciktirir. Ölçüm: bu kapalıyken gecikme 1212 ms'e çıkıyordu.
    max_frame_age_ms: int = 400

    motion_gate_enabled: bool = True
    motion_threshold: float = 0.005
    motion_refresh_interval_s: int = 5

    # ─── Modeller ─────────────────────────────────────────────
    detector_backend: str = "yolo26"  # yolo26 | yolo11 | rtmdet
    detector_model_path: str = "models/yolo26s.pt"
    detector_conf_threshold: float = 0.35
    pose_model_path: str = "models/yolo26s-pose.pt"
    # KADEME 2a. Açıkken kare başına maliyet ~4.5 ms → ~10.3 ms'e çıkar
    # (20 kamerada ~%23 → ~%53 GPU). Ölçüm ve gerekçe:
    # benchmarks/pose_20260815-153539.json · inference/pose/base.py
    pose_enabled: bool = True
    pose_crop_size: int = 192
    # 64: tipik yük (8 kare × ~4.4 kişi ≈ 35 kırpıntı) tek GPU çağrısına
    # sığsın diye. 32'de ikiye bölünüyordu ve %27 pahalıya geliyordu.
    pose_crop_batch: int = 64
    pose_conf_threshold: float = 0.25
    # ⚠ VARSAYILAN KAPALI — ÖLÇÜM HİPOTEZİ ÇÜRÜTTÜ
    #
    # Hipotez şuydu: poz çıkarım bütçesinin %59'u (99.8 ms/kare) ve GPU
    # aynı anda boşta oturuyor (NVML: %0-42, GpuIdle), demek ki maliyet
    # kırpıntı hazırlığının CPU tarafında. GPU'ya taşırsak kazanırız.
    #
    # A/B ölçümü (18.08.2026, 5 kameradan karışık 40 kare, 3.6 kişi/kare):
    #     CPU yolu   2.77 ms/kare   iskelet %95.2
    #     GPU yolu   9.95 ms/kare   iskelet %97.9
    # GPU yolu 3.6 kat DAHA YAVAŞ.
    #
    # Sebep: bu uygulama kareleri poz için YENİDEN GPU'ya yüklüyor
    # (batch başına ~9.8 MB), oysa dedektör onları zaten yüklemişti.
    # Kazanılan CPU işi, tekrarlanan transferin yanında küçük kalıyor.
    # Anlamlı olması için dedektörün tensörünün poz kademesine
    # taşınması gerekir — ayrı ve daha büyük bir iş.
    #
    # ⚠ ASIL DERS AYRI: izole ölçümde poz 2.77 ms/kare, boru hattında
    # 99.8 ms/kare çıkıyor — 36 KAT fark. Yani boru hattındaki poz
    # maliyeti kırpıntı hazırlığından DEĞİL, sistem düzeyindeki CPU
    # çekişmesinden geliyor (20 alım thread'i + çıkarım süreci aynı
    # çekirdekler için yarışıyor). Yanlış yerde optimizasyon arıyorduk.
    # P-15'in aynı dersi, bu sefer ters yönde.
    #
    # Kod duruyor: iskelet isabeti GPU yolunda daha İYİ (%97.9 vs %95.2),
    # yani kare bölge örneklemesi gri dolgudan kötü değil. Dedektör
    # tensörü paylaşılabilir hale gelirse doğrudan kullanılabilir.
    pose_gpu_crop: bool = False
    # ─── KADEME 2b — yüz + ifade ──────────────────────────────
    face_detector_path: str = "models/yunet.onnx"
    emotion_model_path: str = "models/emotieff.onnx"
    # EmotiEffLib model adı (ağırlığı kendisi yönetiyor, yol değil ad ister)
    expression_model_name: str = "enet_b0_8_best_vgaf"
    expression_enabled: bool = True
    # cuda | cpu. `onnxruntime-gpu` CUDA sağlayıcısı artık yükleniyor
    # (pyproject.toml · override-dependencies notu), ama ÖLÇÜM kazancın
    # ihmal edilebilir olduğunu gösterdi: emotiefflib girdileri tek tek
    # işliyor, toplu (batch) çağrı yapmıyor. Bu yüzden GPU'nun sabit
    # maliyeti amorti edilemiyor — 8 yüz için cuda 61.4 ms, cpu 62.9 ms.
    # Gerçek kazanç ONNX oturumunu doğrudan toplu çağırmakla gelir.
    expression_device: str = "cuda"
    # Tek turda en fazla kaç yüz sınıflandırılsın — çıkarım döngüsünü
    # bloklamamak için üst sınır.
    expression_max_faces: int = 4
    # Aynı iz için iki sınıflandırma arasındaki en kısa süre (saniye).
    expression_min_interval_s: float = 2.0
    # Yüz aranmaya değecek en küçük kişi kutusu yüksekliği (piksel).
    # ⚠ Bu eşik ÇIKARIM UZAYINDA (640×640 letterbox) uygulanıyor, kaynak
    #   karede değil. 1280×720 kaynak 640'a inerken ölçek 0.5 olduğu için
    #   buradaki 180 px, kaynakta 360 px'e denk geliyor.
    expression_min_person_px: int = 180
    tracker: str = "botsort"

    # ⚠ 03.09.2026 — ÜÇ AYAR KALDIRILDI: HİÇBİRİ OKUNMUYORDU
    #
    #   use_tensorrt         (varsayılan True)
    #   use_fp16             (varsayılan True)
    #   privacy_blur_default (varsayılan True)
    #
    # Üçü de `config.py`'de tanımlıydı, `.env`'de değer taşıyordu ve
    # kodun HİÇBİR YERİNDE okunmuyordu. İkisi ayrıca aktif olarak
    # yanlış bilgi veriyordu:
    #
    #   · `use_tensorrt=true` — TensorRT üretimde KULLANILMIYOR.
    #     Ölçüldü (1.40×, tespitler birebir aynı) ama parti dolgunluğu
    #     yüzünden bilinçli olarak devreye alınmadı (ADR-0006).
    #     Ayarı okuyan biri tam tersi sonuca varırdı.
    #
    #   · `privacy_blur_default=true` — hiçbir yerde bulanıklaştırma
    #     YOK. Dahası bu değer `/api/v1/system/config` ile panele
    #     "true" diye YAYINLANIYORDU: API, yapmadığı bir şeyi yaptığını
    #     söylüyordu. Yüz bulanıklaştırma bu staj kapsamının dışında
    #     bırakıldı (ticari kurulum değil) ve doğru davranış, kapsam
    #     dışı bir özelliğin ayarını açık bırakmak değil KALDIRMAK.
    #
    #   · `use_fp16=true` — FP16 gerçekten kullanılıyor ama ayardan
    #     değil, dedektör kurulurken `half=True` sabitiyle. Ayar
    #     "değiştirilebilir" izlenimi veriyordu; değiştirilemiyordu.
    #
    # ⚠ Ders (bu projede üçüncü kez): YANLIŞ CEVAP VEREN BİR AYAR,
    # OLMAYAN AYARDAN KÖTÜDÜR. Aynı sınıf: kaldırılan `npm run lint`
    # (çalışmayan kalite kapısı), ölü Prometheus hedefleri (hep
    # kırmızı gösterge), `.env`'deki bayat admin parolası.
    #
    # `extra="ignore"` sayesinde `.env`'de kalan anahtarlar hata
    # üretmiyor; yine de oradan da temizlendiler.

    # ─── KVKK ─────────────────────────────────────────────────
    # ⚠ Bu ayar SİLİNMEDİ çünkü ölü değil: aşağıdaki doğrulayıcı
    # açılmaya çalışılırsa uygulamayı başlatmıyor. Yani bir mekanizma,
    # bir vaat değil — kaldırılan üçünden farkı tam olarak bu.
    store_face_crops: bool = False

    # ─── Türetilmiş yardımcılar ───────────────────────────────

    @field_validator("store_face_crops")
    @classmethod
    def _forbid_face_storage(cls, value: bool) -> bool:
        """Yüz görüntüsü saklamak KVKK m.6 kapsamında biyometrik veri
        işlemektir (PLAN.md §12.1). Kazara açılmasını engelliyoruz."""
        if value:
            raise ValueError(
                "STORE_FACE_CROPS=true KVKK gerekçesiyle yasaklandı. "
                "Yüz görüntüsü saklanmaz; yalnızca etiket ve güven skoru."
            )
        return value

    @property
    def origins(self) -> list[str]:
        """CORS / WebSocket Origin beyaz listesi."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def mediamtx_api_url(self) -> str:
        return f"http://{self.mediamtx_host}:{self.mediamtx_api_port}"

    @property
    def mediamtx_webrtc_url(self) -> str:
        """Tarayıcının WHEP için kullanacağı adres.

        ⚠ `mediamtx_host` DEĞİL `mediamtx_public_host`: bu URL panele
        gönderiliyor ve tarayıcı Docker ağının dışında. Konteyner içi
        servis adı (`mediamtx`) tarayıcıda çözülemez.
        """
        host = self.mediamtx_public_host or self.mediamtx_host
        return f"http://{host}:{self.mediamtx_webrtc_port}"

    @property
    def prometheus_url(self) -> str:
        return f"http://127.0.0.1:{self.prometheus_port}"

    @property
    def grafana_url(self) -> str:
        return f"http://127.0.0.1:{self.grafana_port}"

    def resolve_path(self, value: str) -> Path:
        """Göreli yolları proje köküne göre çözer.

        `.env`'de `models/yolo26s.pt` yazıyor. Worker'lar `backend/`
        dizininden çalıştığı için göreli yol yanlış yeri gösterirdi.
        """
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def detector_weights(self) -> Path:
        return self.resolve_path(self.detector_model_path)

    @property
    def pose_weights(self) -> Path:
        return self.resolve_path(self.pose_model_path)

    @property
    def face_detector_weights(self) -> Path:
        return self.resolve_path(self.face_detector_path)

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        pwd = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{pwd}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def effective_valkey_url(self) -> str:
        if self.valkey_url:
            return self.valkey_url
        pwd = self.valkey_password.get_secret_value()
        auth = f":{pwd}@" if pwd else ""
        return f"redis://{auth}{self.valkey_host}:{self.valkey_port}/0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ayarları bir kez yükleyip önbelleğe alır."""
    return Settings()


settings = get_settings()

__all__ = ["PROJECT_ROOT", "Settings", "get_settings", "settings"]
