"""Extraction agent construction and per-document processing."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
import structlog

from src.agents.extraction.parsers import _parse_agent_output as parse_agent_output
from src.agents.extraction.prompts import EXTRACTION_SYSTEM_PROMPT
from src.agents.extraction.tools import ALL_EXTRACTION_TOOLS
from src.agents.gates.document_integrity import validate_document_integrity
from src.config import settings

logger = structlog.get_logger(__name__)

MAX_EXTRACTION_RETRIES = 2


def build_extraction_agent(llm):
    """Create a ReAct agent with extraction tools bound."""
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


def build_llm_from_settings():
    """Build a LangChain LLM client from project settings."""
    from langchain_openai import ChatOpenAI

    if settings.LLM_PROVIDER == "streamlake":
        return ChatOpenAI(
            model=settings.STREAMLAKE_MODEL,
            base_url=settings.STREAMLAKE_BASE_URL,
            api_key=settings.STREAMLAKE_API_KEY.get_secret_value(),
            temperature=settings.LLM_TEMPERATURE,
        )
    return ChatOpenAI(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        api_key=settings.OLLAMA_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
    )


async def process_single_document(
    agent,
    doc_id: str,
    doc_type: str,
    file_path: str,
) -> tuple[bool, dict | None, float, list[str]]:
    """Run the ReAct agent for one document with retry on gate failure.

    Returns:
        (success, extracted_fields, confidence, errors)
    """
    attempt = 0
    doc_errors: list[str] = []

    while attempt <= MAX_EXTRACTION_RETRIES:
        attempt_start = time.monotonic()

        try:
            user_message = (
                f"Extract structured data from this document:\n"
                f"Document ID: {doc_id}\n"
                f"Document Type: {doc_type}\n"
                f"File Path: {file_path}\n\n"
                f"Use the appropriate tools to extract all relevant fields. "
                f"After extraction, compute confidence scores."
            )

            messages = [HumanMessage(content=user_message)]
            result = await agent.ainvoke({"messages": messages})

            agent_messages = result.get("messages", [])
            final_message = agent_messages[-1] if agent_messages else None

            extracted_fields = parse_agent_output(final_message, doc_type)

            if not extracted_fields:
                raise ValueError("Agent did not return valid extracted data")

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
                doc_confidence = extracted_fields.get("extraction_confidence", 0.85)
                logger.info(
                    "document_extracted",
                    document_id=doc_id,
                    document_type=doc_type,
                    confidence=round(doc_confidence, 4),
                    fields_extracted=len(extracted_fields),
                )
                return True, extracted_fields, doc_confidence, []

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

    return False, None, 0.0, doc_errors
