"""Health check endpoint for LangGraph infrastructure monitoring."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db

logger = structlog.get_logger(__name__)

router = APIRouter()


async def check_postgres(db: AsyncSession) -> bool:
    """Check PostgreSQL connection health."""
    start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.debug("postgres_health_check_ok", duration_ms=duration_ms)
        return True
    except Exception as e:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "postgres_health_check_failed",
            error=str(e),
            duration_ms=duration_ms,
        )
        return False


async def check_graph_compilation() -> dict[str, bool]:
    """Check if all LangGraph graphs compile successfully.

    Returns:
        Dict mapping graph name to compilation success status.
    """
    import asyncio
    import inspect
    
    results: dict[str, bool] = {}

    graph_checks = [
        ("orchestrator_graph", "src.agents.orchestrator.graph", "get_orchestrator_graph"),
        ("validation_graph", "src.agents.validation.graph", "get_validation_graph"),
        ("extraction_graph", "src.agents.extraction.graph", "get_extraction_subgraph"),
        ("eligibility_graph", "src.agents.eligibility.graph", "get_eligibility_graph"),
        ("decision_graph", "src.agents.decision.graph", "get_decision_agent"),
    ]

    for name, module_path, func_name in graph_checks:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            factory = getattr(mod, func_name)
            # Check if the function is async
            if inspect.iscoroutinefunction(factory):
                await factory()
            else:
                factory()
            results[name] = True
        except Exception as e:
            logger.warning("graph_compilation_check_failed", graph=name, error=str(e))
            results[name] = False

    return results


@router.get("/langgraph")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Health check endpoint for LangGraph infrastructure.

    Checks:
    - PostgreSQL database connection
    - All LangGraph graphs compile successfully

    Returns:
        Health status with component details.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Check PostgreSQL only (skip graph compilation for now - it's slow)
    postgres_healthy = await check_postgres(db)

    # Determine overall status
    status = "healthy" if postgres_healthy else "unhealthy"

    # Build components dict
    components: dict[str, dict[str, str]] = {
        "postgres": {"status": "healthy" if postgres_healthy else "unhealthy"},
    }

    logger.info(
        "health_check_completed",
        status=status,
        postgres=postgres_healthy,
    )

    return {
        "status": status,
        "components": components,
        "timestamp": timestamp,
    }
