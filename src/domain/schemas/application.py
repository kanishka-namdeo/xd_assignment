"""Application request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ApplicationCreateRequest(BaseModel):
    applicant_id: UUID
    support_category: str | None = None


class ApplicationResponse(BaseModel):
    id: UUID
    applicant_id: UUID
    status: str
    current_phase: str
    eligibility_score: float | None = None
    validation_confidence: float | None = None
    decision: str | None = None
    decision_explanation: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationStatusUpdateRequest(BaseModel):
    status: str
    phase: str | None = None


class DocumentResponse(BaseModel):
    id: UUID
    applicant_id: UUID
    document_type: str
    processing_status: str
    file_format: str | None = None
    file_size_bytes: int | None = None
    file_hash: str
    extraction_status: str | None = None
    validation_status: str | None = None
    overall_confidence: float | None = None
    uploaded_at: datetime
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
