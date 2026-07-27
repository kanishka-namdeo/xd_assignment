"""Phase 3: Processing - invoke extraction and validation agent subgraphs."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from src.agents.orchestrator.di import _make_assistant_message
from src.utils.circuit_breaker import CircuitBreaker
from src.utils.retry import retry_transient
from src.utils.state_size import check_state_size

if TYPE_CHECKING:
    from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)

# Circuit breakers for subgraph invocations
# Opens after 3 failures, tests recovery after 5 minutes
_extraction_circuit = CircuitBreaker(
    failure_threshold=3, recovery_timeout=300, name="extraction_subgraph"
)
_validation_circuit = CircuitBreaker(
    failure_threshold=3, recovery_timeout=300, name="validation_subgraph"
)


async def _extraction_fallback(state: dict[str, Any]) -> dict[str, Any]:
    """Fallback when extraction circuit is open."""
    logger.warning(
        "extraction_circuit_open_using_fallback",
        application_id=state.get("application_id"),
    )
    return {
        "extracted_data": {},
        "gate_status": "failed",
        "gate_errors": [{"error": "Extraction service temporarily unavailable"}],
        "extraction_results": [],
    }


async def _validation_fallback(state: dict[str, Any]) -> dict[str, Any]:
    """Fallback when validation circuit is open."""
    logger.warning(
        "validation_circuit_open_using_fallback",
        application_id=state.get("application_id"),
    )
    return {
        "validation_results": {"status": "skipped", "error": "Validation service temporarily unavailable"},
        "discrepancies": [],
        "gate_status": "passed",
    }


@_extraction_circuit(fallback=_extraction_fallback)
@retry_transient(max_retries=3, base_delay=1.0)
async def _invoke_extraction_subgraph(graph: Any, state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Invoke extraction subgraph with retry and circuit breaker logic."""
    return await graph.ainvoke(state, config=config)


@_validation_circuit(fallback=_validation_fallback)
@retry_transient(max_retries=3, base_delay=1.0)
async def _invoke_validation_subgraph(state: dict[str, Any]) -> dict[str, Any]:
    """Invoke validation subgraph with retry and circuit breaker logic."""
    from src.agents.validation.graph import run_validation_agent
    return await run_validation_agent(state)


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
    extracted_data: dict[str, Any] = {}
    try:
        from src.agents.extraction.graph import get_extraction_subgraph

        graph = get_extraction_subgraph()
        config = {"configurable": {"thread_id": f"{application_id}_extraction", "recursion_limit": 10}}
        result = await _invoke_extraction_subgraph(graph, state, config)
        extraction_results = result.get("extraction_results", [])
        gate_status = result.get("gate_status", "unknown")
        logger.info("extraction_agent_complete", document_count=len(result.get("extracted_data", {})), gate_status=gate_status)

        if trace:
            trace.span(name="document_extraction", input={"applicant_id": applicant_id}, output={"documents_extracted": len(result.get("extracted_data", {}))})

        if gate_status == "failed":
            logger.warning("extraction_gate_failed", gate_errors=result.get("gate_errors"))
            return {
                "extracted_data": {},
                "extraction_results": extraction_results,
                "validation_results": {"overall_confidence": 0.0},
                "validation_confidence": 0.0,
                "discrepancies": [],
                "messages": [_make_assistant_message("Document extraction encountered validation errors. Please review your documents and try again.")],
                "current_phase": "review",
                "gate_status": "failed",
                "gate_errors": result.get("gate_errors", []),
            }

        # Convert extracted_data (keyed by doc_id) to doc_type keys
        raw_extracted = result.get("extracted_data", {})
        uploaded_docs = state.get("uploaded_documents", [])
        doc_id_to_type = {str(d.get("document_id")): d.get("document_type") for d in uploaded_docs if d.get("document_id")}
        for doc_id, fields in raw_extracted.items():
            doc_type = doc_id_to_type.get(str(doc_id))
            if not doc_type:
                for d in uploaded_docs:
                    if str(d.get("document_id")) == str(doc_id):
                        doc_type = d.get("document_type")
                        break
            if doc_type and fields:
                extracted_data[doc_type] = fields
                logger.info("extracted_data_mapped", doc_type=doc_type, doc_id=doc_id)
    except Exception as e:
        logger.exception("extraction_agent_failed", error=str(e))
        if trace:
            trace.span(name="document_extraction", input={"applicant_id": applicant_id}, output={"error": str(e)}, level="ERROR")
        return {
            "extracted_data": {},
            "extraction_results": [{"status": "failed", "error": str(e)}],
            "validation_results": {"overall_confidence": 0.0},
            "validation_confidence": 0.0,
            "discrepancies": [],
            "messages": [_make_assistant_message("Document extraction encountered an error. Please try again.")],
            "current_phase": "review",
            "gate_status": "failed",
            "gate_errors": [{"error": str(e)}],
        }

    # Validation subgraph
    validation_results: dict = {}
    discrepancies: list = []
    try:
        val_result = await _invoke_validation_subgraph({**state, "extracted_data": extracted_data, "extraction_results": extraction_results})
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

    # Preserve validation_results structure including overall_confidence
    # The validation agent returns: {"status": ..., "overall_confidence": ..., "discrepancies": ...}
    # We pass this through so the decision node can access validation_results.overall_confidence

    response = (
        f"Document processing is complete. We extracted data from {len(extracted_data)} document(s). "
        f"{f'However, we found {len(discrepancies)} discrepancy(ies) that need attention. Our team will review these during the next phase.' if discrepancies else 'All information is consistent across your documents. Moving to the review phase.'}"
    )

    if trace:
        trace.update(output={"documents_extracted": len(extracted_data), "discrepancies_found": len(discrepancies), "phase_transition": "review"})

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", node="processing", duration_ms=round(duration_ms, 2), extraction_count=len(extracted_data), discrepancy_count=len(discrepancies), validation_confidence=validation_results.get("overall_confidence"))
    check_state_size(state, node_name="processing", application_id=application_id)

    return {
        "extracted_data": extracted_data,
        "extraction_results": extraction_results,
        "validation_results": validation_results,
        "validation_confidence": validation_results.get("overall_confidence", 0.0),
        "discrepancies": discrepancies,
        "messages": [_make_assistant_message(response)],
        "current_phase": "review",
    }
