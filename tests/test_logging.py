"""Structured logging utilities for tests."""
from __future__ import annotations

import logging
import time

import structlog
from structlog.contextvars import clear_contextvars, set_contextvars


def configure_test_logging() -> None:
    """Configure structlog for test execution."""
    from src.infrastructure.observability.logging import configure_logging

    configure_logging()


class TestLogger:
    """Structured logger for test execution tracking using structlog."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = time.monotonic()
        self.logger = structlog.get_logger(test_name)

    def log_event(self, event: str, **kwargs) -> None:
        """Log a test event with structured data."""
        elapsed_ms = (time.monotonic() - self.start_time) * 1000
        self.logger.info(
            event,
            test=self.test_name,
            elapsed_ms=round(elapsed_ms, 1),
            **kwargs,
        )

    def log_error(self, event: str, error: Exception, **kwargs) -> None:
        """Log a test error with structured data."""
        elapsed_ms = (time.monotonic() - self.start_time) * 1000
        self.logger.exception(
            event,
            test=self.test_name,
            elapsed_ms=round(elapsed_ms, 1),
            error=str(error),
            **kwargs,
        )

    def log_phase(self, phase: str, **kwargs) -> None:
        """Log a phase transition."""
        self.log_event(f"phase_{phase}", **kwargs)


def get_test_logger(test_name: str) -> TestLogger:
    """Get a test logger instance."""
    return TestLogger(test_name)
