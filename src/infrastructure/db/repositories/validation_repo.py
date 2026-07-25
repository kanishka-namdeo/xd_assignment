"""Cross-document validation data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.validation import CrossDocumentValidation


class CrossDocumentValidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> CrossDocumentValidation:
        validation = CrossDocumentValidation(**kwargs)
        self.session.add(validation)
        await self.session.flush()
        await self.session.refresh(validation)
        return validation

    async def get_by_id(self, validation_id: UUID) -> CrossDocumentValidation | None:
        result = await self.session.execute(
            select(CrossDocumentValidation).where(CrossDocumentValidation.id == validation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_applicant(self, applicant_id: UUID) -> list[CrossDocumentValidation]:
        result = await self.session.execute(
            select(CrossDocumentValidation).where(
                CrossDocumentValidation.applicant_id == applicant_id
            )
        )
        return list(result.scalars().all())

    async def get_unresolved(self, applicant_id: UUID | None = None) -> list[CrossDocumentValidation]:
        stmt = select(CrossDocumentValidation).where(
            CrossDocumentValidation.is_resolved == False  # noqa: E712
        )
        if applicant_id is not None:
            stmt = stmt.where(CrossDocumentValidation.applicant_id == applicant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def resolve(
        self, validation_id: UUID, resolved_by: str, resolution_notes: str | None = None
    ) -> CrossDocumentValidation | None:
        validation = await self.get_by_id(validation_id)
        if validation is None:
            return None
        validation.is_resolved = True
        validation.resolved_by = resolved_by
        validation.resolution_notes = resolution_notes
        await self.session.flush()
        await self.session.refresh(validation)
        return validation
