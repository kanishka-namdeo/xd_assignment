"""Document data access."""

import time
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.document import Document

logger = structlog.get_logger(__name__)


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Document:
        start = time.perf_counter()
        document = Document(**kwargs)
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        logger.info(
            "document_created",
            document_id=str(document.id),
            document_type=kwargs.get("document_type"),
            applicant_id=str(kwargs.get("applicant_id")),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return document

    async def get_by_id(self, document_id: UUID) -> Document | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        logger.debug(
            "document_get_by_id",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=document is not None,
        )
        return document

    async def get_by_applicant(self, applicant_id: UUID) -> list[Document]:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Document).where(Document.applicant_id == applicant_id)
        )
        documents = list(result.scalars().all())
        logger.debug(
            "document_get_by_applicant",
            applicant_id=str(applicant_id),
            count=len(documents),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return documents

    async def get_by_applicant_and_type(
        self, applicant_id: UUID, document_type: str
    ) -> list[Document]:
        start = time.perf_counter()
        result = await self.session.execute(
            select(Document)
            .where(Document.applicant_id == applicant_id)
            .where(Document.document_type == document_type)
        )
        documents = list(result.scalars().all())
        logger.debug(
            "document_get_by_applicant_and_type",
            applicant_id=str(applicant_id),
            document_type=document_type,
            count=len(documents),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return documents

    async def update_status(
        self, document_id: UUID, processing_status: str | None = None, extraction_status: str | None = None, validation_status: str | None = None
    ) -> Document | None:
        start = time.perf_counter()
        document = await self.get_by_id(document_id)
        if document is None:
            logger.warning(
                "document_update_status_not_found",
                document_id=str(document_id),
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            return None
        if processing_status is not None:
            document.processing_status = processing_status
        if extraction_status is not None:
            document.extraction_status = extraction_status
        if validation_status is not None:
            document.validation_status = validation_status
        await self.session.commit()
        await self.session.refresh(document)
        logger.debug(
            "document_status_updated",
            document_id=str(document_id),
            processing_status=processing_status,
            extraction_status=extraction_status,
            validation_status=validation_status,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return document

    async def update(self, document: Document) -> Document:
        start = time.perf_counter()
        await self.session.merge(document)
        await self.session.commit()
        await self.session.refresh(document)
        logger.debug(
            "document_updated",
            document_id=str(document.id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return document
