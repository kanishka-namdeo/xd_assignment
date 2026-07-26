"""Extraction node functions and Gate 1 integration.

Implements the ReAct reasoning loop for document extraction using
LangGraph's create_react_agent pattern. Nodes handle:
1. Running the extraction agent with 6 tools
2. Gate 1 validation (document integrity)
3. Retry logic (max 2 retries on gate failure)
4. Structured logging with duration_ms
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import structlog
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, ValidationError

from src.agents.extraction.prompts import EXTRACTION_SYSTEM_PROMPT
from src.agents.extraction.tools import ALL_EXTRACTION_TOOLS
from src.agents.gates.document_integrity import validate_document_integrity
from src.agents.state import ApplicantState

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic model for structured extraction output
# ---------------------------------------------------------------------------

class ExtractionOutput(BaseModel):
    """Structured output from the extraction agent.

    This model validates and structures the JSON output from the ReAct agent,
    providing type safety and clear error messages when parsing fails.
    """

    document_type: str = Field(..., description="Type of document extracted")
    extraction_confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence score",
    )
    # Allow additional fields dynamically
    model_config = {"extra": "allow"}

# Maximum retries per document when gate fails
MAX_EXTRACTION_RETRIES = 2


# ---------------------------------------------------------------------------
# Helper: Build ReAct agent
# ---------------------------------------------------------------------------

def _build_extraction_agent(llm):
    """Create a ReAct agent with extraction tools bound.

    Args:
        llm: LangChain-compatible LLM instance (ChatOpenAI or similar).

    Returns:
        Compiled LangGraph agent with tools bound.
    """
    agent = create_react_agent(
        model=llm,
        tools=ALL_EXTRACTION_TOOLS,
        prompt=EXTRACTION_SYSTEM_PROMPT,
    )
    logger.info(
        "react_agent_built",
        tool_count=len(ALL_EXTRACTION_TOOLS),
        tools=[t.name for t in ALL_EXTRACTION_TOOLS],
    )
    return agent


# ---------------------------------------------------------------------------
# Node 1: Extract Documents (ReAct loop)
# ---------------------------------------------------------------------------

async def extract_documents_node(state: ApplicantState) -> dict[str, Any]:
    """Phase 3a: Extract data from uploaded documents using ReAct agent.

    For each uploaded document:
    1. Build a ReAct agent with 6 extraction tools
    2. Run agent to extract structured data
    3. Run Gate 1 (document integrity validation)
    4. Retry up to MAX_EXTRACTION_RETRIES if gate fails
    5. Store extracted data and confidence in state

    Args:
        state: Current applicant state with uploaded_documents list.

    Returns:
        State update dict with extracted_data, extraction_confidence,
        gate_status, gate_errors.
    """
    start = time.monotonic()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    uploaded_documents = state.get("uploaded_documents", [])

    logger.info(
        "node_enter",
        node="extract_documents",
        application_id=application_id,
        applicant_id=applicant_id,
        document_count=len(uploaded_documents),
    )

    if not uploaded_documents:
        logger.warning("no_documents_to_extract", application_id=application_id)
        return {
            "extracted_data": {},
            "extraction_confidence": {},
            "gate_status": "passed",
            "gate_errors": [],
        }

    # Get LLM client from injected services
    from src.agents.orchestrator.nodes import get_services, _get_llm_client

    llm_client = _get_llm_client()
    if llm_client is None:
        logger.error("llm_client_not_available", application_id=application_id)
        return {
            "extracted_data": {},
            "extraction_confidence": {},
            "gate_status": "failed",
            "gate_errors": ["LLM client not available for extraction agent"],
        }

    # Build ReAct agent
    try:
        # Convert LLMClient to LangChain-compatible format
        from langchain_openai import ChatOpenAI
        from src.config import settings

        if settings.LLM_PROVIDER == "streamlake":
            llm = ChatOpenAI(
                model=settings.STREAMLAKE_MODEL,
                base_url=settings.STREAMLAKE_BASE_URL,
                api_key=settings.STREAMLAKE_API_KEY.get_secret_value(),
                temperature=settings.LLM_TEMPERATURE,
            )
        else:
            llm = ChatOpenAI(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                api_key=settings.OLLAMA_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
            )

        agent = _build_extraction_agent(llm)
    except Exception as e:
        logger.exception("agent_build_failed", error=str(e), application_id=application_id)
        return {
            "extracted_data": {},
            "extraction_confidence": {},
            "gate_status": "failed",
            "gate_errors": [f"Failed to build extraction agent: {e}"],
        }

    # Process each document
    extracted_data: dict[str, Any] = {}
    extraction_confidence: dict[str, float] = {}
    all_gate_errors: list[str] = []
    gate_passed_all = True

    for doc_info in uploaded_documents:
        doc_id = doc_info.get("document_id", "unknown")
        doc_type = doc_info.get("document_type", "unknown")
        file_path = doc_info.get("file_path", "")

        logger.info(
            "document_extraction_start",
            document_id=doc_id,
            document_type=doc_type,
            file_path=file_path,
        )

        # Retry loop for gate validation
        attempt = 0
        doc_extracted = False
        doc_confidence = 0.0
        doc_errors: list[str] = []

        while attempt <= MAX_EXTRACTION_RETRIES:
            attempt_start = time.monotonic()

            try:
                # Build user message for the agent
                user_message = (
                    f"Extract structured data from this document:\n"
                    f"Document ID: {doc_id}\n"
                    f"Document Type: {doc_type}\n"
                    f"File Path: {file_path}\n\n"
                    f"Use the appropriate tools to extract all relevant fields. "
                    f"After extraction, compute confidence scores."
                )

                # Run ReAct agent
                messages = [HumanMessage(content=user_message)]
                result = await agent.ainvoke({"messages": messages})

                # Parse agent output
                agent_messages = result.get("messages", [])
                final_message = agent_messages[-1] if agent_messages else None

                # Extract structured data from agent response
                # The agent should return JSON in the final message
                extracted_fields = _parse_agent_output(final_message, doc_type)

                if not extracted_fields:
                    raise ValueError("Agent did not return valid extracted data")

                # Run Gate 1: Document Integrity
                gate_valid, gate_errors = validate_document_integrity(
                    extracted_fields, doc_type
                )

                attempt_duration = (time.monotonic() - attempt_start) * 1000
                logger.info(
                    "gate_validation",
                    document_id=doc_id,
                    attempt=attempt + 1,
                    gate_passed=gate_valid,
                    error_count=len(gate_errors),
                    duration_ms=round(attempt_duration, 2),
                )

                if gate_valid:
                    # Gate passed — store results
                    doc_extracted = True
                    doc_confidence = extracted_fields.get("extraction_confidence", 0.85)
                    extracted_data[doc_id] = extracted_fields
                    extraction_confidence[doc_id] = doc_confidence

                    logger.info(
                        "document_extracted",
                        document_id=doc_id,
                        document_type=doc_type,
                        confidence=round(doc_confidence, 4),
                        fields_extracted=len(extracted_fields),
                    )
                    break
                else:
                    # Gate failed — retry with error feedback
                    doc_errors = gate_errors
                    logger.warning(
                        "gate_failed_retrying",
                        document_id=doc_id,
                        attempt=attempt + 1,
                        max_retries=MAX_EXTRACTION_RETRIES + 1,
                        errors=gate_errors,
                    )
                    attempt += 1

            except Exception as e:
                attempt_duration = (time.monotonic() - attempt_start) * 1000
                logger.exception(
                    "extraction_attempt_failed",
                    document_id=doc_id,
                    attempt=attempt + 1,
                    error=str(e),
                    duration_ms=round(attempt_duration, 2),
                )
                doc_errors = [str(e)]
                attempt += 1

        # After retries exhausted
        if not doc_extracted:
            gate_passed_all = False
            all_gate_errors.extend(
                [f"Document {doc_id} ({doc_type}): {err}" for err in doc_errors]
            )
            logger.warning(
                "document_extraction_failed",
                document_id=doc_id,
                document_type=doc_type,
                total_attempts=attempt,
                errors=doc_errors,
            )

    # Final state update
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "node_exit",
        node="extract_documents",
        duration_ms=round(duration_ms, 2),
        documents_processed=len(uploaded_documents),
        documents_succeeded=len(extracted_data),
        documents_failed=len(uploaded_documents) - len(extracted_data),
        gate_status="passed" if gate_passed_all else "failed",
    )

    return {
        "extracted_data": extracted_data,
        "extraction_confidence": extraction_confidence,
        "gate_status": "passed" if gate_passed_all else "failed",
        "gate_errors": all_gate_errors,
    }


# ---------------------------------------------------------------------------
# Node 2: Summarize Extraction Results
# ---------------------------------------------------------------------------

def summarize_extraction_node(state: ApplicantState) -> dict[str, Any]:
    """Phase 3b: Summarize extraction results and prepare for validation.

    Logs extraction summary, checks gate status, and prepares state
    for downstream validation agent.

    Args:
        state: Current applicant state with extracted_data.

    Returns:
        State update dict with messages summarizing extraction.
    """
    start = time.monotonic()
    application_id = state.get("application_id")
    extracted_data = state.get("extracted_data", {})
    extraction_confidence = state.get("extraction_confidence", {})
    gate_status = state.get("gate_status", "unknown")
    gate_errors = state.get("gate_errors", [])

    logger.info(
        "node_enter",
        node="summarize_extraction",
        application_id=application_id,
        document_count=len(extracted_data),
        gate_status=gate_status,
    )

    # Build summary message
    if gate_status == "passed":
        avg_confidence = (
            sum(extraction_confidence.values()) / len(extraction_confidence)
            if extraction_confidence
            else 0.0
        )
        message = (
            f"Document extraction complete. Successfully extracted data from "
            f"{len(extracted_data)} document(s) with average confidence "
            f"{avg_confidence:.2%}. All documents passed integrity checks."
        )
    else:
        error_count = len(gate_errors)
        message = (
            f"Document extraction encountered issues. Extracted data from "
            f"{len(extracted_data)} document(s), but {error_count} integrity "
            f"check(s) failed. These issues will be reviewed in the next phase."
        )

    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "node_exit",
        node="summarize_extraction",
        duration_ms=round(duration_ms, 2),
        gate_status=gate_status,
    )

    return {
        "messages": [{"role": "assistant", "content": message}],
    }


# ---------------------------------------------------------------------------
# Helper: Parse agent output
# ---------------------------------------------------------------------------

def _extract_json_from_text(text: str) -> str | None:
    """Extract JSON block from text using regex.

    Tries multiple patterns to find JSON in agent output:
    1. JSON in markdown code blocks
    2. Raw JSON object
    3. JSON with surrounding text

    Args:
        text: Text content potentially containing JSON

    Returns:
        Extracted JSON string, or None if not found
    """
    # Pattern 1: JSON in markdown code blocks (```json ... ``` or ``` ... ```)
    code_block_pattern = r"```(?:json)?\s*\n([\s\S]*?)\n\s*```"
    match = re.search(code_block_pattern, text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Pattern 2: Raw JSON object (starts with { and ends with })
    json_pattern = r"\{[\s\S]*\}"
    match = re.search(json_pattern, text)
    if match:
        return match.group(0).strip()

    return None


def _parse_agent_output(message: BaseMessage | None, doc_type: str) -> dict[str, Any]:
    """Parse the final message from the ReAct agent into structured data.

    The agent should return JSON in the message content. This function:
    1. Extracts JSON from markdown code blocks or raw text
    2. Validates against ExtractionOutput Pydantic model
    3. Falls back to regex extraction if Pydantic validation fails
    4. Returns empty dict if all parsing fails

    Args:
        message: Final message from the agent (should contain JSON).
        doc_type: Document type for validation.

    Returns:
        Parsed extracted data dictionary, or empty dict if parsing fails.
    """
    if message is None:
        return {}

    content = message.content if hasattr(message, "content") else str(message)

    # Step 1: Extract JSON from text
    json_str = _extract_json_from_text(content)
    if not json_str:
        logger.warning(
            "agent_output_no_json_found",
            content_preview=content[:200] if content else "",
        )
        return {}

    # Step 2: Parse JSON
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(
            "agent_output_json_parse_failed",
            error=str(e),
            json_preview=json_str[:200],
        )
        # Step 3: Fallback - try regex extraction of key fields
        return _regex_fallback_extraction(content, doc_type)

    if not isinstance(parsed, dict):
        logger.warning("agent_output_not_dict", output_type=type(parsed).__name__)
        return {}

    # Step 4: Validate with Pydantic model
    try:
        # Add document_type if not present
        if "document_type" not in parsed:
            parsed["document_type"] = doc_type

        validated = ExtractionOutput(**parsed)
        return validated.model_dump()

    except ValidationError as e:
        logger.warning(
            "agent_output_pydantic_validation_failed",
            error=str(e),
            json_preview=json_str[:200],
        )
        # Return raw dict even if validation fails (better than empty)
        return parsed


def _regex_fallback_extraction(text: str, doc_type: str) -> dict[str, Any]:
    """Fallback extraction using regex patterns.

    Attempts to extract key fields using regex when JSON parsing fails.
    This is a last resort and produces lower confidence results.

    Args:
        text: Raw text content from agent
        doc_type: Document type for field-specific extraction

    Returns:
        Extracted data dictionary with low confidence, or empty dict
    """
    logger.info("regex_fallback_extraction", doc_type=doc_type)

    result: dict[str, Any] = {
        "document_type": doc_type,
        "extraction_confidence": 0.3,  # Low confidence for regex fallback
        "_extraction_method": "regex_fallback",
    }

    # Common patterns across document types
    patterns = {
        "identity_number": r"\b(784-\d{4}-\d{7}-\d)\b",
        "full_name": r"(?:Name|الاسم)[:\s]+([A-Za-z\s]+)",
        "date_of_birth": r"(?:DOB|Date of Birth|تاريخ الميلاد)[:\s]+(\d{4}-\d{2}-\d{2})",
        "nationality": r"(?:Nationality|الجنسية)[:\s]+([A-Za-z\s]+)",
        "gender": r"(?:Gender|الجنس)[:\s]+(Male|Female|ذكر|أنثى)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()

    # Only return result if we extracted at least one field
    if len(result) > 3:  # More than just document_type, confidence, method
        return result

    return {}
