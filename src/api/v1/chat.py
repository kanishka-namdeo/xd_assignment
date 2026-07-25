"""Chat and conversation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AsyncDB
from src.domain.schemas.chat import ChatRequest, ChatResponse, UploadedDocument
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.services.agent_runner import run as run_orchestrator

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
    application_repo = ApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    result = await run_orchestrator(
        {
            "messages": [{"role": "user", "content": request.text}],
            "current_phase": application.current_phase,
            "applicant_id": str(application.applicant_id),
            "application_id": str(application.id),
            "uploaded_files": request.file_paths,
        }
    )

    application.current_phase = result.get("current_phase", application.current_phase)
    await application_repo.update(application)

    uploaded_documents = [
        UploadedDocument(
            doc_type=doc.get("doc_type", "unknown"),
            file_path=doc.get("file_path", ""),
            status=doc.get("status", "uploaded"),
        )
        for doc in result.get("uploaded_documents", [])
    ]

    return ChatResponse(
        message=result["messages"][-1]["content"],
        phase=result.get("current_phase", application.current_phase),
        uploaded_documents=uploaded_documents,
        decision=result.get("decision"),
    )
