"""Chat and conversation endpoints."""

from collections.abc import AsyncGenerator
from pathlib import Path
import time
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from src.agents.decision.tools import decision_formatting_tool
from src.api.deps import AsyncDB
from src.domain.schemas.chat import ChatRequest, ChatResponse, InterruptData, UploadedDocument
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.observability.langfuse_client import LangfuseClient
from src.services.agent_runner import run as run_orchestrator
from src.services.decision_service import DecisionService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])

UPLOAD_DIR = Path("data/uploads")


@router.get("/health/llm")
async def health_llm() -> dict:
    """Verify LLM connectivity with a live request.

    Returns provider, model, latency, and token usage from a ping call.
    """
    llm = LLMClient()
    start_ms = time.perf_counter()

    try:
        result = await llm.chat_completion(
            messages=[{"role": "user", "content": "Respond with the single word: pong"}],
            model="kat-coder-pro-v2.5",
            max_tokens=10,
        )
        latency = result.get("latency_ms", round((time.perf_counter() - start_ms) * 1000, 1))
        return {
            "status": "healthy",
            "provider": llm.provider,
            "model": result.get("model", llm.model),
            "latency_ms": latency,
            "tokens": result.get("usage", {}).get("total_tokens", 0),
        }
    except Exception as e:
        latency = round((time.perf_counter() - start_ms) * 1000, 1)
        logger.exception("health_llm_failed", error=str(e))
        return {
            "status": "unhealthy",
            "provider": llm.provider,
            "model": llm.model,
            "latency_ms": latency,
            "error": str(e),
        }


@router.post(
    "/applications/{application_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    application_id: str,
    db: AsyncDB,
    fastapi_request: Request,
    text: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> ChatResponse:
    logger.info("request_received", application_id=application_id, endpoint="chat")

    application_repo = ApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)

    if application is None:
        logger.warning("request_failed", application_id=application_id, detail="Application not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    previous_phase = application.current_phase

    langfuse_client: LangfuseClient | None = getattr(fastapi_request.app.state, "langfuse", None)

    # Save uploaded files to disk and collect their paths
    file_paths: list[str] = []
    if files:
        upload_dir = UPLOAD_DIR / application_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        for upload in files:
            if upload.filename is None:
                continue
            dest = upload_dir / upload.filename
            content = await upload.read()
            dest.write_bytes(content)
            file_paths.append(str(dest))
            logger.info("file_saved", application_id=application_id, filename=upload.filename, size_bytes=len(content))

    # Load persisted state from previous turns
    previous_state = await application_repo.get_state(application.id)

    # Build input: start from previous state (if any), overlay new turn input
    graph_input: dict[str, Any] = dict(previous_state) if previous_state else {}

    # Check if the previous turn resulted in an interrupt (graph paused waiting for user)
    # If so, resume with the user's text as the resume payload
    had_pending_interrupt = previous_state and previous_state.get("_pending_interrupt")

    if had_pending_interrupt:
        # Resume the graph with the user's response
        graph_input["resume"] = text
        # Don't add a new user message - the interrupt resume handles it
        graph_input["messages"] = previous_state.get("messages", [])
    else:
        # Fresh invocation with new user message
        graph_input["messages"] = [{"role": "user", "content": text}]

    graph_input["current_phase"] = application.current_phase
    graph_input["applicant_id"] = str(application.applicant_id)
    graph_input["application_id"] = str(application.id)
    graph_input["uploaded_files"] = file_paths

    try:
        result = await run_orchestrator(
            graph_input,
            langfuse_client=langfuse_client,
        )
    except Exception as e:
        logger.exception("request_failed", application_id=application_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing error: {str(e)}",
        )

    # Check if the graph paused at an interrupt point
    interrupt_data = None
    if result.get("__interrupt__"):
        interrupt_value = result["__interrupt__"][0].value if isinstance(result["__interrupt__"], list) else result["__interrupt__"].value
        if isinstance(interrupt_value, dict):
            interrupt_data = InterruptData(
                question=interrupt_value.get("question", ""),
                phase=interrupt_value.get("phase", ""),
                missing_fields=interrupt_value.get("missing_fields"),
                missing_documents=interrupt_value.get("missing_documents"),
                discrepancies=interrupt_value.get("discrepancies"),
                recommendations=interrupt_value.get("recommendations"),
            )
        # Mark that we have a pending interrupt for the next turn
        result["_pending_interrupt"] = True
    else:
        # Clear the pending interrupt flag
        result["_pending_interrupt"] = False

    # Persist full state snapshot for next turn
    await application_repo.save_state(application.id, result)

    # Persist decision to DB if the orchestrator reached a decision
    if result.get("decision") and application_id:
        try:
            decision_svc = DecisionService(db)
            await decision_svc.persist_decision(
                application_id=UUID(application_id),
                decision=result["decision"],
                decision_explanation=result.get("decision_explanation", ""),
                eligibility_score=result.get("eligibility_score", 0.0),
                eligibility_factors=result.get("eligibility_factors"),
            )
        except Exception as e:
            logger.exception("decision_persist_failed", application_id=application_id, error=str(e))

    new_phase = result.get("current_phase", application.current_phase)
    application.current_phase = new_phase
    await application_repo.update(application)

    uploaded_documents = [
        UploadedDocument(
            doc_type=doc.get("doc_type", "unknown"),
            file_path=doc.get("file_path", ""),
            status=doc.get("status", "uploaded"),
        )
        for doc in result.get("uploaded_documents", [])
    ]

    if new_phase != previous_phase:
        logger.info("phase_transition", application_id=application_id, from_phase=previous_phase, to_phase=new_phase)

    logger.info("response_sent", application_id=application_id, phase=new_phase, document_count=len(uploaded_documents))

    formatted_card = None
    if result.get("decision"):
        try:
            formatted_card = decision_formatting_tool.invoke({
                "decision": result["decision"],
                "explanation": result.get("decision_explanation", ""),
                "enablement_recommendations": {"recommendations": result.get("enablement_recommendations", [])},
                "applicant_context": {
                    "support_category": result.get("applicant_info", {}).get("support_category", "unknown"),
                    "family_size": result.get("applicant_info", {}).get("family_size", 1),
                },
            })
        except Exception as e:
            logger.warning("decision_formatting_failed", application_id=application_id, error=str(e))

    # Get the message content
    messages = result.get("messages", [])
    message_content = ""
    if messages:
        last_msg = messages[-1]
        message_content = last_msg.content if hasattr(last_msg, "content") else last_msg.get("content", "")

    return ChatResponse(
        message=message_content,
        phase=new_phase,
        uploaded_documents=uploaded_documents,
        decision=result.get("decision"),
        decision_card=formatted_card,
        interrupt=interrupt_data,
    )


async def _stream_generator(
    application_id: str,
    text: str,
    current_phase: str,
    applicant_id: str,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted deltas from the LLM stream."""
    llm = LLMClient()
    messages = [
        {"role": "system", "content": "You are a helpful assistant for the UAE Social Support Application system. Respond clearly and concisely."},
        {"role": "user", "content": text},
    ]

    try:
        async for delta in llm.stream_completion(messages, model="kat-coder-pro-v2.5"):
            yield f"data: {delta}\n\n"
    except Exception as e:
        logger.exception("stream_error", application_id=application_id, error=str(e))
        yield f"data: [ERROR] {str(e)}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/applications/{application_id}/chat/stream")
async def chat_stream(
    application_id: str,
    request: ChatRequest,
    db: AsyncDB,
) -> StreamingResponse:
    """Stream chat responses as server-sent events.

    Yields text deltas from the LLM in SSE format (data: <delta>\\n\\n).
    Ends with data: [DONE]\\n\\n.
    """
    logger.info("request_received", application_id=application_id, endpoint="chat_stream")

    application_repo = ApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return StreamingResponse(
        _stream_generator(
            application_id=application_id,
            text=request.text,
            current_phase=application.current_phase,
            applicant_id=str(application.applicant_id),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
