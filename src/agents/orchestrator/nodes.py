"""7-phase node functions and gate nodes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.messages import BaseMessage

from src.agents.orchestrator.prompts import (
    DOCUMENT_COLLECTION_SYSTEM_PROMPT,
    ENABLEMENT_SYSTEM_PROMPT,
    INTAKE_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
)
from src.agents.state import ApplicantState
from src.config import settings

if TYPE_CHECKING:
    from src.infrastructure.llm.client import LLMClient
    from src.services.decision_service import DecisionService
    from src.services.eligibility_service import EligibilityService
    from src.services.extraction_service import ExtractionService
    from src.services.validation_service import ValidationService

logger = structlog.get_logger(__name__)

# Global service instances (injected at graph compilation time)
_services: dict[str, Any] = {}
_llm_client: "LLMClient | None" = None


def inject_services(
    extraction: ExtractionService | None = None,
    validation: ValidationService | None = None,
    eligibility: EligibilityService | None = None,
    decision: DecisionService | None = None,
) -> None:
    """Inject service instances for use by node functions.

    Call this before compiling the graph, or pass services via config.
    """
    global _services
    if extraction is not None:
        _services["extraction"] = extraction
    if validation is not None:
        _services["validation"] = validation
    if eligibility is not None:
        _services["eligibility"] = eligibility
    if decision is not None:
        _services["decision"] = decision
    logger.info("services_injected", event="services_injected", services=[k for k, v in _services.items() if v is not None])


def inject_llm_client(llm: "LLMClient | None") -> None:
    """Inject an LLMClient instance for conversational node responses."""
    global _llm_client
    _llm_client = llm
    logger.info("llm_client_injected", event="llm_client_injected", provider=llm.provider if llm else None)


def get_services() -> dict[str, Any]:
    """Get injected service instances."""
    return _services


def _get_llm_client() -> "LLMClient | None":
    """Get the injected LLM client instance."""
    return _llm_client


async def _generate_llm_response(
    system_prompt: str,
    user_context: str,
    fallback_response: str,
) -> str:
    """Generate an LLM response with graceful fallback.

    Calls the injected LLMClient if available; otherwise returns the fallback.
    On any LLM error, also falls back to the deterministic response.
    """
    llm = _get_llm_client()
    if llm is None:
        return fallback_response

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context},
        ]
        model = settings.STREAMLAKE_MODEL if settings.LLM_PROVIDER == "streamlake" else settings.OLLAMA_MODEL
        result = await llm.chat_completion(messages, model=model)
        content = result.get("content", "").strip()
        if content:
            return content
    except Exception as e:
        logger.warning("llm_node_fallback", node="unknown", error=str(e))

    return fallback_response


def _get_last_message_content(state: ApplicantState) -> str:
    """Extract text content from the last message, handling both dicts and Message objects."""
    messages = state.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, BaseMessage):
        return last.content
    if isinstance(last, dict):
        return last.get("content", "")
    return str(last)


def _make_assistant_message(content: str) -> dict:
    """Create an assistant message dict."""
    return {"role": "assistant", "content": content}


async def authentication_node(state: ApplicantState) -> ApplicantState:
    """Phase 0: Authentication - validate Emirates ID.

    Deterministic node that validates the Emirates ID identity number
    using the Luhn checksum. Transitions to intake on success,
    or escalates on failure.
    """
    start_ms = time.perf_counter()
    logger.info(
        "node_enter",
        event="node_enter",
        node="authentication",
        current_phase=state.get("current_phase"),
        applicant_id=state.get("applicant_id"),
    )

    last_message = _get_last_message_content(state)
    user_text = last_message.strip()

    identity_number = state.get("identity_number")

    if not identity_number and user_text:
        import re
        match = re.search(r"(\d{15})", user_text)
        if match:
            identity_number = match.group(1)

    if not identity_number:
        response = (
            "Welcome to the UAE Social Support Application system. "
            "Please provide your Emirates ID number (15 digits) to begin your application."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "node_exit",
            event="node_exit",
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
            event="node_exit",
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
            "The ID should be a 15-digit number."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.warning(
            "node_exit",
            event="node_exit",
            node="authentication",
            duration_ms=round(duration_ms, 2),
            next_phase="authentication",
            identity_verified=False,
        )
        return {
            "messages": [_make_assistant_message(response)],
            "current_phase": "authentication",
        }


async def intake_node(state: ApplicantState) -> ApplicantState:
    """Phase 1: Intake - collect basic applicant information.

    Parses user message for basic info, stores in state,
    generates conversational response asking for missing fields.
    Transitions to document_collection when support_category is provided.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", event="node_enter", node="intake", current_phase=state.get("current_phase"), applicant_id=state.get("applicant_id"))

    last_message = _get_last_message_content(state)
    user_text = last_message.strip()

    # Collect already gathered info from state
    applicant_info = state.get("applicant_info", {})
    discrepancies = state.get("discrepancies", [])

    # Try to extract support category from user input
    support_category = None
    if user_text:
        lower_text = user_text.lower()
        if "divorc" in lower_text:
            support_category = "divorced"
        elif "abandon" in lower_text:
            support_category = "abandoned"
        elif "unknown parentage" in lower_text or "orphan" in lower_text:
            support_category = "unknown_parentage"
        elif "disability" in lower_text or "health" in lower_text or "special needs" in lower_text:
            support_category = "health_disability"

    # Update applicant info from message
    if user_text and not applicant_info.get("full_name"):
        # Simple heuristic: first message is treated as name
        if len(user_text.split()) <= 4 and support_category is None:
            applicant_info["full_name"] = user_text.title()

    if support_category:
        applicant_info["support_category"] = support_category

    # Build response
    if support_category:
        response = (
            f"Thank you. I've noted that you're applying under the "
            f"'{support_category.replace('_', ' ').title()}' support category. "
            f"Now I'll need you to upload the required supporting documents. "
            f"Please upload your Emirates ID, bank statements, and other required documents."
        )
        next_phase = "document_collection"
    else:
        missing_fields = []
        if not applicant_info.get("full_name"):
            missing_fields.append("full name")

        if missing_fields:
            field_str = " and ".join(missing_fields)
            response = (
                f"Welcome to the UAE Social Support Application system. "
                f"To get started, please provide your {field_str}. "
                f"You can also tell me your support category (divorced, abandoned, "
                f"unknown parentage, or health/disability) to speed up the process."
            )
        else:
            response = (
                "Thank you for providing your information. "
                "Please tell me which support category you're applying under: "
                "divorced, abandoned, unknown parentage, or health/disability."
            )
        next_phase = "intake"

    # Try LLM-generated response with graceful fallback
    system_prompt = INTAKE_SYSTEM_PROMPT
    user_context = (
        f"Applicant message: {user_text or '(no message)'}\n"
        f"Current info: {applicant_info}\n"
        f"Support category detected: {support_category or 'none yet'}"
    )
    llm_response = await _generate_llm_response(system_prompt, user_context, response)

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="intake", duration_ms=round(duration_ms, 2), next_phase=next_phase, support_category=support_category)

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": next_phase,
        "applicant_info": applicant_info,
    }


async def document_collection_node(state: ApplicantState) -> ApplicantState:
    """Phase 2: Document Collection - track uploaded documents.

    Checks which documents are required based on support_category,
    generates message requesting missing documents,
    tracks uploaded documents in state.
    Transitions to processing after any upload (demo behavior).
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", event="node_enter", node="document_collection", current_phase=state.get("current_phase"), applicant_id=state.get("applicant_id"))

    last_message = _get_last_message_content(state)
    applicant_info = state.get("applicant_info", {})
    support_category = applicant_info.get("support_category", "")
    uploaded_docs = state.get("uploaded_documents", [])
    uploaded_files = state.get("uploaded_files", [])

    # Required documents per category
    required_map = {
        "divorced": ["Emirates ID", "Bank Statement", "Credit Report", "Application Form"],
        "abandoned": ["Emirates ID", "Bank Statement", "Credit Report", "Application Form"],
        "unknown_parentage": ["Emirates ID", "Bank Statement", "Application Form"],
        "health_disability": ["Emirates ID", "Bank Statement", "Credit Report", "Application Form", "Resume"],
    }
    required = required_map.get(support_category, ["Emirates ID", "Bank Statement", "Credit Report", "Application Form"])

    # Check if user uploaded files (demo: any message after intake counts)
    has_uploads = len(uploaded_files) > 0 or len(uploaded_docs) > 0

    # Also check if the message indicates an upload
    user_text = last_message.lower() if last_message else ""
    has_upload_indication = "upload" in user_text or "attached" in user_text or "document" in user_text

    if has_uploads or has_upload_indication:
        # Demo: transition to processing after any upload indication
        response = (
            f"Thank you. We have received your documents. "
            f"We will now process them to extract and validate the information. "
            f"This typically takes a few moments."
        )
        next_phase = "processing"
    else:
        # List required documents
        doc_list = ", ".join(required)
        response = (
            f"Thank you. Based on your '{support_category.replace('_', ' ').title()}' application, "
            f"we need the following documents: {doc_list}. "
            f"Please upload them now by attaching the files to your message."
        )
        next_phase = "document_collection"

    # Try LLM-generated response with graceful fallback
    system_prompt = DOCUMENT_COLLECTION_SYSTEM_PROMPT
    user_context = (
        f"Support category: {support_category}\n"
        f"Required documents: {', '.join(required)}\n"
        f"Already uploaded: {len(uploaded_files) + len(uploaded_docs)} document(s)\n"
        f"User message: {last_message or '(no message)'}"
    )
    llm_response = await _generate_llm_response(system_prompt, user_context, response)

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="document_collection", duration_ms=round(duration_ms, 2), next_phase=next_phase, uploaded_count=len(uploaded_files) + len(uploaded_docs), required_count=len(required))

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": next_phase,
    }


async def processing_node(state: ApplicantState) -> ApplicantState:
    """Phase 3: Processing - invoke extraction and validation agents.

    Invokes the extraction agent subgraph to extract data from documents,
    then invokes the validation agent subgraph to validate cross-document consistency.
    Generates processing status message.
    Transitions to review.
    """
    from src.infrastructure.observability import get_langfuse_client

    start_ms = time.perf_counter()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    logger.info("node_enter", event="node_enter", node="processing", application_id=application_id, applicant_id=applicant_id)

    # Create Langfuse trace for processing phase
    langfuse_client = get_langfuse_client()
    trace = None
    if langfuse_client:
        trace = langfuse_client.trace(
            name="processing_phase",
            session_id=application_id,
            user_id=applicant_id,
            tags=["processing", "document_extraction", "validation"],
            input={"application_id": application_id, "applicant_id": applicant_id},
        )

    applicant_info = state.get("applicant_info", {})
    support_category = applicant_info.get("support_category", "")

    # Invoke extraction agent subgraph
    extraction_results = []
    validation_results = {}
    discrepancies = []

    try:
        from src.agents.extraction.graph import get_extraction_subgraph

        extraction_graph = get_extraction_subgraph()
        config = {
            "configurable": {
                "thread_id": f"{application_id}_extraction",
            },
        }

        extraction_result = await extraction_graph.ainvoke(state, config=config)

        extraction_results = extraction_result.get("extraction_results", [])
        logger.info("extraction_agent_complete", event="extraction_agent_complete", document_count=len(extraction_results), gate_status=extraction_result.get("gate_status"))

        if trace:
            trace.span(
                name="document_extraction",
                input={"applicant_id": applicant_id},
                output={"documents_extracted": len(extraction_results)},
            )

        # Check if extraction passed gate
        if extraction_result.get("gate_status") == "failed":
            logger.warning("extraction_gate_failed", event="extraction_gate_failed", gate_errors=extraction_result.get("gate_errors"))
            state_update = {
                "extraction_results": extraction_results,
                "validation_results": {},
                "discrepancies": [],
                "messages": [_make_assistant_message(
                    "Document extraction encountered validation errors. "
                    "Please review your documents and try again."
                )],
                "current_phase": "review",
                "gate_status": "failed",
                "gate_errors": extraction_result.get("gate_errors", []),
            }
            return state_update

    except Exception as e:
        extraction_results = [{"status": "failed", "error": str(e)}]
        logger.exception("extraction_agent_failed", event="extraction_agent_failed", error=str(e))
        if trace:
            trace.span(
                name="document_extraction",
                input={"applicant_id": applicant_id},
                output={"error": str(e)},
                level="ERROR",
            )

    # Invoke validation agent subgraph
    try:
        from src.agents.validation.graph import run_validation_agent

        validation_state = {**state, "extraction_results": extraction_results}
        validation_result = await run_validation_agent(validation_state)

        validation_results = validation_result.get("validation_results", {})
        discrepancies = validation_result.get("discrepancies", [])
        logger.info("validation_agent_complete", event="validation_agent_complete", discrepancy_count=len(discrepancies), gate_status=validation_result.get("gate_status"))

        if trace:
            trace.span(
                name="cross_document_validation",
                input={"applicant_id": applicant_id, "support_category": support_category},
                output={"discrepancies_found": len(discrepancies)},
            )

    except Exception as e:
        validation_results = {"status": "failed", "error": str(e)}
        logger.exception("validation_agent_failed", event="validation_agent_failed", error=str(e))
        if trace:
            trace.span(
                name="cross_document_validation",
                input={"applicant_id": applicant_id, "support_category": support_category},
                output={"error": str(e)},
                level="ERROR",
            )

    # Store results in state for downstream nodes
    state_update: dict[str, Any] = {
        "extraction_results": extraction_results,
        "validation_results": validation_results,
        "discrepancies": discrepancies,
    }

    # Generate response
    if discrepancies:
        discrepancy_count = len(discrepancies)
        response = (
            f"Document processing is complete. "
            f"We extracted data from {len(extraction_results)} document(s). "
            f"However, we found {discrepancy_count} discrepancy(ies) that need attention. "
            f"Our team will review these during the next phase."
        )
    else:
        response = (
            f"Document processing is complete. "
            f"We successfully extracted and validated data from {len(extraction_results)} document(s). "
            f"All information is consistent across your documents. "
            f"Moving to the review phase."
        )

    state_update["messages"] = [_make_assistant_message(response)]
    state_update["current_phase"] = "review"

    if trace:
        trace.update(
            output={
                "documents_extracted": len(extraction_results),
                "discrepancies_found": len(discrepancies),
                "phase_transition": "review",
            }
        )

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="processing", duration_ms=round(duration_ms, 2), extraction_count=len(extraction_results), discrepancy_count=len(discrepancies))

    return state_update


async def review_node(state: ApplicantState) -> ApplicantState:
    """Phase 4: Review - check validation results and present findings.

    Checks validation results for discrepancies,
    generates message presenting findings.
    For demo, acknowledges and transitions to decision.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", event="node_enter", node="review", applicant_id=state.get("applicant_id"), discrepancy_count=len(state.get("discrepancies", [])))

    discrepancies = state.get("discrepancies", [])
    validation_results = state.get("validation_results", {})

    if discrepancies:
        discrepancy_messages = [d.get("message", d.get("type", "unknown")) for d in discrepancies[:3]]
        discrepancy_text = "; ".join(discrepancy_messages)
        response = (
            f"Review complete. We found the following discrepancies: {discrepancy_text}. "
            f"These will be flagged for manual review. "
            f"Proceeding to the decision phase."
        )
    else:
        findings = validation_results.get("findings", {})
        response = (
            "Review complete. All documents have been cross-checked and validated. "
            "Your information is consistent across all submitted documents. "
            "Proceeding to the decision phase."
        )

    discrepancy_count = len(discrepancies)
    system_prompt = REVIEW_SYSTEM_PROMPT
    user_context = (
        f"Validation result: {'discrepancies found' if discrepancies else 'all consistent'}\n"
        f"Number of discrepancies: {discrepancy_count}\n"
        f"Discrepancy details: {discrepancies[:2] if discrepancies else 'none'}"
    )
    llm_response = await _generate_llm_response(system_prompt, user_context, response)

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="review", duration_ms=round(duration_ms, 2), discrepancy_count=len(discrepancies))

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": "decision",
    }


async def decision_node(state: ApplicantState) -> ApplicantState:
    """Phase 5: Decision - invoke eligibility and decision agents.

    Invokes the eligibility agent subgraph to compute eligibility score,
    then invokes the decision agent subgraph to make final recommendation.
    Generates decision message with explanation and decision value.
    Transitions to enablement.
    """
    start_ms = time.perf_counter()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    logger.info("node_enter", event="node_enter", node="decision", application_id=application_id, applicant_id=applicant_id)

    decision = "manual_review"
    decision_explanation = "Unable to compute eligibility - agent invocation failed."
    eligibility_score = 0.5
    eligibility_factors = {}

    # Invoke eligibility agent subgraph
    try:
        from src.agents.eligibility.graph import get_eligibility_graph

        eligibility_graph = get_eligibility_graph()
        config = {
            "configurable": {
                "thread_id": f"{application_id}_eligibility",
            },
        }

        eligibility_result = await eligibility_graph.ainvoke(state, config=config)

        eligibility_score = eligibility_result.get("eligibility_score", 0.5)
        eligibility_factors = eligibility_result.get("eligibility_factors", {})
        logger.info("eligibility_agent_complete", event="eligibility_agent_complete", score=eligibility_score, gate_status=eligibility_result.get("gate_status"))

        # Check if eligibility passed gate
        if eligibility_result.get("gate_status") == "failed":
            logger.warning("eligibility_gate_failed", event="eligibility_gate_failed", gate_errors=eligibility_result.get("gate_errors"))
            decision = "soft_decline"
            decision_explanation = "Application does not meet hard eligibility requirements."
            return {
                "messages": [_make_assistant_message(
                    f"We have reached a decision on your application. "
                    f"Decision: {decision.replace('_', ' ').title()}. "
                    f"{decision_explanation}"
                )],
                "current_phase": "enablement",
                "decision": decision,
                "decision_explanation": decision_explanation,
                "eligibility_score": eligibility_score,
                "eligibility_factors": eligibility_factors,
                "gate_status": "failed",
                "gate_errors": eligibility_result.get("gate_errors", []),
            }

    except Exception as e:
        logger.exception("eligibility_agent_failed", event="eligibility_agent_failed", error=str(e))
        # Fall back to service-based eligibility
        services = get_services()
        eligibility_service = services.get("eligibility")
        if eligibility_service and application_id:
            try:
                eligibility_result = await eligibility_service.compute_eligibility(application_id)
                eligibility_score = eligibility_result.get("eligibility_score", 0.5)
                eligibility_factors = eligibility_result.get("factors", {})
                logger.info("eligibility_service_fallback", event="eligibility_service_fallback", score=eligibility_score)
            except Exception as e2:
                logger.exception("eligibility_service_fallback_failed", event="eligibility_service_fallback_failed", error=str(e2))

    # Invoke decision agent subgraph
    try:
        from src.agents.decision.graph import decision_agent

        decision_state = {
            **state,
            "eligibility_score": eligibility_score,
            "eligibility_factors": eligibility_factors,
        }
        config = {
            "configurable": {
                "thread_id": f"{application_id}_decision",
            },
        }

        decision_result = await decision_agent.ainvoke(decision_state, config=config)

        decision = decision_result.get("decision", "manual_review")
        decision_explanation = decision_result.get("decision_explanation", decision_explanation)
        logger.info("decision_agent_complete", event="decision_agent_complete", decision=decision)

    except Exception as e:
        logger.exception("decision_agent_failed", event="decision_agent_failed", error=str(e))
        # Fall back to service-based decision
        services = get_services()
        decision_service = services.get("decision")
        if decision_service and application_id:
            try:
                decision_result = await decision_service.make_decision(application_id)
                decision = decision_result.get("decision", "manual_review")
                decision_explanation = decision_result.get("explanation", decision_explanation)
                logger.info("decision_service_fallback", event="decision_service_fallback", decision=decision)
            except Exception as e2:
                logger.exception("decision_service_fallback_failed", event="decision_service_fallback_failed", error=str(e2))
        elif eligibility_score >= 0.7:
            decision = "approved"
            decision_explanation = f"Application approved with eligibility score {eligibility_score:.0%}."
        elif eligibility_score >= 0.5:
            decision = "manual_review"
            decision_explanation = f"Application requires manual review. Score: {eligibility_score:.0%}."
        else:
            decision = "soft_decline"
            decision_explanation = f"Application declined with eligibility score {eligibility_score:.0%}."

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="decision", duration_ms=round(duration_ms, 2), decision=decision, eligibility_score=eligibility_score)

    return {
        "messages": [_make_assistant_message(
            f"We have reached a decision on your application. "
            f"Decision: {decision.replace('_', ' ').title()}. "
            f"{decision_explanation}"
        )],
        "current_phase": "enablement",
        "decision": decision,
        "decision_explanation": decision_explanation,
        "eligibility_score": eligibility_score,
        "eligibility_factors": eligibility_factors,
    }


async def enablement_node(state: ApplicantState) -> ApplicantState:
    """Phase 6: Enablement - generate enablement recommendations.

    Generates enablement recommendations based on profile.
    Generates final message.
    Transitions to END.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", event="node_enter", node="enablement", applicant_id=state.get("applicant_id"), decision=state.get("decision"))

    decision = state.get("decision", "manual_review")
    applicant_info = state.get("applicant_info", {})
    support_category = applicant_info.get("support_category", "unknown")
    family_size = applicant_info.get("family_size", 1)

    recommendations = []

    if decision == "approved":
        recommendations = [
            "Your support benefits will be processed within 5-7 business days.",
            "A case worker will be assigned to your file and will contact you shortly.",
            "You will receive monthly support payments via bank transfer.",
            "Keep your documents up to date and report any changes in your situation.",
        ]
    elif decision == "manual_review":
        recommendations = [
            "Your application requires additional review by our team.",
            "Please ensure all your documents are complete and accurate.",
            "You may be contacted for additional information or clarification.",
            "Check your application status regularly for updates.",
        ]
    else:
        recommendations = [
            "Your application does not currently meet the eligibility criteria.",
            "You may reapply if your circumstances change.",
            "Consider contacting our support center for guidance on alternative programs.",
            "You can request a review of this decision within 30 days.",
        ]

    # Category-specific recommendations
    if support_category == "divorced":
        recommendations.append(
            "For divorced applicants: Ensure your divorce certificate is on file."
        )
    elif support_category == "health_disability":
        recommendations.append(
            "For health/disability applicants: Medical assessment may be required for benefit determination."
        )

    recommendation_text = " ".join(recommendations)

    response = (
        f"Your application process is complete. "
        f"Decision: {decision.replace('_', ' ').title()}. "
        f"Next steps: {recommendation_text}"
    )

    system_prompt = ENABLEMENT_SYSTEM_PROMPT
    user_context = (
        f"Decision: {decision}\n"
        f"Support category: {support_category}\n"
        f"Recommendations: {recommendation_text[:200]}"
    )
    llm_response = await _generate_llm_response(system_prompt, user_context, response)

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="enablement", duration_ms=round(duration_ms, 2), recommendation_count=len(recommendations), decision=decision)

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": "enablement",
        "enablement_recommendations": recommendations,
    }
