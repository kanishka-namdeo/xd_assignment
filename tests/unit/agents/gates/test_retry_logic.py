"""Unit tests for retry logic gate."""

import pytest
import asyncio
import structlog

from src.agents.gates.retry_logic import execute_with_gate, execute_with_gate_sync

logger = structlog.get_logger(__name__)


class TestExecuteWithGateSync:
    """Test synchronous execute_with_gate function."""

    def test_gate_passes_first_attempt(self):
        """Gate passes on first attempt should return immediately."""
        call_count = 0

        def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "processed": True}

        def gate_func(state):
            return True, []

        state = {"initial": "data"}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=2)

        assert call_count == 1
        assert result["gate_passed"] is True
        assert result["gate_attempts"] == 1
        assert result["processed"] is True
        assert "gate_escalated" not in result

    def test_gate_passes_after_retry(self):
        """Gate passes after retry should succeed."""
        call_count = 0

        def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "attempt": call_count}

        def gate_func(state):
            # Pass on second attempt
            if state.get("attempt", 0) >= 2:
                return True, []
            return False, ["Error on first attempt"]

        state = {"initial": "data"}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=2)

        assert call_count == 2
        assert result["gate_passed"] is True
        assert result["gate_attempts"] == 2
        assert result["attempt"] == 2

    def test_gate_fails_all_retries(self):
        """Gate fails all retries should escalate."""
        call_count = 0

        def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "attempt": call_count}

        def gate_func(state):
            return False, [f"Error on attempt {state.get('attempt', 0)}"]

        state = {"initial": "data"}
        logger.debug("test_start", test="gate_fails_all_retries", max_retries=2)
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=2)

        assert call_count == 3  # Initial + 2 retries
        assert result["gate_passed"] is False
        assert result["gate_attempts"] == 3
        assert result["gate_escalated"] is True
        assert result["gate_final_errors"] == ["Error on attempt 3"]

    def test_agent_func_raises_exception(self):
        """Agent function raising exception should be caught."""
        call_count = 0

        def agent_func(state):
            nonlocal call_count
            call_count += 1
            raise ValueError("Agent error")

        def gate_func(state):
            return True, []

        state = {"initial": "data"}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=1)

        assert call_count == 2  # Initial + 1 retry
        assert result["gate_passed"] is False
        assert result["gate_escalated"] is True
        assert "gate_error" in result

    def test_zero_max_retries(self):
        """Zero max retries should only attempt once."""
        call_count = 0

        def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "attempt": call_count}

        def gate_func(state):
            return False, ["Always fails"]

        state = {"initial": "data"}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=0)

        assert call_count == 1
        assert result["gate_passed"] is False
        assert result["gate_attempts"] == 1
        assert result["gate_escalated"] is True

    def test_gate_errors_propagated_to_state(self):
        """Gate errors should be propagated to state for next attempt."""
        received_errors = []
        call_count = 0

        def agent_func(state):
            nonlocal call_count
            call_count += 1
            if "gate_errors" in state:
                received_errors.append(state["gate_errors"])
            return {**state, "attempt": call_count}

        def gate_func(state):
            if state.get("attempt", 0) < 2:
                return False, ["Error message"]
            return True, []

        state = {"initial": "data"}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=2)

        assert len(received_errors) > 0
        assert result["gate_passed"] is True


class TestExecuteWithGateAsync:
    """Test asynchronous execute_with_gate function."""

    @pytest.mark.asyncio
    async def test_async_gate_passes_first_attempt(self):
        """Async gate passes on first attempt should return immediately."""
        call_count = 0

        async def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "processed": True}

        def gate_func(state):
            return True, []

        state = {"initial": "data"}
        result = await execute_with_gate(agent_func, gate_func, state, max_retries=2)

        assert call_count == 1
        assert result["gate_passed"] is True
        assert result["gate_attempts"] == 1
        assert result["processed"] is True

    @pytest.mark.asyncio
    async def test_async_gate_passes_after_retry(self):
        """Async gate passes after retry should succeed."""
        call_count = 0

        async def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "attempt": call_count}

        def gate_func(state):
            if state.get("attempt", 0) >= 2:
                return True, []
            return False, ["Error on first attempt"]

        state = {"initial": "data"}
        result = await execute_with_gate(agent_func, gate_func, state, max_retries=2)

        assert call_count == 2
        assert result["gate_passed"] is True
        assert result["gate_attempts"] == 2

    @pytest.mark.asyncio
    async def test_async_gate_fails_all_retries(self):
        """Async gate fails all retries should escalate."""
        call_count = 0

        async def agent_func(state):
            nonlocal call_count
            call_count += 1
            return {**state, "attempt": call_count}

        def gate_func(state):
            return False, [f"Error on attempt {state.get('attempt', 0)}"]

        state = {"initial": "data"}
        result = await execute_with_gate(agent_func, gate_func, state, max_retries=2)

        assert call_count == 3
        assert result["gate_passed"] is False
        assert result["gate_attempts"] == 3
        assert result["gate_escalated"] is True

    @pytest.mark.asyncio
    async def test_async_agent_func_raises_exception(self):
        """Async agent function raising exception should be caught."""
        call_count = 0

        async def agent_func(state):
            nonlocal call_count
            call_count += 1
            raise ValueError("Async agent error")

        def gate_func(state):
            return True, []

        state = {"initial": "data"}
        result = await execute_with_gate(agent_func, gate_func, state, max_retries=1)

        assert call_count == 2
        assert result["gate_passed"] is False
        assert result["gate_escalated"] is True
        assert "gate_error" in result

    @pytest.mark.asyncio
    async def test_async_with_real_gate(self):
        """Test with real gate function."""
        from src.agents.gates.document_integrity import validate_document_integrity

        async def agent_func(state):
            # Simulate agent processing
            return {
                **state,
                "extracted_data": {
                    "identity_number": "784-2000-1234567-2",
                    "full_name_en": "John Doe",
                    "nationality": "UAE",
                    "date_of_birth": "1990-01-01",
                    "gender": "Male",
                    "expiry_date": "2030-12-31",
                    "is_mrz_verified": True,
                },
            }

        def gate_func(state):
            return validate_document_integrity(
                state.get("extracted_data", {}),
                "emirates_id"
            )

        state = {}
        result = await execute_with_gate(agent_func, gate_func, state, max_retries=2)

        assert result["gate_passed"] is True
        assert result["gate_attempts"] == 1


class TestRetryLogicEdgeCases:
    """Test edge cases in retry logic."""

    def test_gate_returns_string_error(self):
        """Gate returning string error instead of list should work."""
        def agent_func(state):
            return state

        def gate_func(state):
            return False, "Single error string"

        state = {"initial": "data"}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=0)

        assert result["gate_passed"] is False
        assert result["gate_escalated"] is True
        assert result["gate_final_errors"] == "Single error string"

    def test_state_mutation_across_retries(self):
        """State should be properly mutated across retries."""
        attempts = []

        def agent_func(state):
            attempts.append(state.copy())
            return {**state, "counter": state.get("counter", 0) + 1}

        def gate_func(state):
            if state.get("counter", 0) >= 3:
                return True, []
            return False, ["Not enough"]

        state = {"counter": 0}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=5)

        assert result["gate_passed"] is True
        assert result["counter"] == 3
        assert len(attempts) == 3

    def test_empty_errors_list(self):
        """Gate with empty errors list should still fail."""
        def agent_func(state):
            return state

        def gate_func(state):
            return False, []  # Empty errors but still fails

        state = {}
        result = execute_with_gate_sync(agent_func, gate_func, state, max_retries=0)

        assert result["gate_passed"] is False
        assert result["gate_escalated"] is True
