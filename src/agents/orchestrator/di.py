"""Dependency injection for orchestrator node functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

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
    extraction: "ExtractionService | None" = None,
    validation: "ValidationService | None" = None,
    eligibility: "EligibilityService | None" = None,
    decision: "DecisionService | None" = None,
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
    logger.info("services_injected", services=[k for k, v in _services.items() if v is not None])


def inject_llm_client(llm: "LLMClient | None") -> None:
    """Inject an LLMClient instance for conversational node responses."""
    global _llm_client
    _llm_client = llm
    logger.info("llm_client_injected", provider=llm.provider if llm else None)


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


def _get_last_message_content(state: dict) -> str:
    """Extract text content from the last message, handling both dicts and Message objects."""
    from langchain_core.messages import BaseMessage

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
