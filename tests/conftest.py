"""Shared test fixtures."""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.infrastructure.db.session import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database session for unit tests."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def mock_neo4j() -> MagicMock:
    """Mock Neo4j driver."""
    driver = MagicMock()
    driver.session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    driver.session.return_value.__exit__ = MagicMock(return_value=None)
    return driver


@pytest.fixture
def mock_qdrant() -> MagicMock:
    """Mock Qdrant client."""
    return MagicMock()


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM client."""
    client = AsyncMock()
    client.chat_completion = AsyncMock(return_value={
        "choices": [{"message": {"content": "Test response"}}],
        "usage": {"total_tokens": 100}
    })
    return client
