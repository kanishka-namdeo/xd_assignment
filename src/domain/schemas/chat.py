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


class ChatResponse(BaseModel):
    message: str
    phase: str
    uploaded_documents: list[UploadedDocument] = []
    decision: str | None = None
