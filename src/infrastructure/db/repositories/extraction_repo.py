"""Extraction data access - one repository per extraction table."""

from uuid import UUID

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


class EmiratesIDRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> EmiratesIDData:
        data = EmiratesIDData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        return data

    async def get_by_document_id(self, document_id: UUID) -> EmiratesIDData | None:
        result = await self.session.execute(
            select(EmiratesIDData).where(EmiratesIDData.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_identity_number(self, identity_number: str) -> EmiratesIDData | None:
        result = await self.session.execute(
            select(EmiratesIDData).where(EmiratesIDData.identity_number == identity_number)
        )
        return result.scalar_one_or_none()

    async def upsert(self, document_id: UUID, **kwargs) -> EmiratesIDData:
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(document_id=document_id, **kwargs)


class BankStatementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> BankStatementData:
        data = BankStatementData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        return data

    async def get_by_document_id(self, document_id: UUID) -> BankStatementData | None:
        result = await self.session.execute(
            select(BankStatementData).where(BankStatementData.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, document_id: UUID, **kwargs) -> BankStatementData:
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(document_id=document_id, **kwargs)


class CreditReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> CreditReportData:
        data = CreditReportData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        return data

    async def get_by_document_id(self, document_id: UUID) -> CreditReportData | None:
        result = await self.session.execute(
            select(CreditReportData).where(CreditReportData.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, document_id: UUID, **kwargs) -> CreditReportData:
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(document_id=document_id, **kwargs)


class ResumeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> ResumeData:
        data = ResumeData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        return data

    async def get_by_document_id(self, document_id: UUID) -> ResumeData | None:
        result = await self.session.execute(
            select(ResumeData).where(ResumeData.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, document_id: UUID, **kwargs) -> ResumeData:
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(document_id=document_id, **kwargs)


class AssetsLiabilitiesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> AssetsLiabilitiesData:
        data = AssetsLiabilitiesData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        return data

    async def get_by_document_id(self, document_id: UUID) -> AssetsLiabilitiesData | None:
        result = await self.session.execute(
            select(AssetsLiabilitiesData).where(AssetsLiabilitiesData.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, document_id: UUID, **kwargs) -> AssetsLiabilitiesData:
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(document_id=document_id, **kwargs)


class ApplicationFormRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> ApplicationFormData:
        data = ApplicationFormData(**kwargs)
        self.session.add(data)
        await self.session.flush()
        await self.session.refresh(data)
        return data

    async def get_by_document_id(self, document_id: UUID) -> ApplicationFormData | None:
        result = await self.session.execute(
            select(ApplicationFormData).where(ApplicationFormData.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, document_id: UUID, **kwargs) -> ApplicationFormData:
        existing = await self.get_by_document_id(document_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(document_id=document_id, **kwargs)
