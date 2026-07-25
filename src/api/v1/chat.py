"""Chat and conversation endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AsyncDB
from src.domain.schemas.chat import ChatRequest, ChatResponse, UploadedDocument
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.services.agent_runner import run as run_orchestrator

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post(
    "/applications/{application_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    application_id: str,
    request: ChatRequest,
    db: AsyncDB,
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

    try:
        result = await run_orchestrator(
            {
                "messages": [{"role": "user", "content": request.text}],
                "current_phase": application.current_phase,
                "applicant_id": str(application.applicant_id),
                "application_id": str(application.id),
                "uploaded_files": request.file_paths,
            }
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
