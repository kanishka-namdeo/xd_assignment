"""Tests for retry_transient decorator."""

import pytest

from src.utils.retry import retry_transient


@pytest.mark.asyncio
async def test_retry_on_transient_error() -> None:
    """Test that transient errors trigger retries."""
    call_count = 0

    @retry_transient(max_retries=3, base_delay=0.01)
    async def failing_func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Transient failure")
        return "success"

    result = await failing_func()
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_non_transient_error() -> None:
    """Test that non-transient errors don't trigger retries."""
    call_count = 0

    @retry_transient(max_retries=3, base_delay=0.01)
    async def failing_func() -> str:
        nonlocal call_count
        call_count += 1
        raise ValueError("Non-transient error")

    with pytest.raises(ValueError, match="Non-transient error"):
        await failing_func()
    assert call_count == 1


@pytest.mark.asyncio
async def test_max_retries_exceeded() -> None:
    """Test that function raises after max retries."""
    call_count = 0

    @retry_transient(max_retries=2, base_delay=0.01)
    async def failing_func() -> str:
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Always fails")

    with pytest.raises(ConnectionError, match="Always fails"):
        await failing_func()
    assert call_count == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_exponential_backoff_delays() -> None:
    """Test that delays follow exponential backoff pattern."""
    import time

    call_times: list[float] = []

    @retry_transient(max_retries=3, base_delay=0.05)
    async def failing_func() -> str:
        call_times.append(time.perf_counter())
        if len(call_times) < 3:
            raise TimeoutError("Transient timeout")
        return "success"

    result = await failing_func()
    assert result == "success"
    assert len(call_times) == 3

    # Check delays are roughly exponential (0.05s, 0.1s)
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]
    assert 0.04 <= delay1 <= 0.08  # ~0.05s
    assert 0.08 <= delay2 <= 0.15  # ~0.1s


@pytest.mark.asyncio
async def test_successful_first_attempt() -> None:
    """Test that successful first attempt doesn't retry."""
    call_count = 0

    @retry_transient(max_retries=3, base_delay=0.01)
    async def success_func() -> str:
        nonlocal call_count
        call_count += 1
        return "immediate success"

    result = await success_func()
    assert result == "immediate success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_preserves_function_metadata() -> None:
    """Test that decorator preserves function name and docstring."""

    @retry_transient(max_retries=3, base_delay=0.01)
    async def documented_func() -> str:
        """This is a test function."""
        return "test"

    assert documented_func.__name__ == "documented_func"
    assert documented_func.__doc__ == "This is a test function."
