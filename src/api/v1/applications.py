"""Application and document management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AsyncDB
from src.domain.schemas.application import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationStatusUpdateRequest,
    DocumentListResponse,
    DocumentResponse,
)
from src.services.application_service import ApplicationService
from src.services.document_service import DocumentService

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_application_response(app) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        applicant_id=app.applicant_id,
        status=app.status,
        current_phase=app.current_phase,
        eligibility_score=app.eligibility_score,
        decision=app.decision,
        decision_explanation=app.decision_explanation,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def _to_document_response(doc) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        applicant_id=doc.applicant_id,
        document_type=doc.document_type,
        processing_status=doc.processing_status,
        file_format=doc.file_format,
        file_size_bytes=doc.file_size_bytes,
        file_hash=doc.file_hash,
        extraction_status=doc.extraction_status,
        validation_status=doc.validation_status,
        overall_confidence=doc.overall_confidence,
        uploaded_at=doc.uploaded_at,
        created_at=doc.created_at,
    )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    request: ApplicationCreateRequest,
    db: AsyncDB,
) -> ApplicationResponse:
    """Create a new application for an applicant."""
    service = ApplicationService(db)
    application = await service.create_application(
        applicant_id=request.applicant_id,
        support_category=request.support_category,
    )
    return _to_application_response(application)


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_application(
    application_id: UUID,
    db: AsyncDB,
) -> ApplicationResponse:
    """Get application status and details."""
    service = ApplicationService(db)
    application = await service.get_application(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return _to_application_response(application)


@router.patch(
    "/{application_id}/status",
    response_model=ApplicationResponse,
    status_code=status.HTTP_200_OK,
)
async def update_application_status(
    application_id: UUID,
    request: ApplicationStatusUpdateRequest,
    db: AsyncDB,
) -> ApplicationResponse:
    """Update application status and phase."""
    service = ApplicationService(db)
    application = await service.update_application_status(
        application_id, request.status, request.phase
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return _to_application_response(application)


@router.get(
    "/{application_id}/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_documents(
    application_id: UUID,
    db: AsyncDB,
) -> DocumentListResponse:
    """List all documents for an application."""
    app_service = ApplicationService(db)
    application = await app_service.get_application(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    doc_service = DocumentService(db)
    documents = await doc_service.list_documents(application.applicant_id)
    return DocumentListResponse(
        documents=[_to_document_response(d) for d in documents],
        total=len(documents),
    )


@router.post(
    "/{application_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    application_id: UUID,
    db: AsyncDB,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
) -> DocumentResponse:
    """Upload a document for an application (multipart/form-data)."""
    app_service = ApplicationService(db)
    application = await app_service.get_application(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    doc_service = DocumentService(db)
    document = await doc_service.upload_document(
        applicant_id=application.applicant_id,
        file=file,
        document_type=document_type,
    )
    return _to_document_response(document)


@router.delete(
    "/{application_id}/documents/{document_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_document(
    application_id: UUID,
    document_id: UUID,
    db: AsyncDB,
) -> dict:
    """Delete a document from an application."""
    app_service = ApplicationService(db)
    application = await app_service.get_application(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    doc_service = DocumentService(db)
    deleted = await doc_service.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return {"status": "deleted", "document_id": str(document_id)}
