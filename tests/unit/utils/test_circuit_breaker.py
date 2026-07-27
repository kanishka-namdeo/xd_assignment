"""Test circuit breaker for graceful degradation."""

import time
from unittest.mock import AsyncMock

import pytest

from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerState


def test_circuit_breaker_starts_closed():
    """Test that circuit breaker starts in CLOSED state."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_opens_after_threshold():
    """Test that circuit opens after reaching failure threshold."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    # Simulate 3 failures
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN


def test_circuit_breaker_transitions_to_half_open():
    """Test that circuit transitions to HALF_OPEN after recovery timeout."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Should transition to HALF_OPEN on next call
    assert cb.can_attempt() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN


def test_circuit_breaker_closes_after_success_in_half_open():
    """Test that circuit closes after successful call in HALF_OPEN state."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Transition to HALF_OPEN via can_attempt()
    assert cb.can_attempt() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN
    
    # Simulate successful call
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_reopens_after_failure_in_half_open():
    """Test that circuit reopens after failed call in HALF_OPEN state."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Simulate failed call
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN


def test_circuit_breaker_blocks_calls_when_open():
    """Test that circuit breaker blocks calls when OPEN."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    
    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    
    # Should not allow calls
    assert cb.can_attempt() is False


@pytest.mark.asyncio
async def test_circuit_breaker_decorator_success():
    """Test circuit breaker decorator with successful function."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    @cb
    async def successful_func():
        return "success"
    
    result = await successful_func()
    assert result == "success"
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_decorator_failure():
    """Test circuit breaker decorator with failing function."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    
    @cb
    async def failing_func():
        raise ValueError("test error")
    
    # First failure
    with pytest.raises(ValueError):
        await failing_func()
    assert cb.failure_count == 1
    assert cb.state == CircuitBreakerState.CLOSED
    
    # Second failure - should open circuit
    with pytest.raises(ValueError):
        await failing_func()
    assert cb.failure_count == 2
    assert cb.state == CircuitBreakerState.OPEN
    
    # Third call should be blocked
    with pytest.raises(Exception) as exc_info:
        await failing_func()
    error_msg = str(exc_info.value).lower()
    assert "circuit breaker" in error_msg and "open" in error_msg


@pytest.mark.asyncio
async def test_circuit_breaker_decorator_with_fallback():
    """Test circuit breaker decorator with fallback function."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    
    async def fallback():
        return "fallback_result"
    
    @cb(fallback=fallback)
    async def failing_func():
        raise ValueError("test error")
    
    # First failure - should raise
    with pytest.raises(ValueError):
        await failing_func()
    
    # Second failure - should open circuit
    with pytest.raises(ValueError):
        await failing_func()
    
    # Third call - circuit open, should use fallback
    result = await failing_func()
    assert result == "fallback_result"


def test_circuit_breaker_reset():
    """Test that circuit breaker can be manually reset."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    
    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    
    # Reset
    cb.reset()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0
