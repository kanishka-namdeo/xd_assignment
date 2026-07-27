"""Shared tool wrapper utilities for reducing boilerplate in agent tools."""

import time
from functools import wraps
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


def tool_wrapper(
    tool_name: str | None = None,
    log_start: bool = False,
) -> Callable:
    """Decorator factory that adds timing and error-handling boilerplate to tool functions.

    Wraps a tool function with:
    - perf_counter timing and duration_ms logging
    - Structured log events for start/complete
    - Exception catching with logger.exception

    Use as:
        @tool
        @tool_wrapper("my_tool")
        def my_tool_fn(...): ...

    Or compose with langchain's @tool:
        @tool
        def my_tool_fn(...):
            return _run_with_timing("my_tool", lambda: logic())

    Args:
        tool_name: Name for log events. Defaults to the wrapped function's __name__.
        log_start: If True, log a DEBUG event when the tool starts.

    Returns:
        Decorated function with timing and error handling.
    """

    def decorator(func: Callable) -> Callable:
        name = tool_name or func.__name__

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            if log_start:
                logger.debug("tool_start", tool=name)
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info("tool_complete", tool=name, duration_ms=round(duration_ms, 2))
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.exception("tool_error", tool=name, error=str(e), duration_ms=round(duration_ms, 2))
                raise

        return wrapper

    return decorator


def _run_with_timing(
    tool_name: str,
    fn: Callable[[], Any],
) -> Any:
    """Execute a function with timing and error logging.

    Useful for tool bodies that want inline timing without a decorator:

        @tool
        def my_tool(...):
            return _run_with_timing("my_tool", lambda: logic())

    Args:
        tool_name: Name for log events.
        fn: Zero-argument callable containing the tool logic.

    Returns:
        The result of fn().
    """
    start = time.perf_counter()
    try:
        result = fn()
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("tool_complete", tool=tool_name, duration_ms=round(duration_ms, 2))
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("tool_error", tool=tool_name, error=str(e), duration_ms=round(duration_ms, 2))
        raise
