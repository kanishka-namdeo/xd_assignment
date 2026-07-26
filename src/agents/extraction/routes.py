"""Extraction routing logic.

Deterministic routing based on extraction results and gate status.
No LLM calls — pure Python routing.
"""

from __future__ import annotations

import structlog

from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


def route_after_extraction(state: ApplicantState) -> str:
    """Route after extraction based on gate status.

    Args:
        state: Current applicant state.

    Returns:
        Route key: "extraction_passed" or "extraction_failed".
    """
    gate_status = state.get("gate_status", "unknown")

    if gate_status == "passed":
        logger.info(
            "route_extraction",
            route="extraction_passed",
            gate_status=gate_status,
        )
        return "extraction_passed"
    else:
        logger.warning(
            "route_extraction",
            route="extraction_failed",
            gate_status=gate_status,
            error_count=len(state.get("gate_errors", [])),
        )
        return "extraction_failed"
