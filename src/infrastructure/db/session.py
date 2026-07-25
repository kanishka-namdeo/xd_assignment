"""SQLAlchemy async engine and sessionmaker."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import Settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


_engine = None
_SessionLocal = None


def get_engine(settings: Settings):
    global _engine
    if _engine is None:
        database_url = settings.DATABASE_URL
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(settings)
        _SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _SessionLocal
