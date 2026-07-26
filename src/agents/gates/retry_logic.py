"""Gate retry logic for deterministic validation.

Executes agent functions with deterministic gates, retrying on gate failure
and escalating to manual review after max retries.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import structlog

logger = structlog.get_logger(__name__)


async def execute_with_gate(
    agent_func: Callable[..., Awaitable[dict]],
    gate_func: Callable[[dict], tuple[bool, list[str] | str | None]],
    state: dict,
    max_retries: int = 2,
) -> dict:
    """Execute agent function with deterministic gate validation.

    If the gate fails, feeds error back to agent and retries.
    After max_retries, escalates to manual review.

    Args:
        agent_func: Async function that processes the state and returns updated state.
        gate_func: Sync function that validates the state and returns (passes, errors).
        state: Current agent state dictionary.
        max_retries: Maximum number of retry attempts (default 2).

    Returns:
        Updated state dictionary with gate results.
    """
    attempt = 0
    last_errors: list[str] | str | None = None

    while attempt <= max_retries:
        try:
            # Execute agent function
            logger.debug("gate_execution", step="agent_func_start", attempt=attempt + 1, max_attempts=max_retries + 1, application_id=state.get("application_id"), document_type=state.get("document_type"))
            updated_state = await agent_func(state)

            # Run gate validation
            logger.debug("gate_execution", step="gate_start", attempt=attempt + 1)
            passes, errors = gate_func(updated_state)

            if passes:
                logger.info("gate_passed", attempt=attempt + 1, application_id=state.get("application_id"))
                updated_state["gate_passed"] = True
                updated_state["gate_attempts"] = attempt + 1
                return updated_state

            # Gate failed
            last_errors = errors
            logger.warning(
                "gate_failed",
                attempt=attempt + 1,
                errors=errors if isinstance(errors, str) else errors,
                application_id=state.get("application_id"),
                document_type=state.get("document_type"),
            )

            # Feed errors back to state for next attempt
            updated_state["gate_errors"] = errors
            state = updated_state
            attempt += 1

        except Exception as e:
            logger.exception("gate_error", attempt=attempt + 1, error=str(e), application_id=state.get("application_id"))
            state["gate_error"] = str(e)
            attempt += 1

    # Max retries exceeded — escalate to manual review
    logger.warning(
        "gate_escalated",
        total_attempts=attempt,
        max_retries=max_retries,
        final_errors=last_errors,
        application_id=state.get("application_id"),
    )
    state["gate_passed"] = False
    state["gate_attempts"] = attempt
    state["gate_escalated"] = True
    state["gate_final_errors"] = last_errors

    return state


def execute_with_gate_sync(
    agent_func: Callable[[dict], dict],
    gate_func: Callable[[dict], tuple[bool, list[str] | str | None]],
    state: dict,
    max_retries: int = 2,
) -> dict:
    """Synchronous version of execute_with_gate.

    Args:
        agent_func: Sync function that processes the state and returns updated state.
        gate_func: Sync function that validates the state and returns (passes, errors).
        state: Current agent state dictionary.
        max_retries: Maximum number of retry attempts (default 2).

    Returns:
        Updated state dictionary with gate results.
    """
    attempt = 0
    last_errors: list[str] | str | None = None

    while attempt <= max_retries:
        try:
            # Execute agent function
            logger.debug("gate_execution", step="agent_func_start", attempt=attempt + 1, max_attempts=max_retries + 1, application_id=state.get("application_id"), document_type=state.get("document_type"))
            updated_state = agent_func(state)

            # Run gate validation
            logger.debug("gate_execution", step="gate_start", attempt=attempt + 1)
            passes, errors = gate_func(updated_state)

            if passes:
                logger.info("gate_passed", attempt=attempt + 1, application_id=state.get("application_id"))
                updated_state["gate_passed"] = True
                updated_state["gate_attempts"] = attempt + 1
                return updated_state

            # Gate failed
            last_errors = errors
            logger.warning(
                "gate_failed",
                attempt=attempt + 1,
                errors=errors if isinstance(errors, str) else errors,
                application_id=state.get("application_id"),
                document_type=state.get("document_type"),
            )

            # Feed errors back to state for next attempt
            updated_state["gate_errors"] = errors
            state = updated_state
            attempt += 1

        except Exception as e:
            logger.exception("gate_error", attempt=attempt + 1, error=str(e), application_id=state.get("application_id"))
            state["gate_error"] = str(e)
            attempt += 1

    # Max retries exceeded — escalate to manual review
    logger.warning(
        "gate_escalated",
        total_attempts=attempt,
        max_retries=max_retries,
        final_errors=last_errors,
        application_id=state.get("application_id"),
    )
    state["gate_passed"] = False
    state["gate_attempts"] = attempt
    state["gate_escalated"] = True
    state["gate_final_errors"] = last_errors

    return state
