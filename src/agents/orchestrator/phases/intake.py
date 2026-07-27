"""Phase 1: Intake - collect basic applicant information via LLM parsing."""

from __future__ import annotations

import json
import re
import time

import structlog
from langgraph.types import interrupt

from src.agents.state import ApplicantState
from src.utils.state_size import check_state_size

logger = structlog.get_logger(__name__)

INTAKE_FIELDS = [
    "full_name", "date_of_birth", "nationality", "contact_phone", "contact_email",
    "address", "marital_status", "family_size", "employment_status", "employer_name",
    "occupation", "housing_status", "support_category",
]

FIELD_LABELS = {
    "full_name": "full name",
    "date_of_birth": "date of birth",
    "nationality": "nationality",
    "contact_phone": "contact phone number",
    "contact_email": "contact email",
    "address": "residential address",
    "marital_status": "marital status",
    "family_size": "family size",
    "employment_status": "employment status",
    "employer_name": "employer name",
    "occupation": "occupation",
    "housing_status": "housing status",
    "support_category": "support category (divorced, abandoned, unknown parentage, or health/disability)",
}


async def intake_node(state: ApplicantState) -> dict:
    """Phase 1: Intake - collect basic applicant information.

    Uses interrupt() to pause the graph when required fields are missing.
    When resumed via Command(resume=user_input), processes the user response
    and either loops back (more missing fields) or advances to document_collection.
    """
    start_ms = time.perf_counter()
    logger.info("node_enter", node="intake", current_phase=state.get("current_phase"), applicant_id=state.get("applicant_id"))

    # Check if we're resuming from an interrupt (user responded to a question)
    # The interrupt() call below will return the user's response when resumed
    applicant_info = dict(state.get("applicant_info", {}))

    # First, try to extract fields from the last user message
    last_message = state.get("messages", [])[-1] if state.get("messages") else ""
    if hasattr(last_message, "content"):
        user_text = last_message.content.strip()
    elif isinstance(last_message, dict):
        user_text = last_message.get("content", "").strip()
    else:
        user_text = str(last_message).strip()

    if user_text:
        fields_json = ", ".join(f'"{f}"' for f in INTAKE_FIELDS)
        extraction_prompt = (
            "You are an information extraction assistant. Extract any of the following fields "
            f"from the user's message: [{fields_json}]. "
            "Return ONLY a JSON object with the fields you found. "
            "Use these exact values for support_category: divorced, abandoned, unknown_parentage, health_disability. "
            "If no fields can be extracted, return an empty JSON object {}."
        )
        from src.agents.orchestrator.di import _generate_llm_response
        llm_json_str = await _generate_llm_response(extraction_prompt, user_text, "{}")

        try:
            # Try parsing the entire string as JSON first
            extracted = json.loads(llm_json_str.strip())
            for field in INTAKE_FIELDS:
                if field in extracted and extracted[field]:
                    applicant_info[field] = str(extracted[field]).strip()
            logger.debug("intake_llm_extraction", extracted_fields=[k for k in extracted if k in INTAKE_FIELDS])
        except json.JSONDecodeError:
            # Fallback: extract JSON object with balanced braces
            try:
                brace_count = 0
                start_idx = None
                for i, ch in enumerate(llm_json_str):
                    if ch == '{':
                        if brace_count == 0:
                            start_idx = i
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0 and start_idx is not None:
                            json_str = llm_json_str[start_idx:i+1]
                            extracted = json.loads(json_str)
                            for field in INTAKE_FIELDS:
                                if field in extracted and extracted[field]:
                                    applicant_info[field] = str(extracted[field]).strip()
                            logger.debug("intake_llm_extraction", extracted_fields=[k for k in extracted if k in INTAKE_FIELDS])
                            break
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning("intake_llm_parse_failed", error=str(e))
        
        # Regex-based fallback for any fields not extracted by LLM
        missing_after_llm = [f for f in INTAKE_FIELDS if not applicant_info.get(f)]
        if missing_after_llm:
            logger.info("intake_regex_fallback", missing_fields=missing_after_llm, user_text=user_text[:200])
            # Map field names to regex patterns
            field_patterns = {
                "full_name": r"(?:my\s+)?(?:name|full name)\s*(?:is|:)\s*([A-Za-z\s]+?)(?:\.|,|\n|$)",
                "date_of_birth": r"(?:date of birth|dob|birth date)\s*(?:is|:)\s*(\d{4}-\d{2}-\d{2})",
                "nationality": r"nationality\s*(?:is|:)\s*([A-Za-z]+?)(?:\.|,|\n|$)",
                "contact_phone": r"(?:phone|tel|telephone)\s*(?:is|:)\s*([+\d\s\-()]+?)(?:\.|,|\n|$)",
                "contact_email": r"email\s*(?:is|:)\s*([\w\.-]+@[\w\.-]+?\.\w+)",
                "address": r"address\s*(?:is|:)\s*([^\n\.]+?)(?:\.|\n|$)",
                "marital_status": r"marital status\s*(?:is|:)\s*(single|married|divorced|widowed|separated)",
                "family_size": r"family size\s*(?:is|:)\s*(\d+)",
                "employment_status": r"employment status\s*(?:is|:)\s*(employed|self-employed|unemployed|retired|student)",
                "employer_name": r"employer\s*(?:name)?\s*(?:is|:)\s*([A-Za-z\s]+?)(?:\.|,|\n|$)",
                "occupation": r"occupation\s*(?:is|:)\s*([A-Za-z\s]+?)(?:\.|,|\n|$)",
                "housing_status": r"housing status\s*(?:is|:)\s*(rented|owned|family|mortgage)",
                "support_category": r"support category\s*(?:is|:)\s*(divorced|abandoned|unknown_parentage|health_disability)",
            }
            
            for field in missing_after_llm:
                if field in field_patterns:
                    pattern = field_patterns[field]
                    match = re.search(pattern, user_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        if value:
                            applicant_info[field] = value
                            logger.info("intake_regex_extracted", field=field, value=value)
                    else:
                        logger.debug("intake_regex_no_match", field=field, pattern=pattern)

    missing_fields = [f for f in INTAKE_FIELDS if not applicant_info.get(f)]
    support_category = applicant_info.get("support_category")

    # If all fields collected and support_category is set, advance to document_collection
    if support_category:
        category_display = support_category.replace("_", " ").title()
        response = (
            f"Thank you. I've noted that you're applying under the "
            f"'{category_display}' support category. "
            f"Now I'll need you to upload the required supporting documents. "
            f"Please upload your Emirates ID, bank statements, and other required documents."
        )
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "node_exit", node="intake", duration_ms=round(duration_ms, 2),
            next_phase="document_collection", support_category=support_category,
            fields_collected=len(INTAKE_FIELDS), fields_missing=0,
        )
        result = {
            "messages": [{"role": "assistant", "content": response}],
            "current_phase": "document_collection",
            "applicant_info": applicant_info,
            "support_category": applicant_info.get("support_category"),
        }
        check_state_size(state, node_name="intake", application_id=state.get("application_id"))
        return result

    # Missing fields - use interrupt() to pause and ask the user
    next_missing = missing_fields[:3]
    field_descriptions = [FIELD_LABELS.get(f, f) for f in next_missing]
    field_str = ", ".join(field_descriptions)

    # interrupt() pauses the graph and returns user response when resumed
    user_response = interrupt({
        "question": f"To continue, please provide your {field_str}.",
        "field": field_str,
        "phase": "intake",
        "missing_fields": missing_fields,
    })

    # When resumed, process the user response as a new message
    if user_response and isinstance(user_response, str):
        for field in missing_fields:
            field_lower = field.lower()
            if field_lower in user_response.lower():
                # Try to extract the value from the response
                # Simple heuristic: look for the field name and take what follows
                idx = user_response.lower().find(field_lower)
                if idx >= 0:
                    # Take text after the field mention, up to next punctuation
                    after = user_response[idx + len(field):].strip()
                    value = after.split(",")[0].split(".")[0].split(";")[0].strip()
                    if value:
                        applicant_info[field] = value

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info(
        "node_exit", node="intake", duration_ms=round(duration_ms, 2),
        next_phase="intake", support_category=support_category,
        fields_collected=len(INTAKE_FIELDS) - len(missing_fields), fields_missing=len(missing_fields),
    )

    result = {
        "messages": [{"role": "assistant", "content": f"Thank you for the information. To continue, please provide your {field_str}."}],
        "current_phase": "intake",
        "applicant_info": applicant_info,
    }
    check_state_size(state, node_name="intake", application_id=state.get("application_id"))
    return result
