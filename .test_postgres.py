import asyncio
import time

import structlog

from sqlalchemy import text
from src.infrastructure.db.session import get_engine
from src.config import settings
from src.infrastructure.observability.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


async def check():
    t0 = time.time()
    logger.info("postgres_connection_check_started")
    e = get_engine(settings)
    async with e.connect() as c:
        t1 = time.time()
        r = await c.execute(text("SELECT 1"))
        duration_ms = (time.time() - t1) * 1000
        result = r.scalar()
        logger.info("postgres_connection_check_completed", result=result, duration_ms=round(duration_ms, 1))
    total_duration_ms = (time.time() - t0) * 1000
    logger.info("postgres_check_completed", total_duration_ms=round(total_duration_ms, 1))


asyncio.run(check())
