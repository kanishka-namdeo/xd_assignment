"""LangGraph agent execution wrapper."""

import time

import structlog
from src.agents.orchestrator.graph import build_orchestrator_graph

logger = structlog.get_logger(__name__)


async def run(input_data: dict) -> dict:
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

    try:
        graph = build_orchestrator_graph()
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
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
