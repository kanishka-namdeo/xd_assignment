"""Shared dependencies (get_db, get_settings, get_neo4j, get_qdrant, services)."""

from typing import Annotated, AsyncGenerator

import structlog
from fastapi import Depends
from neo4j._async.driver import AsyncDriver
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.graph.driver import get_driver as get_neo4j_driver
from src.infrastructure.vector.client import get_client as get_qdrant_client
from src.services.application_service import ApplicationService
from src.services.decision_service import DecisionService
from src.services.document_service import DocumentService
from src.services.eligibility_service import EligibilityService
from src.services.extraction_service import ExtractionService
from src.services.validation_service import ValidationService

logger = structlog.get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory(settings)
    db = session_factory()
    logger.debug("dependency_created", )
    try:
        yield db
    finally:
        await db.close()
        logger.debug("dependency_closed", )


async def get_neo4j() -> AsyncGenerator[AsyncDriver, None]:
    driver = get_neo4j_driver(settings)
    logger.debug("dependency_created", )
    try:
        yield driver
    finally:
        logger.debug("dependency_closed", )


async def get_qdrant() -> AsyncGenerator[AsyncQdrantClient, None]:
    client = get_qdrant_client(settings)
    logger.debug("dependency_created", )
    try:
        yield client
    finally:
        logger.debug("dependency_closed", )


def get_application_service(db: AsyncSession = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_eligibility_service(db: AsyncSession = Depends(get_db)) -> EligibilityService:
    return EligibilityService(db)


def get_extraction_service(
    db: AsyncSession = Depends(get_db),
    neo4j: AsyncDriver = Depends(get_neo4j),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
) -> ExtractionService:
    return ExtractionService(db, neo4j_driver=neo4j, qdrant_client=qdrant)


def get_validation_service(db: AsyncSession = Depends(get_db)) -> ValidationService:
    return ValidationService(db)


def get_decision_service(db: AsyncSession = Depends(get_db)) -> DecisionService:
    return DecisionService(db)


AsyncDB = Annotated[AsyncSession, Depends(get_db)]
AsyncNeo4j = Annotated[AsyncDriver, Depends(get_neo4j)]
AsyncQdrant = Annotated[AsyncQdrantClient, Depends(get_qdrant)]
