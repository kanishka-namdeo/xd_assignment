"""Gate retry logic for deterministic validation.

Executes agent functions with deterministic gates, retrying on gate failure
and escalating to manual review after max retries.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


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
            logger.debug("Executing agent_func (attempt %d/%d)", attempt + 1, max_retries + 1)
            updated_state = await agent_func(state)

            # Run gate validation
            logger.debug("Running gate validation")
            passes, errors = gate_func(updated_state)

            if passes:
                logger.info("Gate passed on attempt %d", attempt + 1)
                updated_state["gate_passed"] = True
                updated_state["gate_attempts"] = attempt + 1
                return updated_state

            # Gate failed
            last_errors = errors
            logger.warning(
                "Gate failed on attempt %d: %s",
                attempt + 1,
                errors if isinstance(errors, str) else ", ".join(errors),
            )

            # Feed errors back to state for next attempt
            updated_state["gate_errors"] = errors
            state = updated_state
            attempt += 1

        except Exception as e:
            logger.error("Error in execute_with_gate (attempt %d): %s", attempt + 1, e)
            state["gate_error"] = str(e)
            attempt += 1

    # Max retries exceeded — escalate to manual review
    logger.warning(
        "Gate failed after %d attempts, escalating to manual review",
        max_retries + 1,
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
            logger.debug("Executing agent_func (attempt %d/%d)", attempt + 1, max_retries + 1)
            updated_state = agent_func(state)

            # Run gate validation
            logger.debug("Running gate validation")
            passes, errors = gate_func(updated_state)

            if passes:
                logger.info("Gate passed on attempt %d", attempt + 1)
                updated_state["gate_passed"] = True
                updated_state["gate_attempts"] = attempt + 1
                return updated_state

            # Gate failed
            last_errors = errors
            logger.warning(
                "Gate failed on attempt %d: %s",
                attempt + 1,
                errors if isinstance(errors, str) else ", ".join(errors),
            )

            # Feed errors back to state for next attempt
            updated_state["gate_errors"] = errors
            state = updated_state
            attempt += 1

        except Exception as e:
            logger.error("Error in execute_with_gate_sync (attempt %d): %s", attempt + 1, e)
            state["gate_error"] = str(e)
            attempt += 1

    # Max retries exceeded — escalate to manual review
    logger.warning(
        "Gate failed after %d attempts, escalating to manual review",
        max_retries + 1,
    )
    state["gate_passed"] = False
    state["gate_attempts"] = attempt
    state["gate_escalated"] = True
    state["gate_final_errors"] = last_errors

    return state
