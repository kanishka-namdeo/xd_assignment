"""LangGraph agent execution wrapper."""

import time
from typing import Any

import structlog
from langgraph.types import Command
from src.agents.orchestrator.graph import build_orchestrator_graph
from src.agents.orchestrator.nodes import inject_llm_client
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.observability.langfuse_client import LangfuseClient
from src.services.extraction_pipeline import persist_results

logger = structlog.get_logger(__name__)


async def run(input_data: dict, langfuse_client: LangfuseClient | None = None) -> dict:
    """Run the orchestrator graph.

    On first invocation, runs the graph from the input state.
    On subsequent invocations with the same thread_id, resumes from checkpoint.
    If the graph paused at an interrupt(), returns the interrupt data.
    """
    start_ms = time.perf_counter()
    thread_id = input_data.get("application_id", "default")
    applicant_id = input_data.get("applicant_id")

    logger.info(
        "graph_invocation",
        thread_id=thread_id,
        applicant_id=applicant_id,
        current_phase=input_data.get("current_phase"),
        message_count=len(input_data.get("messages", [])),
        file_count=len(input_data.get("uploaded_files", [])),
    )

    callbacks = []
    if langfuse_client and langfuse_client.enabled:
        handler = langfuse_client.get_callback_handler()
        if handler:
            callbacks.append(handler)

    try:
        # Create and inject LLM client for conversational node responses
        llm_client = LLMClient()
        inject_llm_client(llm_client)

        graph = await build_orchestrator_graph()
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": thread_id,
                "recursion_limit": 50,
            },
            "callbacks": callbacks if callbacks else None,
            "metadata": {
                "langfuse_session_id": thread_id,
                "langfuse_user_id": applicant_id or "anonymous",
            },
        }

        # Use propagate_attributes for Langfuse trace attributes
        from langfuse import propagate_attributes

        with propagate_attributes(
            trace_name="orchestrator_graph",
            session_id=thread_id,
            user_id=applicant_id or "anonymous",
            tags=["langgraph", "orchestrator"],
        ):
            # Check if this is a resume invocation (user responded to an interrupt)
            # If input_data contains a "resume" key, use Command(resume=...)
            resume_payload = input_data.get("resume")
            if resume_payload is not None:
                # Resume from checkpoint with the user's response
                # Include state updates (e.g., uploaded_files) alongside the resume value
                state_update = {
                    "uploaded_files": input_data.get("uploaded_files", []),
                    "messages": input_data.get("messages", []),
                }
                logger.info(
                    "resuming_graph_with_command",
                    thread_id=thread_id,
                    resume_payload_type=type(resume_payload).__name__,
                    state_update_keys=list(state_update.keys()),
                    uploaded_files_count=len(state_update["uploaded_files"]),
                    uploaded_files=state_update["uploaded_files"],
                )
                result = await graph.ainvoke(
                    Command(resume=resume_payload, update=state_update),
                    config=config,
                )
            else:
                # Fresh invocation
                result = await graph.ainvoke(input_data, config=config)

        # Persist extraction/validation results to PostgreSQL, Qdrant, Neo4j
        # This is the service-layer persistence step — nodes only produce state updates.
        if result.get("extraction_results"):
            await persist_results(result)

        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "graph_complete",
            thread_id=thread_id,
            duration_ms=round(duration_ms, 2),
            result_phase=result.get("current_phase"),
            decision=result.get("decision"),
            has_interrupt=bool(result.get("__interrupt__")),
        )
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.exception(
            "graph_error",
            thread_id=thread_id,
            duration_ms=round(duration_ms, 2),
            error=str(e),
        )
        raise
