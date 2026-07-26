"""Phase 3: Processing - invoke extraction and validation agent subgraphs."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from src.agents.orchestrator.di import _make_assistant_message

if TYPE_CHECKING:
    from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


async def processing_node(state: dict[str, Any]) -> dict[str, Any]:
    """Phase 3: Processing - invoke extraction and validation agents."""
    start_ms = time.perf_counter()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    logger.info("node_enter", node="processing", application_id=application_id, applicant_id=applicant_id)

    # Langfuse tracing
    try:
        from src.infrastructure.observability import get_langfuse_client

        langfuse_client = get_langfuse_client()
        trace = langfuse_client.trace(
            name="processing_phase", session_id=application_id, user_id=applicant_id,
            tags=["processing", "document_extraction", "validation"],
            input={"application_id": application_id, "applicant_id": applicant_id},
        ) if langfuse_client else None
    except Exception:
        trace = None

    applicant_info = state.get("applicant_info", {})
    support_category = applicant_info.get("support_category", "")

    # Extraction subgraph
    extraction_results: list = []
    try:
        from src.agents.extraction.graph import get_extraction_subgraph

        graph = get_extraction_subgraph()
        config = {"configurable": {"thread_id": f"{application_id}_extraction"}}
        result = await graph.ainvoke(state, config=config)
        extraction_results = result.get("extraction_results", [])
        logger.info("extraction_agent_complete", document_count=len(extraction_results), gate_status=result.get("gate_status"))

        if trace:
            trace.span(name="document_extraction", input={"applicant_id": applicant_id}, output={"documents_extracted": len(extraction_results)})

        if result.get("gate_status") == "failed":
            logger.warning("extraction_gate_failed", gate_errors=result.get("gate_errors"))
            return {
                "extraction_results": extraction_results, "validation_results": {}, "discrepancies": [],
                "messages": [_make_assistant_message("Document extraction encountered validation errors. Please review your documents and try again.")],
                "current_phase": "review", "gate_status": "failed", "gate_errors": result.get("gate_errors", []),
            }
    except Exception as e:
        extraction_results = [{"status": "failed", "error": str(e)}]
        logger.exception("extraction_agent_failed", error=str(e))
        if trace:
            trace.span(name="document_extraction", input={"applicant_id": applicant_id}, output={"error": str(e)}, level="ERROR")

    # Validation subgraph
    validation_results: dict = {}
    discrepancies: list = []
    try:
        from src.agents.validation.graph import run_validation_agent

        val_result = await run_validation_agent({**state, "extraction_results": extraction_results})
        validation_results = val_result.get("validation_results", {})
        discrepancies = val_result.get("discrepancies", [])
        logger.info("validation_agent_complete", discrepancy_count=len(discrepancies), gate_status=val_result.get("gate_status"))

        if trace:
            trace.span(name="cross_document_validation", input={"applicant_id": applicant_id, "support_category": support_category}, output={"discrepancies_found": len(discrepancies)})
    except Exception as e:
        validation_results = {"status": "failed", "error": str(e)}
        logger.exception("validation_agent_failed", error=str(e))
        if trace:
            trace.span(name="cross_document_validation", input={"applicant_id": applicant_id, "support_category": support_category}, output={"error": str(e)}, level="ERROR")

    response = (
        f"Document processing is complete. We extracted data from {len(extraction_results)} document(s). "
        f"{f'However, we found {len(discrepancies)} discrepancy(ies) that need attention. Our team will review these during the next phase.' if discrepancies else 'All information is consistent across your documents. Moving to the review phase.'}"
    )

    if trace:
        trace.update(output={"documents_extracted": len(extraction_results), "discrepancies_found": len(discrepancies), "phase_transition": "review"})

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", node="processing", duration_ms=round(duration_ms, 2), extraction_count=len(extraction_results), discrepancy_count=len(discrepancies))

    return {
        "extraction_results": extraction_results, "validation_results": validation_results, "discrepancies": discrepancies,
        "messages": [_make_assistant_message(response)], "current_phase": "review",
    }
