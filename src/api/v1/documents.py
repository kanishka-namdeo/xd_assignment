"""Document upload and status endpoints."""

import structlog
from fastapi import APIRouter, HTTPException

from src.api.deps import AsyncDB
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.db.repositories.document_repo import DocumentRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/status")
async def document_status(
    application_id: str,
    db: AsyncDB,
) -> dict:
    """Return document upload status for an application."""
    logger.info("request_received", application_id=application_id)

    application_repo = ApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    document_repo = DocumentRepository(db)
    documents = await document_repo.get_by_applicant(application.applicant_id)

    return {
        "application_id": application_id,
        "documents": [
            {
                "document_type": doc.document_type,
                "status": doc.processing_status,
                "confidence": doc.overall_confidence,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in documents
        ],
    }
