"""Chat request/response schemas."""

from pydantic import BaseModel
from uuid import UUID


class ChatRequest(BaseModel):
    text: str
    file_paths: list[str] = []


class UploadedDocument(BaseModel):
    doc_type: str
    file_path: str
    status: str


class InterruptData(BaseModel):
    """Data returned when the graph pauses at an interrupt point."""
    question: str
    phase: str
    missing_fields: list[str] | None = None
    missing_documents: list[str] | None = None
    discrepancies: list[dict] | None = None
    recommendations: list[str] | None = None


class ChatResponse(BaseModel):
    message: str
    phase: str
    uploaded_documents: list[UploadedDocument] = []
    decision: str | None = None
    decision_card: dict | None = None
    interrupt: InterruptData | None = None
    enablement_recommendations: list[dict] | list[str] | None = None
    discrepancies: list[dict] | None = None
    validation_confidence: float | None = None
