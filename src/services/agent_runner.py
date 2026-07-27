"""LangGraph agent execution wrapper."""

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from langgraph.types import Command
from src.agents.orchestrator.graph import build_orchestrator_graph
from src.agents.orchestrator.nodes import inject_llm_client
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.observability.langfuse_client import LangfuseClient
from src.services.extraction_pipeline import persist_results

logger = structlog.get_logger(__name__)

# Node names that represent key milestones in the orchestrator graph.
_KEY_EVENTS: dict[str, str] = {
    "extraction_results": "extraction_complete",
    "validation_results": "validation_complete",
    "decision": "decision_reached",
    "eligibility_score": "eligibility_scored",
}


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


async def run_streaming(
    input_data: dict, langfuse_client: LangfuseClient | None = None
) -> AsyncIterator[dict[str, Any]]:
    """Run the orchestrator graph with streaming support.

    Yields phase transitions and key events as they occur during graph execution.
    Uses LangGraph's astream() method instead of ainvoke() for real-time feedback.

    Yields:
        dict with event structure:
        - type: "phase_transition" | "extraction_complete" | "validation_complete" |
                "decision_reached" | "eligibility_scored" | "interrupt" | "complete"
        - phase: (for phase_transition) the new phase name
        - document_count: (for extraction_complete) number of documents processed
        - confidence: (for validation_complete) validation confidence score
        - decision: (for decision_reached) the decision string
        - score: (for eligibility_scored) the eligibility score
        - interrupt_data: (for interrupt) the interrupt payload
        - timestamp: Unix timestamp of the event
        - duration_ms: (for complete) total streaming duration
    """
    start_ms = time.perf_counter()
    thread_id = input_data.get("application_id", "default")
    applicant_id = input_data.get("applicant_id")
    last_phase = input_data.get("current_phase")

    logger.info(
        "graph_streaming_invocation",
        thread_id=thread_id,
        applicant_id=applicant_id,
        current_phase=input_data.get("current_phase"),
        message_count=len(input_data.get("messages", [])),
        file_count=len(input_data.get("uploaded_files", [])),
    )

    callbacks: list[Any] = []
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
            trace_name="orchestrator_graph_streaming",
            session_id=thread_id,
            user_id=applicant_id or "anonymous",
            tags=["langgraph", "orchestrator", "streaming"],
        ):
            # Check if this is a resume invocation (user responded to an interrupt)
            resume_payload = input_data.get("resume")
            if resume_payload is not None:
                # Resume from checkpoint with the user's response
                state_update = {
                    "uploaded_files": input_data.get("uploaded_files", []),
                    "messages": input_data.get("messages", []),
                }
                logger.info(
                    "resuming_graph_streaming_with_command",
                    thread_id=thread_id,
                    resume_payload_type=type(resume_payload).__name__,
                    state_update_keys=list(state_update.keys()),
                    uploaded_files_count=len(state_update["uploaded_files"]),
                )
                async for event in graph.astream(
                    Command(resume=resume_payload, update=state_update),
                    config=config,
                ):
                    # Process streaming events
                    async for yielded in _process_stream_event(event, last_phase, start_ms, thread_id):
                        yield yielded
                        # Track phase for subsequent events
                        if yielded.get("type") == "phase_transition":
                            last_phase = yielded.get("phase")
            else:
                # Fresh invocation with streaming
                async for event in graph.astream(input_data, config=config):
                    # Process streaming events
                    async for yielded in _process_stream_event(event, last_phase, start_ms, thread_id):
                        yield yielded
                        # Track phase for subsequent events
                        if yielded.get("type") == "phase_transition":
                            last_phase = yielded.get("phase")

        # Final completion event
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.info(
            "graph_streaming_complete",
            thread_id=thread_id,
            duration_ms=round(duration_ms, 2),
        )
        yield {
            "type": "complete",
            "timestamp": time.time(),
            "duration_ms": round(duration_ms, 2),
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start_ms) * 1000
        logger.exception(
            "graph_streaming_error",
            thread_id=thread_id,
            duration_ms=round(duration_ms, 2),
            error=str(e),
        )
        raise


async def _process_stream_event(
    event: dict[str, Any],
    last_phase: str | None,
    start_ms: float,
    thread_id: str,
) -> AsyncIterator[dict[str, Any]]:
    """Process a single streaming event from the graph.

    Extracts phase transitions and key events from the event payload.
    """
    # LangGraph astream() yields events in the form: {node_name: state_update}
    # The state_update contains the fields that changed in that node
    for node_name, state_update in event.items():
        if not isinstance(state_update, dict):
            continue

        # Check for phase transitions
        new_phase = state_update.get("current_phase")
        if new_phase and new_phase != last_phase:
            duration_ms = (time.perf_counter() - start_ms) * 1000
            logger.info(
                "streaming_phase_transition",
                thread_id=thread_id,
                phase=new_phase,
                duration_ms=round(duration_ms, 2),
            )
            yield {
                "type": "phase_transition",
                "phase": new_phase,
                "timestamp": time.time(),
                "duration_ms": round(duration_ms, 2),
            }

        # Check for key events (extraction, validation, decision, eligibility)
        for state_key, event_type in _KEY_EVENTS.items():
            if state_key in state_update and state_update[state_key] is not None:
                duration_ms = (time.perf_counter() - start_ms) * 1000
                event_data: dict[str, Any] = {
                    "type": event_type,
                    "timestamp": time.time(),
                    "duration_ms": round(duration_ms, 2),
                }

                # Add event-specific metadata
                if state_key == "extraction_results":
                    event_data["document_count"] = len(state_update[state_key])
                elif state_key == "validation_results":
                    event_data["confidence"] = state_update.get("validation_confidence")
                elif state_key == "decision":
                    event_data["decision"] = state_update[state_key]
                elif state_key == "eligibility_score":
                    event_data["score"] = state_update[state_key]

                logger.info(
                    "streaming_key_event",
                    event_type=event_type,
                    thread_id=thread_id,
                    duration_ms=round(duration_ms, 2),
                    **{k: v for k, v in event_data.items() if k not in ("type", "timestamp", "duration_ms")},
                )
                yield event_data

        # Check for interrupts
        if "__interrupt__" in state_update:
            duration_ms = (time.perf_counter() - start_ms) * 1000
            logger.info(
                "streaming_interrupt",
                thread_id=thread_id,
                duration_ms=round(duration_ms, 2),
            )
            yield {
                "type": "interrupt",
                "interrupt_data": state_update["__interrupt__"],
                "timestamp": time.time(),
                "duration_ms": round(duration_ms, 2),
            }
