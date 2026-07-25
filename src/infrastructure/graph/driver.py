"""Neo4j async driver setup - singleton pattern."""

import structlog
from neo4j import AsyncGraphDatabase
from neo4j._async.driver import AsyncDriver

from src.config import Settings

logger = structlog.get_logger(__name__)

_driver: AsyncDriver | None = None


def get_driver(settings: Settings) -> AsyncDriver:
    """Return the singleton Neo4j async driver, creating it on first call."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        logger.info(
            "neo4j_driver_created",
            uri=settings.NEO4J_URI,
        )
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver connection."""
    global _driver
    if _driver is not None:
        await _driver.close()
        logger.info("neo4j_driver_closed")
        _driver = None
