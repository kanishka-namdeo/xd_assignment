"""Langfuse trace context helpers for request-to-trace correlation."""

from __future__ import annotations

from contextvars import ContextVar

trace_context: ContextVar[dict | None] = ContextVar("trace_context", default=None)


def set_trace_context(
    trace_id: str,
    session_id: str,
    user_id: str | None = None,
) -> None:
    """Set the trace context for the current async task."""
    trace_context.set({
        "trace_id": trace_id,
        "session_id": session_id,
        "user_id": user_id,
    })


def get_trace_context() -> dict | None:
    """Get the current trace context, or None if not set."""
    return trace_context.get()


def clear_trace_context() -> None:
    """Clear the trace context for the current async task."""
    trace_context.set(None)
