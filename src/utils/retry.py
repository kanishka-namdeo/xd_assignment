"""Retry decorators with exponential backoff for transient failures."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, TypeVar

import structlog

from src.utils.error_classifier import ErrorType, classify_error

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def retry_transient(
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that retries async functions on transient errors with exponential backoff.

    Delays follow exponential backoff: base_delay * 2^attempt (1s, 2s, 4s by default).
    Only retries when the error is classified as ErrorType.TRANSIENT.
    Non-transient errors are raised immediately without retry.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    error_type = classify_error(exc)
                    if error_type != ErrorType.TRANSIENT or attempt == max_retries:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "transient_error_retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=delay,
                        error=str(exc),
                        error_type=error_type.value,
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator
