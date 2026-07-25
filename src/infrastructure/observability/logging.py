"""Central structlog configuration with PII masking and stdlib bridging."""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars
from structlog.dev import ConsoleRenderer
from structlog.processors import (
    JSONRenderer,
    StackInfoRenderer,
    TimeStamper,
    add_log_level,
    format_exc_info,
)
from structlog.stdlib import ProcessorFormatter

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "identity_number",
        "full_name",
        "full_name_en",
        "full_name_ar",
        "email",
        "phone",
        "contact_phone",
        "contact_email",
        "account_number",
        "iban",
        "password",
        "token",
        "secret_key",
        "api_key",
        "mother_name",
        "sponsor_name",
    }
)

_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{15}\b"),
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    re.compile(r"\bAE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{3}\b", re.IGNORECASE),
)

REDACTED = "[REDACTED]"


def pii_redactor(
    _logger: logging.Logger, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
            continue
        if isinstance(value, str):
            if any(pattern.search(value) for pattern in _PII_PATTERNS):
                event_dict[key] = REDACTED
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    renderer: structlog.types.Processor = (
        JSONRenderer() if log_format == "json" else ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.contextvars.merge_contextvars,
            pii_redactor,
            TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level=level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=[
                add_log_level,
                TimeStamper(fmt="iso"),
                format_exc_info,
                StackInfoRenderer(),
                merge_contextvars,
                pii_redactor,
            ],
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
