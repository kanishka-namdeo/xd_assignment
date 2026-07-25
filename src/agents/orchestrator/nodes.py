"""7-phase node functions and gate nodes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.messages import BaseMessage

from src.agents.state import ApplicantState

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
        result = await llm.chat_completion(messages, model="kat-coder-pro-v2.5")
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


def intake_node(state: ApplicantState) -> ApplicantState:
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
    import asyncio as _asyncio
    system_prompt = (
        "You are a helpful and professional intake assistant for the UAE Social Support Application system. "
        "Your role is to collect basic information from applicants in a warm, clear manner. "
        "Keep responses concise and guide the applicant to the next step."
    )
    user_context = (
        f"Applicant message: {user_text or '(no message)'}\n"
        f"Current info: {applicant_info}\n"
        f"Support category detected: {support_category or 'none yet'}"
    )
    try:
        loop = _asyncio.get_event_loop()
        llm_response = loop.run_until_complete(
            _generate_llm_response(system_prompt, user_context, response)
        )
    except Exception:
        llm_response = response

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="intake", duration_ms=round(duration_ms, 2), next_phase=next_phase, support_category=support_category)

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": next_phase,
        "applicant_info": applicant_info,
    }


def document_collection_node(state: ApplicantState) -> ApplicantState:
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
    system_prompt = (
        "You are a helpful document collection assistant for the UAE Social Support Application system. "
        "Your role is to request and track required supporting documents from applicants. "
        "Be clear about which documents are needed and reassure applicants about the process. "
        "Keep responses concise."
    )
    user_context = (
        f"Support category: {support_category}\n"
        f"Required documents: {', '.join(required)}\n"
        f"Already uploaded: {len(uploaded_files) + len(uploaded_docs)} document(s)\n"
        f"User message: {last_message or '(no message)'}"
    )
    import asyncio as _asyncio2
    try:
        loop2 = _asyncio2.get_event_loop()
        llm_response = loop2.run_until_complete(
            _generate_llm_response(system_prompt, user_context, response)
        )
    except Exception:
        llm_response = response

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="document_collection", duration_ms=round(duration_ms, 2), next_phase=next_phase, uploaded_count=len(uploaded_files) + len(uploaded_docs), required_count=len(required))

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": next_phase,
    }


def processing_node(state: ApplicantState) -> ApplicantState:
    """Phase 3: Processing - call extraction and validation services.

    Calls ExtractionService.extract_all_documents() and
    ValidationService.validate_cross_document().
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

    # Try to use injected services if available
    services = get_services()
    extraction_service = services.get("extraction")
    validation_service = services.get("validation")

    extraction_results = []
    validation_results = {}
    discrepancies = []

    if extraction_service and applicant_id:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            extraction_results = loop.run_until_complete(
                extraction_service.extract_all_documents(applicant_id)
            )
            logger.info("extraction_complete", event="extraction_complete", document_count=len(extraction_results))
            if trace:
                trace.span(
                    name="document_extraction",
                    input={"applicant_id": applicant_id},
                    output={"documents_extracted": len(extraction_results)},
                )
        except Exception as e:
            extraction_results = [{"status": "failed", "error": str(e)}]
            logger.exception("extraction_failed", event="extraction_failed", error=str(e))
            if trace:
                trace.span(
                    name="document_extraction",
                    input={"applicant_id": applicant_id},
                    output={"error": str(e)},
                    level="ERROR",
                )

    if validation_service and applicant_id:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            validation_results = loop.run_until_complete(
                validation_service.validate_cross_document(applicant_id, support_category)
            )
            discrepancies = validation_results.get("discrepancies", [])
            logger.info("validation_complete", event="validation_complete", discrepancy_count=len(discrepancies))
            if trace:
                trace.span(
                    name="cross_document_validation",
                    input={"applicant_id": applicant_id, "support_category": support_category},
                    output={"discrepancies_found": len(discrepancies)},
                )
        except Exception as e:
            validation_results = {"status": "failed", "error": str(e)}
            logger.exception("validation_failed", event="validation_failed", error=str(e))
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


def review_node(state: ApplicantState) -> ApplicantState:
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

    # Try LLM-generated response with graceful fallback
    system_prompt = (
        "You are a professional review officer for the UAE Social Support Application system. "
        "Your role is to communicate cross-document validation results to applicants clearly and empathetically. "
        "If discrepancies exist, explain them plainly. If everything is consistent, reassure the applicant. "
        "Keep responses concise and professional."
    )
    discrepancy_count = len(discrepancies)
    user_context = (
        f"Validation result: {'discrepancies found' if discrepancies else 'all consistent'}\n"
        f"Number of discrepancies: {discrepancy_count}\n"
        f"Discrepancy details: {discrepancies[:2] if discrepancies else 'none'}"
    )
    import asyncio as _asyncio3
    try:
        loop3 = _asyncio3.get_event_loop()
        llm_response = loop3.run_until_complete(
            _generate_llm_response(system_prompt, user_context, response)
        )
    except Exception:
        llm_response = response

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="review", duration_ms=round(duration_ms, 2), discrepancy_count=len(discrepancies))

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": "decision",
    }


def decision_node(state: ApplicantState) -> ApplicantState:
    """Phase 5: Decision - compute eligibility and make decision.

    Calls EligibilityService.compute_eligibility() and
    DecisionService.make_decision().
    Generates decision message with explanation and decision value.
    Transitions to enablement.
    """
    start_ms = time.perf_counter()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    logger.info("node_enter", event="node_enter", node="decision", application_id=application_id, applicant_id=applicant_id)

    services = get_services()
    eligibility_service = services.get("eligibility")
    decision_service = services.get("decision")

    decision = "manual_review"
    decision_explanation = "Unable to compute eligibility - services not available."
    eligibility_score = 0.5

    if eligibility_service and application_id:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            eligibility_result = loop.run_until_complete(
                eligibility_service.compute_eligibility(application_id)
            )
            eligibility_score = eligibility_result.get("eligibility_score", 0.5)
            logger.info("eligibility_computed", event="eligibility_computed", score=eligibility_score)
        except Exception as e:
            eligibility_score = 0.5
            decision_explanation = f"Eligibility computation error: {e}"
            logger.exception("eligibility_failed", event="eligibility_failed", error=str(e))

    if decision_service and application_id:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            decision_result = loop.run_until_complete(
                decision_service.make_decision(application_id)
            )
            decision = decision_result.get("decision", "manual_review")
            decision_explanation = decision_result.get("explanation", decision_explanation)
            logger.info("decision_made", event="decision_made", decision=decision)
        except Exception as e:
            decision = "manual_review"
            decision_explanation = f"Decision error: {e}"
            logger.exception("decision_failed", event="decision_failed", error=str(e))
    elif eligibility_score >= 0.7:
        decision = "approved"
        decision_explanation = f"Application approved with eligibility score {eligibility_score:.0%}."
    elif eligibility_score >= 0.5:
        decision = "manual_review"
        decision_explanation = f"Application requires manual review. Score: {eligibility_score:.0%}."
    else:
        decision = "soft_decline"
        decision_explanation = f"Application declined with eligibility score {eligibility_score:.0%}."

    # Generate explanation text if services available
    if eligibility_service and application_id:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            explanation_text = loop.run_until_complete(
                eligibility_service.get_eligibility_explanation(application_id)
            )
            if explanation_text:
                decision_explanation = explanation_text
        except Exception:
            pass

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
    }


def enablement_node(state: ApplicantState) -> ApplicantState:
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

    # Try LLM-generated response with graceful fallback
    system_prompt = (
        "You are a compassionate case worker delivering the final decision and next steps "
        "for the UAE Social Support Application system. "
        "Communicate the decision clearly and outline concrete next steps. "
        "Be empathetic whether the outcome is approval, manual review, or decline. "
        "Keep responses concise and actionable."
    )
    user_context = (
        f"Decision: {decision}\n"
        f"Support category: {support_category}\n"
        f"Recommendations: {recommendation_text[:200]}"
    )
    import asyncio as _asyncio4
    try:
        loop4 = _asyncio4.get_event_loop()
        llm_response = loop4.run_until_complete(
            _generate_llm_response(system_prompt, user_context, response)
        )
    except Exception:
        llm_response = response

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info("node_exit", event="node_exit", node="enablement", duration_ms=round(duration_ms, 2), recommendation_count=len(recommendations), decision=decision)

    return {
        "messages": [_make_assistant_message(llm_response)],
        "current_phase": "enablement",
        "enablement_recommendations": recommendations,
    }
