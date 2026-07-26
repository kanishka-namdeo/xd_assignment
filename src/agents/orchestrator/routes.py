"""Conditional edge routing logic."""

import structlog
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


def route_by_phase(state: ApplicantState) -> str:
    """Route to the node matching the current phase."""
    phase = state.get("current_phase", "authentication")
    logger.info("routing_decision", phase=phase, applicant_id=state.get("applicant_id"), application_id=state.get("application_id"))
    return phase


def route_after_intake(state: ApplicantState) -> str:
    """Route after intake: loop back if missing fields, advance to document_collection."""
    phase = state.get("current_phase", "intake")
    logger.debug("routing_after_intake", next_phase=phase)
    return phase


def route_after_document_collection(state: ApplicantState) -> str:
    """Route after document collection: loop back if missing docs, advance to processing."""
    phase = state.get("current_phase", "document_collection")
    logger.debug("routing_after_document_collection", next_phase=phase)
    return phase


def route_after_review(state: ApplicantState) -> str:
    """Route after review: loop to document_collection if new docs, loop to review if discrepancies remain, advance to decision."""
    phase = state.get("current_phase", "decision")
    logger.debug("routing_after_review", next_phase=phase)
    return phase
