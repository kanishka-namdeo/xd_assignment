"""Document service - file upload, storage, and metadata management."""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.db.models.document import Document
from src.infrastructure.db.repositories.document_repo import DocumentRepository

logger = structlog.get_logger(__name__)

UPLOAD_DIR = Path("uploads")

DOCUMENT_TYPE_MAP: dict[str, list[str]] = {
    "emirates_id": ["emirates_id", "eid", "id_card"],
    "bank_statement": ["bank_statement", "bank", "statement"],
    "credit_report": ["credit_report", "credit", "aecb"],
    "resume": ["resume", "cv", "curriculum_vitae"],
    "assets_liabilities": ["assets_liabilities", "assets", "financial_statement"],
    "application_form": ["application_form", "application", "form"],
}


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def classify_document_type(filename: str, declared_type: str | None = None) -> str:
    """Classify document type from filename or declared type."""
    if declared_type and declared_type in DOCUMENT_TYPE_MAP:
        return declared_type

    name_lower = (filename or "").lower()
    for doc_type, keywords in DOCUMENT_TYPE_MAP.items():
        if any(kw in name_lower for kw in keywords):
            return doc_type
    return "application_form"


def get_file_format(filename: str) -> str:
    """Extract file format from filename extension."""
    ext = Path(filename).suffix.lower().lstrip(".")
    format_map = {
        "pdf": "pdf",
        "xlsx": "xlsx",
        "xls": "xlsx",
        "jpg": "jpg",
        "jpeg": "jpg",
        "png": "png",
        "docx": "docx",
    }
    return format_map.get(ext, "unknown")


class DocumentService:
    """Manage document upload, storage, and lifecycle."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DocumentRepository(session)

    async def upload_document(
        self,
        applicant_id: UUID,
        file: UploadFile,
        document_type: str | None = None,
    ) -> Document:
        """Upload a file, compute hash, store on disk, and create DB record."""
        try:
            content = await file.read()
            file_hash = compute_file_hash(content)
            file_format = get_file_format(file.filename or "unknown")
            classified_type = classify_document_type(file.filename or "", document_type)

            logger.debug(
                "document_classified",
                filename=file.filename,
                declared_type=document_type,
                classified_type=classified_type,
                file_format=file_format,
                file_hash_prefix=file_hash[:16],
            )

            upload_subdir = UPLOAD_DIR / str(applicant_id)
            upload_subdir.mkdir(parents=True, exist_ok=True)

            stored_filename = f"{uuid.uuid4().hex}_{file.filename}"
            file_path = upload_subdir / stored_filename
            file_path.write_bytes(content)

            document = await self.repo.create(
                applicant_id=applicant_id,
                document_type=classified_type,
                file_path=str(file_path),
                file_format=file_format,
                file_size_bytes=len(content),
                file_hash=file_hash,
                processing_status="uploaded",
            )

            logger.info(
                "document_uploaded",
                document_id=str(document.id),
                applicant_id=str(applicant_id),
                document_type=classified_type,
                file_size=len(content),
            )
            return document
        except Exception as e:
            logger.exception(
                "document_upload_failed",
                applicant_id=str(applicant_id),
                filename=file.filename,
                error=str(e),
            )
            raise

    async def get_document(self, document_id: UUID) -> Document | None:
        """Retrieve document metadata by ID."""
        return await self.repo.get_by_id(document_id)

    async def list_documents(self, applicant_id: UUID) -> list[Document]:
        """List all documents for an applicant."""
        return await self.repo.get_by_applicant(applicant_id)

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete a document from storage and mark as archived."""
        document = await self.repo.get_by_id(document_id)
        if document is None:
            logger.warning("document_not_found", document_id=str(document_id))
            return False

        file_path = Path(document.file_path)
        if file_path.exists():
            file_path.unlink()

        document.processing_status = "archived"
        await self.repo.update(document)

        logger.info("document_deleted", document_id=str(document_id))
        return True

    async def update_processing_status(
        self,
        document_id: UUID,
        processing_status: str | None = None,
        extraction_status: str | None = None,
        validation_status: str | None = None,
    ) -> Document | None:
        """Update document processing pipeline status."""
        result = await self.repo.update_status(
            document_id,
            processing_status=processing_status,
            extraction_status=extraction_status,
            validation_status=validation_status,
        )
        if result is not None:
            logger.debug(
                "processing_status_updated",
                document_id=str(document_id),
                processing_status=processing_status,
                extraction_status=extraction_status,
                validation_status=validation_status,
            )
        else:
            logger.warning("document_status_update_failed", document_id=str(document_id))
        return result
