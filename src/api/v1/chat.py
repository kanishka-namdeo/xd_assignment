"""Chat and conversation endpoints."""

from collections.abc import AsyncGenerator
import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AsyncDB
from src.domain.schemas.chat import ChatRequest, ChatResponse, UploadedDocument
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.observability.langfuse_client import LangfuseClient
from src.services.agent_runner import run as run_orchestrator

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


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
    request: ChatRequest,
    db: AsyncDB,
    fastapi_request: Request,
) -> ChatResponse:
    logger.info("request_received", event="request_received", application_id=application_id, endpoint="chat")

    application_repo = ApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)

    if application is None:
        logger.warning("request_failed", event="request_failed", application_id=application_id, detail="Application not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    previous_phase = application.current_phase

    langfuse_client: LangfuseClient | None = getattr(fastapi_request.app.state, "langfuse", None)

    try:
        result = await run_orchestrator(
            {
                "messages": [{"role": "user", "content": request.text}],
                "current_phase": application.current_phase,
                "applicant_id": str(application.applicant_id),
                "application_id": str(application.id),
                "uploaded_files": request.file_paths,
            },
            langfuse_client=langfuse_client,
        )
    except Exception as e:
        logger.exception("request_failed", event="request_failed", application_id=application_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing error: {str(e)}",
        )

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
        logger.info("phase_transition", event="phase_transition", application_id=application_id, from_phase=previous_phase, to_phase=new_phase)

    logger.info("response_sent", event="response_sent", application_id=application_id, phase=new_phase, document_count=len(uploaded_documents))

    return ChatResponse(
        message=result["messages"][-1].content if hasattr(result["messages"][-1], 'content') else result["messages"][-1]["content"],
        phase=new_phase,
        uploaded_documents=uploaded_documents,
        decision=result.get("decision"),
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
    logger.info("request_received", event="request_received", application_id=application_id, endpoint="chat_stream")

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
