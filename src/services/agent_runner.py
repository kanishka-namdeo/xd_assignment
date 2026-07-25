"""LangGraph agent execution wrapper."""

import time

import structlog
from src.agents.orchestrator.graph import build_orchestrator_graph
from src.agents.orchestrator.nodes import inject_llm_client
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.observability.langfuse_client import LangfuseClient

logger = structlog.get_logger(__name__)


async def run(input_data: dict, langfuse_client: LangfuseClient | None = None) -> dict:
    start_ms = time.perf_counter()
    thread_id = input_data.get("application_id", "default")
    applicant_id = input_data.get("applicant_id")

    logger.info(
        "graph_invocation",
        event="graph_invocation",
        thread_id=thread_id,
        applicant_id=applicant_id,
        current_phase=input_data.get("current_phase"),
        message_count=len(input_data.get("messages", [])),
        file_count=len(input_data.get("uploaded_files", [])),
    )

    callbacks = []
    if langfuse_client and langfuse_client.enabled:
        handler = langfuse_client.get_callback_handler(
            trace_name="orchestrator_graph",
            session_id=thread_id,
            user_id=applicant_id or "anonymous",
            tags=["langgraph", "orchestrator"],
        )
        if handler:
            callbacks.append(handler)

    try:
        # Create and inject LLM client for conversational node responses
        llm_client = LLMClient()
        inject_llm_client(llm_client)

        graph = build_orchestrator_graph()
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "callbacks": callbacks if callbacks else None,
        }
        result = await graph.ainvoke(input_data, config=config)

        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "graph_complete",
            event="graph_complete",
            thread_id=thread_id,
            duration_ms=round(duration_ms, 2),
            result_phase=result.get("current_phase"),
            decision=result.get("decision"),
        )
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.exception(
            "graph_error",
            event="graph_error",
            thread_id=thread_id,
            duration_ms=round(duration_ms, 2),
            error=str(e),
        )
        raise
