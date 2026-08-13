"""Yapılandırılmış loglama (structlog).

Geliştirmede renkli/okunabilir, üretimde JSON çıktı verir.
JSON önemli: log toplayıcılar (Loki, ELK) alanlara göre sorgu yapabilsin.

⚠ ASLA loglanmayacaklar (PLAN.md §13.3): parolalar, token'lar,
   RTSP kimlik bilgileri, ham kare verisi, yüz görüntüleri.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "jwt",
    "api_key",
    "access_key",
    "secret_key",
    "rtsp_url",
    "cookie",
}


def _redact_sensitive(
    _logger: Any, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Hassas alanları maskeler — kazara sır loglamaya karşı son savunma."""
    for key in list(event_dict):
        if any(marker in key.lower() for marker in _SENSITIVE_KEYS):
            event_dict[key] = "***"
    return event_dict


def configure_logging(level: str = "INFO", *, json_output: bool = False) -> None:
    """Loglamayı yapılandırır. Uygulama açılışında bir kez çağrılır."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        _redact_sensitive,
    ]

    if json_output:
        processors += [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors += [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


__all__ = ["configure_logging", "get_logger"]
