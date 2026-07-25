"""Neo4j async driver setup - singleton pattern."""

from neo4j import AsyncGraphDatabase
from neo4j._async.driver import AsyncDriver

from src.config import Settings

_driver: AsyncDriver | None = None


def get_driver(settings: Settings) -> AsyncDriver:
    """Return the singleton Neo4j async driver, creating it on first call."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver connection."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
