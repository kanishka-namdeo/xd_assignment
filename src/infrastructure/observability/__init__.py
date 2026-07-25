"""Observability infrastructure (Langfuse, structured logging, tracing)."""

from src.infrastructure.observability.langfuse_client import LangfuseClient
from src.infrastructure.observability.logging import configure_logging
from src.infrastructure.observability.tracing import clear_trace_context, get_trace_context, set_trace_context

_langfuse_client: LangfuseClient | None = None


def set_langfuse_client(client: LangfuseClient) -> None:
    """Store a module-level LangfuseClient singleton for access by nodes."""
    global _langfuse_client
    _langfuse_client = client


def get_langfuse_client() -> LangfuseClient | None:
    """Return the module-level LangfuseClient singleton, or None."""
    return _langfuse_client


__all__ = [
    "LangfuseClient",
    "configure_logging",
    "get_langfuse_client",
    "set_langfuse_client",
    "clear_trace_context",
    "get_trace_context",
    "set_trace_context",
]
