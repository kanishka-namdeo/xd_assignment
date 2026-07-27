"""Validation node functions implementing Reflexion reasoning loop.

Nodes:
- attempt_validation: Initial validation pass with per-doc and cross-doc checks
- evaluate_validation: Assess discrepancies and classify as OCR errors or real
- critique_validation: Self-critique and decide if retry needed
- generate_clarification: Create questions for unresolved discrepancies
- finalize_validation: Compute confidence and prepare results
- gate_2_check: Deterministic completeness validation
"""

from __future__ import annotations

import json
import time

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain.agents import create_agent

from src.agents.gates.completeness import validate_completeness
from src.agents.state import ApplicantState
from src.agents.validation.prompts import VALIDATION_SYSTEM_PROMPT
from src.agents.validation.tools import (
    applicant_clarify_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    per_document_validation_tool,
    validation_confidence_tool,
)
from src.config import settings
from src.domain.constants.document_types import DEFAULT_REQUIRED_DOCUMENTS, REQUIRED_DOCUMENTS

logger = structlog.get_logger(__name__)


def _get_llm():
    """Get LangChain ChatModel for ReAct agent."""
    try:
        from langchain_openai import ChatOpenAI

        if settings.LLM_PROVIDER == "streamlake":
            return ChatOpenAI(
                model=settings.STREAMLAKE_MODEL,
                base_url=settings.STREAMLAKE_BASE_URL,
                api_key=settings.STREAMLAKE_API_KEY.get_secret_value(),
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        else:
            return ChatOpenAI(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                api_key=settings.OLLAMA_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
    except ImportError:
        logger.error("langchain_openai_not_installed")
        raise


async def attempt_validation_node(state: ApplicantState) -> dict:
    """Attempt node: Run initial validation on all extracted documents.

    Uses LangGraph's create_react_agent with 5 validation tools:
    - per_document_validation_tool: Per-document integrity checks
    - cross_document_compare_tool: Cross-document consistency
    - discrepancy_classify_tool: OCR error vs real discrepancy
    - applicant_clarify_tool: Generate clarification questions
    - validation_confidence_tool: Overall confidence scoring
    """
    start = time.perf_counter()
    logger.info(
        "node_enter",
        node="attempt_validation",
        application_id=state.get("application_id"),
        applicant_id=state.get("applicant_id"),
    )

    extracted_data = state.get("extracted_data", {})
    if not extracted_data:
        logger.warning(
            "no_extracted_data",
            application_id=state.get("application_id"),
        )
        return {
            "validation_results": {},
            "discrepancies": [],
            "messages": [AIMessage(content="No extracted data available for validation.")],
        }

    try:
        llm = _get_llm()
        tools = [
            per_document_validation_tool,
            cross_document_compare_tool,
            discrepancy_classify_tool,
            applicant_clarify_tool,
            validation_confidence_tool,
        ]

        agent = create_agent(llm, tools)

        validation_context = {
            "applicant_id": state.get("applicant_id"),
            "application_id": state.get("application_id"),
            "support_category": state.get("support_category"),
            "document_types": list(extracted_data.keys()),
            "extracted_data_summary": {
                doc_id: {"doc_type": doc_data.get("doc_type", "unknown")}
                for doc_id, doc_data in extracted_data.items()
            },
        }

        messages = [
            SystemMessage(content=VALIDATION_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Validate the following documents for application {state.get('application_id')}. "
                    f"Applicant context: {json.dumps(validation_context, default=str)}"
                )
            ),
        ]

        result = await agent.ainvoke({"messages": messages})

        final_message = result["messages"][-1].content if result["messages"] else ""

        try:
            validation_data = json.loads(final_message)
        except json.JSONDecodeError:
            validation_data = {
                "per_document_validation": {},
                "cross_document_validation": {},
                "raw_agent_output": True,
            }

        per_doc_validation = validation_data.get("per_document_validation", {})
        cross_doc_validation = validation_data.get("cross_document_validation", {})
        all_discrepancies = validation_data.get("discrepancies", [])

        validation_results = {
            "per_document_validation": per_doc_validation,
            "cross_document_validation": cross_doc_validation,
        }

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "attempt_validation_complete",
            application_id=state.get("application_id"),
            documents_validated=len(per_doc_validation),
            discrepancies_found=len(all_discrepancies),
            duration_ms=round(duration_ms, 2),
        )

        message_content = (
            f"Validation attempt complete. Validated {len(per_doc_validation)} documents. "
            f"Found {len(all_discrepancies)} discrepancies."
        )

        return {
            "validation_results": validation_results,
            "discrepancies": all_discrepancies,
            "messages": result["messages"],
        }

    except Exception as e:
        logger.exception(
            "attempt_validation_failed",
            application_id=state.get("application_id"),
            error=str(e),
        )
        return {
            "validation_results": {},
            "discrepancies": [],
            "messages": [AIMessage(content=f"Validation attempt failed: {str(e)}")],
        }


def evaluate_validation_node(state: ApplicantState) -> dict:
    """Evaluate node: Classify discrepancies as OCR errors or real inconsistencies.

    Uses discrepancy_classify_tool to judge each discrepancy based on
    extraction confidence and discrepancy characteristics.
    """
    start = time.perf_counter()
    logger.info(
        "node_enter",
        node="evaluate_validation",
        application_id=state.get("application_id"),
        discrepancy_count=len(state.get("discrepancies", [])),
    )

    discrepancies = state.get("discrepancies", [])
    extraction_confidence = state.get("extraction_confidence", {})

    classified_discrepancies = []
    for disc in discrepancies:
        if disc.get("classification") == "unclassified":
            classification_result = discrepancy_classify_tool.invoke({
                "discrepancy": disc,
                "extraction_confidence": extraction_confidence,
            })
            disc["classification"] = classification_result.get("classification", "ambiguous")
            disc["confidence"] = classification_result.get("confidence", 0.0)
            disc["reasoning"] = classification_result.get("reasoning", "")
            disc["recommended_action"] = classification_result.get("recommended_action", "manual_review")

        classified_discrepancies.append(disc)

    ocr_errors = [d for d in classified_discrepancies if d.get("classification") == "ocr_error"]
    real_discrepancies = [d for d in classified_discrepancies if d.get("classification") == "real_discrepancy"]
    ambiguous = [d for d in classified_discrepancies if d.get("classification") == "ambiguous"]

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "evaluate_validation_complete",
        application_id=state.get("application_id"),
        ocr_errors=len(ocr_errors),
        real_discrepancies=len(real_discrepancies),
        ambiguous=len(ambiguous),
        duration_ms=round(duration_ms, 2),
    )

    message_content = (
        f"Discrepancy evaluation complete. "
        f"OCR errors: {len(ocr_errors)}, Real discrepancies: {len(real_discrepancies)}, "
        f"Ambiguous: {len(ambiguous)}."
    )

    return {
        "discrepancies": classified_discrepancies,
        "messages": [AIMessage(content=message_content)],
    }


def critique_validation_node(state: ApplicantState) -> dict:
    """Critique node: Self-critique and decide if retry or clarification needed.

    Evaluates validation confidence and determines next action:
    - If confidence >= 0.80 and no critical discrepancies: proceed
    - If confidence < 0.80 or critical discrepancies: request clarification or escalate
    """
    start = time.perf_counter()
    logger.info(
        "node_enter",
        node="critique_validation",
        application_id=state.get("application_id"),
    )

    validation_results = state.get("validation_results", {})
    discrepancies = state.get("discrepancies", [])
    retry_count = state.get("retry_count", 0)

    unresolved_real = [
        d for d in discrepancies
        if d.get("classification") == "real_discrepancy"
        and d.get("resolution_status") == "unresolved"
    ]

    critical_discrepancies = [
        d for d in unresolved_real
        if d.get("discrepancy_type") in ["identity_mismatch", "income_mismatch"]
    ]

    needs_clarification = len(unresolved_real) > 0
    should_escalate = len(critical_discrepancies) > 0 and retry_count >= 2

    confidence_result = validation_confidence_tool.invoke({
        "validation_results": validation_results,
        "discrepancies": discrepancies,
    })

    overall_confidence = confidence_result.get("overall_confidence", 0.0)
    recommendation = confidence_result.get("recommendation", "escalate")

    if should_escalate:
        next_action = "escalate"
        critique_message = (
            f"Critical discrepancies remain unresolved after {retry_count} retries. "
            f"Escalating to manual review."
        )
    elif needs_clarification and retry_count < 2:
        next_action = "request_clarification"
        critique_message = (
            f"Found {len(unresolved_real)} unresolved discrepancies. "
            f"Requesting applicant clarification."
        )
    elif overall_confidence >= 0.80:
        next_action = "proceed"
        critique_message = (
            f"Validation confidence {overall_confidence:.2f} >= 0.80. "
            f"Proceeding to next phase."
        )
    else:
        next_action = "manual_review"
        critique_message = (
            f"Validation confidence {overall_confidence:.2f} < 0.80. "
            f"Recommending manual review."
        )

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "critique_validation_complete",
        application_id=state.get("application_id"),
        overall_confidence=round(overall_confidence, 2),
        next_action=next_action,
        unresolved_count=len(unresolved_real),
        retry_count=retry_count,
        duration_ms=round(duration_ms, 2),
    )

    return {
        "validation_results": {
            **validation_results,
            "overall_confidence": overall_confidence,
            "recommendation": recommendation,
        },
        "messages": [AIMessage(content=critique_message)],
        "_next_action": next_action,
    }


def generate_clarification_node(state: ApplicantState) -> dict:
    """Generate clarification questions for unresolved discrepancies.

    Uses applicant_clarify_tool to formulate questions for the applicant
    to resolve real discrepancies.
    """
    start = time.perf_counter()
    logger.info(
        "node_enter",
        node="generate_clarification",
        application_id=state.get("application_id"),
    )

    discrepancies = state.get("discrepancies", [])
    applicant_context = {
        "applicant_id": state.get("applicant_id"),
        "application_id": state.get("application_id"),
        "support_category": state.get("support_category"),
    }

    clarification_questions = []
    for disc in discrepancies:
        if (
            disc.get("classification") == "real_discrepancy"
            and disc.get("resolution_status") == "unresolved"
        ):
            question_result = applicant_clarify_tool.invoke({
                "discrepancy": disc,
                "applicant_context": applicant_context,
            })
            clarification_questions.append(question_result)
            disc["clarification_question"] = question_result.get("question")

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "generate_clarification_complete",
        application_id=state.get("application_id"),
        questions_generated=len(clarification_questions),
        duration_ms=round(duration_ms, 2),
    )

    message_content = (
        f"Generated {len(clarification_questions)} clarification questions for the applicant."
    )

    return {
        "discrepancies": discrepancies,
        "messages": [AIMessage(content=message_content)],
        "_clarification_questions": clarification_questions,
    }


def finalize_validation_node(state: ApplicantState) -> dict:
    """Finalize node: Compute final confidence and prepare validation results.

    Marks validation as complete and sets gate status based on results.
    """
    start = time.perf_counter()
    logger.info(
        "node_enter",
        node="finalize_validation",
        application_id=state.get("application_id"),
    )

    validation_results = state.get("validation_results", {})
    discrepancies = state.get("discrepancies", [])

    unresolved_count = sum(
        1 for d in discrepancies
        if d.get("resolution_status") == "unresolved"
    )

    overall_confidence = validation_results.get("overall_confidence", 0.0)

    if overall_confidence >= 0.80 and unresolved_count == 0:
        gate_status = "passed"
        gate_errors = []
    elif overall_confidence >= 0.70:
        gate_status = "passed"
        gate_errors = [f"Validation confidence {overall_confidence:.2f} is borderline"]
    else:
        gate_status = "failed"
        gate_errors = [f"Validation confidence {overall_confidence:.2f} < 0.70"]

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "finalize_validation_complete",
        application_id=state.get("application_id"),
        gate_status=gate_status,
        overall_confidence=round(overall_confidence, 2),
        unresolved_count=unresolved_count,
        duration_ms=round(duration_ms, 2),
    )

    message_content = (
        f"Validation finalized. Gate status: {gate_status}. "
        f"Confidence: {overall_confidence:.2f}. Unresolved discrepancies: {unresolved_count}."
    )

    return {
        "gate_status": gate_status,
        "gate_errors": gate_errors,
        "validation_results": {**validation_results, "overall_confidence": overall_confidence},
        "messages": [AIMessage(content=message_content)],
    }


def gate_2_completeness_node(state: ApplicantState) -> dict:
    """Gate 2: Deterministic completeness validation.

    Validates that all required documents are processed and identity
    information is consistent. No LLM calls.
    """
    start = time.perf_counter()
    logger.info(
        "node_enter",
        node="gate_2_completeness",
        application_id=state.get("application_id"),
    )

    extracted_data = state.get("extracted_data", {})
    validation_results = state.get("validation_results", {})
    support_category = state.get("support_category")

    required_documents = _get_required_documents(support_category)

    per_doc_validation = validation_results.get("per_document_validation", {})
    validation_results_by_type = {}
    for doc_id, result in per_doc_validation.items():
        if isinstance(result, dict):
            doc_type = result.get("document_type", "unknown")
            validation_results_by_type[doc_type] = {
                "is_valid": result.get("overall_status") == "valid",
                "errors": result.get("errors", []),
            }

    is_complete, missing_items = validate_completeness(
        validation_results_by_type,
        extracted_data,
        required_documents,
    )

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "gate_2_complete",
        application_id=state.get("application_id"),
        is_complete=is_complete,
        missing_count=len(missing_items),
        duration_ms=round(duration_ms, 2),
    )

    if is_complete:
        message_content = "Gate 2 passed: All required documents processed and identity consistent."
        gate_status = state.get("gate_status", "passed")
    else:
        message_content = f"Gate 2 failed: {len(missing_items)} completeness issues found."
        gate_status = "failed"

    return {
        "gate_status": gate_status,
        "gate_errors": state.get("gate_errors", []) + missing_items,
        "messages": [AIMessage(content=message_content)],
    }


def _get_required_documents(support_category: str | None) -> list[str]:
    """Get list of required documents for a support category."""
    if support_category is None:
        return DEFAULT_REQUIRED_DOCUMENTS
    return REQUIRED_DOCUMENTS.get(support_category.lower(), DEFAULT_REQUIRED_DOCUMENTS)
