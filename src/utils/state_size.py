"""State size estimation and validation for LangGraph checkpoint management.

LangGraph checkpoints the full state after each node execution. Large state
objects can cause slow serialization, increased storage, and memory pressure.
This module provides utilities to estimate and monitor state size.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


def estimate_state_size(state: dict[str, Any]) -> int:
    """Estimate the serialized size of a state dict in bytes.

    Uses JSON serialization for a realistic size estimate. Falls back to
    sys.getsizeof if serialization fails (e.g. non-serializable objects).

    Args:
        state: The LangGraph state dictionary to measure.

    Returns:
        Estimated size in bytes.
    """
    try:
        serialized = json.dumps(state, default=str)
        return len(serialized.encode("utf-8"))
    except (TypeError, ValueError, OverflowError):
        return sys.getsizeof(state)


def check_state_size(
    state: dict[str, Any],
    node_name: str | None = None,
    application_id: str | None = None,
) -> int:
    """Check state size and log warnings if it exceeds the threshold.

    This function is non-blocking — it logs warnings but never raises
    or prevents graph execution.

    Args:
        state: The LangGraph state dictionary to check.
        node_name: Optional name of the node producing this state.
        application_id: Optional application ID for log context.

    Returns:
        The estimated size in bytes.
    """
    size_bytes = estimate_state_size(state)
    size_kb = size_bytes / 1024
    threshold_kb = settings.STATE_SIZE_WARNING_KB

    log_kwargs: dict[str, Any] = {
        "state_size_bytes": size_bytes,
        "state_size_kb": round(size_kb, 2),
    }
    if node_name:
        log_kwargs["node"] = node_name
    if application_id:
        log_kwargs["application_id"] = application_id

    if size_kb > threshold_kb:
        logger.warning(
            "state_size_exceeded",
            threshold_kb=threshold_kb,
            **log_kwargs,
        )
    else:
        logger.debug("state_size_check", **log_kwargs)

    return size_bytes
