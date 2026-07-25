"""Cross-document validation data access."""

import time
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.validation import CrossDocumentValidation

logger = structlog.get_logger(__name__)


class CrossDocumentValidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> CrossDocumentValidation:
        start = time.perf_counter()
        validation = CrossDocumentValidation(**kwargs)
        self.session.add(validation)
        await self.session.flush()
        await self.session.refresh(validation)
        logger.info(
            "validation_created",
            validation_id=str(validation.id),
            applicant_id=str(validation.applicant_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return validation

    async def get_by_id(self, validation_id: UUID) -> CrossDocumentValidation | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(CrossDocumentValidation).where(CrossDocumentValidation.id == validation_id)
        )
        validation = result.scalar_one_or_none()
        logger.debug(
            "validation_get_by_id",
            validation_id=str(validation_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=validation is not None,
        )
        return validation

    async def get_by_applicant(self, applicant_id: UUID) -> list[CrossDocumentValidation]:
        start = time.perf_counter()
        result = await self.session.execute(
            select(CrossDocumentValidation).where(
                CrossDocumentValidation.applicant_id == applicant_id
            )
        )
        validations = list(result.scalars().all())
        logger.debug(
            "validation_get_by_applicant",
            applicant_id=str(applicant_id),
            count=len(validations),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return validations

    async def get_unresolved(self, applicant_id: UUID | None = None) -> list[CrossDocumentValidation]:
        start = time.perf_counter()
        stmt = select(CrossDocumentValidation).where(
            CrossDocumentValidation.is_resolved == False  # noqa: E712
        )
        if applicant_id is not None:
            stmt = stmt.where(CrossDocumentValidation.applicant_id == applicant_id)
        result = await self.session.execute(stmt)
        validations = list(result.scalars().all())
        logger.debug(
            "validation_get_unresolved",
            applicant_id=str(applicant_id),
            count=len(validations),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return validations

    async def resolve(
        self, validation_id: UUID, resolved_by: str, resolution_notes: str | None = None
    ) -> CrossDocumentValidation | None:
        start = time.perf_counter()
        validation = await self.get_by_id(validation_id)
        if validation is None:
            logger.warning(
                "validation_resolve_not_found",
                validation_id=str(validation_id),
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            return None
        validation.is_resolved = True
        validation.resolved_by = resolved_by
        validation.resolution_notes = resolution_notes
        await self.session.flush()
        await self.session.refresh(validation)
        logger.info(
            "validation_resolved",
            validation_id=str(validation_id),
            resolved_by=resolved_by,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return validation
