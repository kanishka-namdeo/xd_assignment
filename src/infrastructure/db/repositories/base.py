"""Generic CRUD base repository."""

import time
from typing import Generic, TypeVar
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

Base = TypeVar("Base")


class BaseRepository(Generic[Base]):
    def __init__(self, model: type[Base], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> Base | None:
        start = time.perf_counter()
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        logger.debug(
            "repository_get_by_id",
            model=self.model.__name__,
            entity_id=str(entity_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            found=entity is not None,
        )
        return entity

    async def create(self, **kwargs) -> Base:
        start = time.perf_counter()
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        logger.debug(
            "repository_create",
            model=self.model.__name__,
            entity_id=str(entity.id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return entity

    async def update(self, entity: Base) -> Base:
        start = time.perf_counter()
        await self.session.merge(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        logger.debug(
            "repository_update",
            model=self.model.__name__,
            entity_id=str(entity.id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return entity
