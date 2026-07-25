"""Generic CRUD base repository."""

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

Base = TypeVar("Base")


class BaseRepository(Generic[Base]):
    def __init__(self, model: type[Base], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> Base | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Base:
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: Base) -> Base:
        await self.session.merge(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
