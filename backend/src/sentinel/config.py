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
    target_fps_high_risk: int = 8
    target_fps_idle: int = 1
    ingest_worker_count: int = 4
    ring_buffer_seconds: int = 30
    shm_slot_count: int = 128

    motion_gate_enabled: bool = True
    motion_threshold: float = 0.005
    motion_refresh_interval_s: int = 5

    # ─── Modeller ─────────────────────────────────────────────
    detector_backend: str = "yolo26"  # yolo26 | yolo11 | rtmdet
    detector_model_path: str = "models/yolo26s.pt"
    detector_conf_threshold: float = 0.35
    pose_model_path: str = "models/yolo26s-pose.pt"
    face_detector_path: str = "models/yunet.onnx"
    emotion_model_path: str = "models/emotieff.onnx"
    tracker: str = "botsort"
    use_tensorrt: bool = True
    use_fp16: bool = True

    # ─── KVKK ─────────────────────────────────────────────────
    privacy_blur_default: bool = True
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
        return f"http://{self.mediamtx_host}:{self.mediamtx_webrtc_port}"

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
