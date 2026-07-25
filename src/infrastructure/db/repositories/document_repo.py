"""Document data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Document:
        document = Document(**kwargs)
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_applicant(self, applicant_id: UUID) -> list[Document]:
        result = await self.session.execute(
            select(Document).where(Document.applicant_id == applicant_id)
        )
        return list(result.scalars().all())

    async def get_by_applicant_and_type(
        self, applicant_id: UUID, document_type: str
    ) -> list[Document]:
        result = await self.session.execute(
            select(Document)
            .where(Document.applicant_id == applicant_id)
            .where(Document.document_type == document_type)
        )
        return list(result.scalars().all())

    async def update_status(
        self, document_id: UUID, processing_status: str | None = None, extraction_status: str | None = None, validation_status: str | None = None
    ) -> Document | None:
        document = await self.get_by_id(document_id)
        if document is None:
            return None
        if processing_status is not None:
            document.processing_status = processing_status
        if extraction_status is not None:
            document.extraction_status = extraction_status
        if validation_status is not None:
            document.validation_status = validation_status
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update(self, document: Document) -> Document:
        await self.session.merge(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document
