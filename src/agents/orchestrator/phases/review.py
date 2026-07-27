"""Phase 4: Review - detect new uploads, generate clarification questions."""

from __future__ import annotations

import time

import structlog
from langgraph.types import interrupt

from src.agents.orchestrator.di import _make_assistant_message
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


async def review_node(state: ApplicantState) -> ApplicantState:
    """Phase 4: Review - detect new uploads, generate clarification questions.

    Checks if new files were uploaded since last review. If so, transitions back
    to document_collection. Otherwise, uses applicant_clarify_tool to generate
    clarification questions for each discrepancy. Transitions to decision when
    no discrepancies remain. Uses interrupt() to pause for user responses.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", node="review", applicant_id=state.get("applicant_id"), discrepancy_count=len(state.get("discrepancies", [])))

    uploaded_files = state.get("uploaded_files", [])
    uploaded_documents = state.get("uploaded_documents", [])
    discrepancies = state.get("discrepancies", [])
    applicant_info = state.get("applicant_info", {})

    # Detect new files uploaded since last review
    previous_doc_count = len([d for d in uploaded_documents if d.get("file_path") in uploaded_files])
    if state.get("new_documents_uploaded", False) or len(uploaded_files) > previous_doc_count:
        response = (
            "New documents detected. Returning to document collection to process them."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info("node_exit", node="review", duration_ms=round(duration_ms, 2), next_phase="document_collection", new_documents=True)
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "document_collection",
            "new_documents_uploaded": False,
        }

    # Check if there are unresolved discrepancies
    unresolved = [d for d in discrepancies if d.get("resolution_status") != "resolved"]

    if not unresolved:
        response = (
            "Review complete. All documents have been cross-checked and validated. "
            "Your information is consistent across all submitted documents. "
            "Proceeding to the decision phase."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info("node_exit", node="review", duration_ms=round(duration_ms, 2), next_phase="decision", discrepancy_count=0)
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "decision",
        }

    # Generate clarification questions for unresolved discrepancies
    from src.agents.validation.tools import applicant_clarify_tool

    applicant_context = {
        "applicant_id": state.get("applicant_id", "unknown"),
        "application_id": state.get("application_id", "unknown"),
        "support_category": applicant_info.get("support_category", "unknown"),
    }

    clarification_questions = []
    for disc in unresolved:
        try:
            result = applicant_clarify_tool.invoke({
                "discrepancy": disc,
                "applicant_context": applicant_context,
            })
            question = result.get("question", "")
            clarification_questions.append(question)
        except Exception as e:
            logger.warning("clarify_tool_failed", discrepancy_type=disc.get("type"), error=str(e))
            clarification_questions.append(f"We need clarification on: {disc.get('message', disc.get('type', 'unknown'))}")

    questions_text = "\n".join(f"- {q}" for q in clarification_questions if q)
    response = (
        f"We found some inconsistencies in your documents that need clarification:\n\n"
        f"{questions_text}\n\n"
        f"Please provide the requested information or upload corrected documents."
    )

    # Use interrupt() to pause and wait for user response
    user_response = interrupt({
        "question": response,
        "discrepancies": [{"type": d.get("type"), "message": d.get("message")} for d in unresolved],
        "phase": "review",
    })

    # When resumed, process the user response to update discrepancy resolution status
    resolved_discrepancies = []
    if user_response:
        # Mark discrepancies as resolved based on user response
        # Simple heuristic: if user provides clarification, mark as resolved
        for disc in discrepancies:
            # Create a new dict to avoid mutating the original
            disc_copy = {**disc}
            if disc_copy.get("resolution_status") != "resolved":
                # Check if the user response addresses this discrepancy
                disc_type = disc_copy.get("type", "")
                disc_message = disc_copy.get("message", "")
                if disc_type and disc_type.lower() in str(user_response).lower():
                    disc_copy["resolution_status"] = "resolved"
                    disc_copy["resolution"] = str(user_response)
                elif disc_message and disc_message.lower() in str(user_response).lower():
                    disc_copy["resolution_status"] = "resolved"
                    disc_copy["resolution"] = str(user_response)
            resolved_discrepancies.append(disc_copy)
    else:
        # No user response - return original discrepancies unchanged
        resolved_discrepancies = list(discrepancies)

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", node="review", duration_ms=round(duration_ms, 2), next_phase="review", discrepancy_count=len(unresolved))

    return {
        "messages": [_make_assistant_message(response)],
        "current_phase": "review",
        "discrepancies": resolved_discrepancies,
    }
