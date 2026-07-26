"""Phase 0: Authentication - validate Emirates ID."""

from __future__ import annotations

import re
import time

import structlog

from src.agents.orchestrator.di import _get_last_message_content, _make_assistant_message
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


async def authentication_node(state: ApplicantState) -> ApplicantState:
    """Phase 0: Authentication - validate Emirates ID.

    Deterministic node that validates the Emirates ID identity number
    using the Luhn checksum. Transitions to intake on success,
    or escalates on failure.
    """
    start_ms = time.perf_counter()
    logger.info(
        "node_enter",
        node="authentication",
        current_phase=state.get("current_phase"),
        applicant_id=state.get("applicant_id"),
    )

    last_message = _get_last_message_content(state)
    user_text = last_message.strip()

    identity_number = state.get("identity_number")

    if not identity_number and user_text:
        match = re.search(r"(\d{14})", user_text)
        if match:
            identity_number = match.group(1)

    if not identity_number:
        response = (
            "Welcome to the UAE Social Support Application system. "
            "Please provide your Emirates ID number (14 digits) to begin your application."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "node_exit",
            node="authentication",
            duration_ms=round(duration_ms, 2),
            next_phase="authentication",
        )
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "authentication",
        }

    from src.utils.emirates_id import validate as emirates_id_validate

    is_valid = emirates_id_validate(str(identity_number))

    if is_valid:
        response = (
            f"Emirates ID verified successfully. "
            f"Welcome to the UAE Social Support Application system. "
            f"To get started, please provide your full name."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "node_exit",
            node="authentication",
            duration_ms=round(duration_ms, 2),
            next_phase="intake",
            identity_verified=True,
        )
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "intake",
            "identity_number": identity_number,
        }
    else:
        response = (
            "The Emirates ID number provided could not be verified. "
            "Please check the number and try again. "
            "The ID should be a 14-digit number."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.warning(
            "node_exit",
            node="authentication",
            duration_ms=round(duration_ms, 2),
            next_phase="authentication",
            identity_verified=False,
        )
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "authentication",
        }
