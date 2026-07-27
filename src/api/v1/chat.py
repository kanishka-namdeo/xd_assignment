"""Chat and conversation endpoints."""

import json
from collections.abc import AsyncGenerator
from pathlib import Path
import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.config import settings
from src.domain.schemas.chat import ChatResponse
from src.infrastructure.llm.client import LLMClient
from src.services.agent_runner import run_streaming
from src.services.chat_service import ChatService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])

UPLOAD_DIR = Path("data/uploads")


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


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
            model=settings.STREAMLAKE_MODEL,
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
    fastapi_request: Request,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    text: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> ChatResponse:
    logger.info("request_received", application_id=application_id, endpoint="chat")

    langfuse_client = getattr(fastapi_request.app.state, "langfuse", None)

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

    return await chat_service.handle_chat(
        application_id=application_id,
        text=text,
        file_paths=file_paths,
        langfuse_client=langfuse_client,
    )


async def _stream_generator(
    application_id: str,
    text: str,
    files: list[UploadFile],
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted events from the orchestrator graph."""
    try:
        # Save uploaded files to disk
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

        # Build graph input
        graph_input = {
            "messages": [{"role": "user", "content": text}],
            "uploaded_files": file_paths,
            "application_id": application_id,
        }

        # Stream events from orchestrator
        async for event in run_streaming(graph_input):
            # Convert event dict to SSE format
            yield f"data: {json.dumps(event)}\n\n"

    except Exception as e:
        logger.exception("stream_error", application_id=application_id, error=str(e))
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/applications/{application_id}/chat/stream")
async def chat_stream(
    application_id: str,
    text: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> StreamingResponse:
    """Stream orchestrator events as server-sent events.

    Yields phase transitions, extraction/validation results, and decisions
    in SSE format (data: <json>\\n\\n).
    Ends with data: [DONE]\\n\\n.
    """
    logger.info("request_received", application_id=application_id, endpoint="chat_stream")

    return StreamingResponse(
        _stream_generator(
            application_id=application_id,
            text=text,
            files=files,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
