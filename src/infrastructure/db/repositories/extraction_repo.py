"""Extraction data access - one repository per extraction table."""

import time
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.extraction import (
    ApplicationFormData,
    AssetsLiabilitiesData,
    BankStatementData,
    CreditReportData,
    EmiratesIDData,
    ResumeData,
)

logger = structlog.get_logger(__name__)


def _log_create(logger_instance: structlog.BoundLogger, repo_name: str, entity_id: str, duration_ms: float) -> None:
    logger_instance.debug(
        "extraction_data_created",
        repository=repo_name,
        entity_id=entity_id,
        duration_ms=duration_ms,
    )


def _log_upsert(logger_instance: structlog.BoundLogger, repo_name: str, document_id: str, is_update: bool, duration_ms: float) -> None:
    logger_instance.debug(
        "extraction_data_upserted",
        repository=repo_name,
        document_id=str(document_id),
        operation="update" if is_update else "insert",
        duration_ms=duration_ms,
    )


class EmiratesIDRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> EmiratesIDData:
        start = time.perf_counter()
        data = EmiratesIDData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        _log_create(logger, "EmiratesIDRepository", str(data.id), round((time.perf_counter() - start) * 1000, 2))
        return data

    async def get_by_document_id(self, document_id: UUID) -> EmiratesIDData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(EmiratesIDData).where(EmiratesIDData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_document_id",
            repository="EmiratesIDRepository",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def get_by_identity_number(self, identity_number: str) -> EmiratesIDData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(EmiratesIDData).where(EmiratesIDData.identity_number == identity_number)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_identity_number",
            repository="EmiratesIDRepository",
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def upsert(self, document_id: UUID, **kwargs) -> EmiratesIDData:
        start = time.perf_counter()
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            _log_upsert(logger, "EmiratesIDRepository", str(document_id), True, round((time.perf_counter() - start) * 1000, 2))
            return existing
        data = await self.create(document_id=document_id, **kwargs)
        _log_upsert(logger, "EmiratesIDRepository", str(document_id), False, round((time.perf_counter() - start) * 1000, 2))
        return data


class BankStatementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> BankStatementData:
        start = time.perf_counter()
        data = BankStatementData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        _log_create(logger, "BankStatementRepository", str(data.id), round((time.perf_counter() - start) * 1000, 2))
        return data

    async def get_by_document_id(self, document_id: UUID) -> BankStatementData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(BankStatementData).where(BankStatementData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_document_id",
            repository="BankStatementRepository",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def upsert(self, document_id: UUID, **kwargs) -> BankStatementData:
        start = time.perf_counter()
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            _log_upsert(logger, "BankStatementRepository", str(document_id), True, round((time.perf_counter() - start) * 1000, 2))
            return existing
        data = await self.create(document_id=document_id, **kwargs)
        _log_upsert(logger, "BankStatementRepository", str(document_id), False, round((time.perf_counter() - start) * 1000, 2))
        return data


class CreditReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> CreditReportData:
        start = time.perf_counter()
        data = CreditReportData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        _log_create(logger, "CreditReportRepository", str(data.id), round((time.perf_counter() - start) * 1000, 2))
        return data

    async def get_by_document_id(self, document_id: UUID) -> CreditReportData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(CreditReportData).where(CreditReportData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_document_id",
            repository="CreditReportRepository",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def upsert(self, document_id: UUID, **kwargs) -> CreditReportData:
        start = time.perf_counter()
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            _log_upsert(logger, "CreditReportRepository", str(document_id), True, round((time.perf_counter() - start) * 1000, 2))
            return existing
        data = await self.create(document_id=document_id, **kwargs)
        _log_upsert(logger, "CreditReportRepository", str(document_id), False, round((time.perf_counter() - start) * 1000, 2))
        return data


class ResumeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> ResumeData:
        start = time.perf_counter()
        data = ResumeData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        _log_create(logger, "ResumeRepository", str(data.id), round((time.perf_counter() - start) * 1000, 2))
        return data

    async def get_by_document_id(self, document_id: UUID) -> ResumeData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(ResumeData).where(ResumeData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_document_id",
            repository="ResumeRepository",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def upsert(self, document_id: UUID, **kwargs) -> ResumeData:
        start = time.perf_counter()
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            _log_upsert(logger, "ResumeRepository", str(document_id), True, round((time.perf_counter() - start) * 1000, 2))
            return existing
        data = await self.create(document_id=document_id, **kwargs)
        _log_upsert(logger, "ResumeRepository", str(document_id), False, round((time.perf_counter() - start) * 1000, 2))
        return data


class AssetsLiabilitiesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> AssetsLiabilitiesData:
        start = time.perf_counter()
        data = AssetsLiabilitiesData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        _log_create(logger, "AssetsLiabilitiesRepository", str(data.id), round((time.perf_counter() - start) * 1000, 2))
        return data

    async def get_by_document_id(self, document_id: UUID) -> AssetsLiabilitiesData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(AssetsLiabilitiesData).where(AssetsLiabilitiesData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_document_id",
            repository="AssetsLiabilitiesRepository",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def upsert(self, document_id: UUID, **kwargs) -> AssetsLiabilitiesData:
        start = time.perf_counter()
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            _log_upsert(logger, "AssetsLiabilitiesRepository", str(document_id), True, round((time.perf_counter() - start) * 1000, 2))
            return existing
        data = await self.create(document_id=document_id, **kwargs)
        _log_upsert(logger, "AssetsLiabilitiesRepository", str(document_id), False, round((time.perf_counter() - start) * 1000, 2))
        return data


class ApplicationFormRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> ApplicationFormData:
        start = time.perf_counter()
        data = ApplicationFormData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        _log_create(logger, "ApplicationFormRepository", str(data.id), round((time.perf_counter() - start) * 1000, 2))
        return data

    async def get_by_document_id(self, document_id: UUID) -> ApplicationFormData | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(ApplicationFormData).where(ApplicationFormData.document_id == document_id)
        )
        data = result.scalar_one_or_none()
        logger.debug(
            "extraction_data_get_by_document_id",
            repository="ApplicationFormRepository",
            document_id=str(document_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=data is not None,
        )
        return data

    async def upsert(self, document_id: UUID, **kwargs) -> ApplicationFormData:
        start = time.perf_counter()
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            _log_upsert(logger, "ApplicationFormRepository", str(document_id), True, round((time.perf_counter() - start) * 1000, 2))
            return existing
        data = await self.create(document_id=document_id, **kwargs)
        _log_upsert(logger, "ApplicationFormRepository", str(document_id), False, round((time.perf_counter() - start) * 1000, 2))
        return data
