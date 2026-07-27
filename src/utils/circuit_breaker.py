"""Circuit breaker for graceful degradation of subgraph invocations.

Implements the circuit breaker pattern to prevent cascading failures when
subgraphs consistently fail. After N failures in M minutes, the circuit
opens and skips the subgraph, calling fallback immediately.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failing, requests blocked, fallback called immediately
- HALF_OPEN: Testing recovery, one request allowed through
"""

import time
from enum import Enum
from functools import wraps
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and no fallback provided."""

    def __init__(self, name: str, failure_count: int, last_failure: float):
        self.name = name
        self.failure_count = failure_count
        self.last_failure = last_failure
        super().__init__(
            f"Circuit breaker '{name}' is open after {failure_count} failures"
        )


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Usage:
        # As decorator
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)

        @cb
        async def invoke_subgraph():
            return await graph.ainvoke(state)

        # With fallback
        async def fallback():
            return default_result

        @cb(fallback=fallback)
        async def invoke_subgraph():
            return await graph.ainvoke(state)
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 300.0,
        name: str = "unnamed",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery (HALF_OPEN)
            name: Name for logging (e.g., "extraction_subgraph")
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.time()

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Number of consecutive failures."""
        return self._failure_count

    def can_attempt(self) -> bool:
        """Check if a request can be attempted.

        Returns:
            True if request can proceed, False if circuit is open
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._transition_to(CircuitBreakerState.HALF_OPEN)
                return True
            return False

        # HALF_OPEN: allow one attempt
        return True

    def record_success(self) -> None:
        """Record a successful call. Closes circuit if in HALF_OPEN."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            logger.info(
                "circuit_breaker_closed",
                circuit_name=self.name,
                message="Successful call in HALF_OPEN state, closing circuit",
            )
            self._transition_to(CircuitBreakerState.CLOSED)
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call. Opens circuit if threshold reached."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Failed in HALF_OPEN, reopen circuit
            logger.warning(
                "circuit_breaker_reopened",
                circuit_name=self.name,
                failure_count=self._failure_count,
                message="Failed call in HALF_OPEN state, reopening circuit",
            )
            self._transition_to(CircuitBreakerState.OPEN)

        elif self._state == CircuitBreakerState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                logger.warning(
                    "circuit_breaker_opened",
                    circuit_name=self.name,
                    failure_count=self._failure_count,
                    threshold=self.failure_threshold,
                    message=f"Circuit opened after {self._failure_count} failures",
                )
                self._transition_to(CircuitBreakerState.OPEN)

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(
            "circuit_breaker_reset",
            circuit_name=self.name,
            previous_state=self._state.value,
            previous_failure_count=self._failure_count,
        )
        self._transition_to(CircuitBreakerState.CLOSED)
        self._failure_count = 0

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        logger.debug(
            "circuit_breaker_state_change",
            circuit_name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
        )

    def __call__(self, func: Callable | None = None, *, fallback: Callable | None = None):
        """Use as decorator with optional fallback.

        Usage:
            @cb
            async def func(): ...

            @cb(fallback=fallback_func)
            async def func(): ...
        """
        if func is None:
            # Called with arguments: @cb(fallback=...)
            return lambda f: self._decorate(f, fallback)
        # Called without arguments: @cb
        return self._decorate(func, fallback)

    def _decorate(self, func: Callable, fallback: Callable | None = None) -> Callable:
        """Decorate a function with circuit breaker logic."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.can_attempt():
                if fallback:
                    logger.warning(
                        "circuit_breaker_fallback_called",
                        circuit_name=self.name,
                        failure_count=self._failure_count,
                        message="Circuit open, calling fallback",
                    )
                    return await fallback() if _is_coroutine(fallback) else fallback()
                raise CircuitBreakerOpen(
                    self.name, self._failure_count, self._last_failure_time
                )

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        return wrapper


def _is_coroutine(func: Callable) -> bool:
    """Check if a function is a coroutine function."""
    import asyncio
    return asyncio.iscoroutinefunction(func)
