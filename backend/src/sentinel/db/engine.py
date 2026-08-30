"""Veritabanı bağlantı havuzu.

⚠ NEDEN TEK BİR MOTOR, MODÜL SEVİYESİNDE
SQLAlchemy `AsyncEngine` kendi bağlantı havuzunu tutuyor. Her istekte
yeni motor kurmak, her istekte yeni bir havuz açmak demek — bağlantı
sayısı süreç ömrü boyunca birikir ve PostgreSQL `too many connections`
ile reddetmeye başlar.

⚠ NEDEN `NullPool` DEĞİL
Worker'lar uzun ömürlü ve saniyede birkaç kez yazıyor; her yazımda TCP
+ TLS + kimlik doğrulama turu atmak, yazılan verinin kendisinden pahalı
olurdu.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from sentinel.config import get_settings
from sentinel.logging import get_logger

log = get_logger(__name__)

_motor: AsyncEngine | None = None


def motor() -> AsyncEngine:
    """Süreç ömrü boyunca tek olan veritabanı motorunu döndürür."""
    global _motor
    if _motor is None:
        ayarlar = get_settings()
        _motor = create_async_engine(
            ayarlar.effective_database_url,
            # ⚠ Havuz küçük tutuluyor: bu süreçlerin hiçbiri veritabanı
            # ağırlıklı değil. Analytics worker saniyede birkaç satır
            # yazıyor, API sorguları seyrek. Büyük havuz boşuna bağlantı
            # tutar ve aynı makinedeki `teknofest_postgres` ile birlikte
            # sunucunun bağlantı bütçesini zorlar.
            pool_size=5,
            max_overflow=5,
            # Bağlantı bu süre boşta kalırsa yenileniyor. Uzun süre
            # boşta duran bağlantılar güvenlik duvarları ve PostgreSQL
            # tarafından sessizce kapatılabiliyor; yenilemeden
            # kullanmak "server closed the connection unexpectedly"
            # hatasına yol açar.
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
        )
        log.info(
            "veritabani_motoru_kuruldu",
            host=ayarlar.postgres_host,
            port=ayarlar.postgres_port,
            db=ayarlar.postgres_db,
        )
    return _motor


async def kapat() -> None:
    """Havuzu kapatır — kapanışta çağrılmalı."""
    global _motor
    if _motor is not None:
        await _motor.dispose()
        _motor = None


__all__ = ["kapat", "motor"]
