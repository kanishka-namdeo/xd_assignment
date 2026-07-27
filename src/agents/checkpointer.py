"""Shared checkpointer factory for all LangGraph agents with TTL cleanup."""

import asyncio
from datetime import datetime, timedelta, timezone

import psycopg
import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row

from src.config import settings

logger = structlog.get_logger(__name__)

_checkpointer: AsyncPostgresSaver | None = None
_manager: "CheckpointerManager | None" = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return a long-lived AsyncPostgresSaver, creating it on first call.

    This is a singleton factory that all graphs share to avoid connection leaks.
    """
    global _checkpointer
    if _checkpointer is None:
        # Convert SQLAlchemy async URL to sync PostgreSQL URL
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        # Replace localhost with 127.0.0.1 to avoid IPv6 hang issues
        db_url = db_url.replace("localhost", "127.0.0.1")
        conn = await psycopg.AsyncConnection.connect(
            db_url,
            autocommit=True,
            row_factory=dict_row,
        )
        _checkpointer = AsyncPostgresSaver(conn)
        logger.info("postgres_saver_initialized")
    return _checkpointer


class CheckpointerManager:
    """Manages the checkpointer singleton and background TTL cleanup task.
    
    The cleanup task runs periodically and deletes checkpoints older than
    the configured TTL to prevent unbounded database growth.
    """

    def __init__(self) -> None:
        """Initialize the manager with configuration from settings."""
        self.ttl_days: int = settings.CHECKPOINT_TTL_DAYS
        self.cleanup_interval_minutes: int = settings.CHECKPOINT_CLEANUP_INTERVAL_MINUTES
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task if not already running."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            logger.warning("cleanup_task_already_running")
            return

        self._shutdown_event.clear()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            "cleanup_task_started",
            ttl_days=self.ttl_days,
            cleanup_interval_minutes=self.cleanup_interval_minutes,
        )

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task gracefully."""
        if self._cleanup_task is None or self._cleanup_task.done():
            logger.warning("cleanup_task_not_running")
            return

        logger.info("stopping_cleanup_task")
        self._shutdown_event.set()
        self._cleanup_task.cancel()
        
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        
        logger.info("cleanup_task_stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop that runs cleanup periodically."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._run_cleanup()
                except Exception:
                    logger.exception("cleanup_task_error")
                
                # Wait for the interval or until shutdown is signaled
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.cleanup_interval_minutes * 60,
                    )
                    # If we get here, shutdown was signaled
                    break
                except asyncio.TimeoutError:
                    # Timeout means it's time for another cleanup
                    pass
        except asyncio.CancelledError:
            logger.info("cleanup_loop_cancelled")
            raise

    async def _run_cleanup(self) -> None:
        """Execute a single cleanup operation."""
        start_time = datetime.now(timezone.utc)
        
        # Ensure checkpointer is initialized
        checkpointer = await get_checkpointer()
        conn = checkpointer.conn
        
        # Calculate cutoff timestamp
        cutoff_time = start_time - timedelta(days=self.ttl_days)
        
        logger.info(
            "checkpoint_cleanup_started",
            cutoff_time=cutoff_time.isoformat(),
            ttl_days=self.ttl_days,
        )
        
        try:
            # Delete old checkpoints and their writes.
            # checkpoint_blobs are shared across checkpoints via version references
            # and are not deleted here to avoid breaking newer checkpoints.
            async with conn.cursor() as cur:
                # Check if there are any old checkpoints to clean
                await cur.execute(
                    """
                    SELECT COUNT(*) FROM checkpoints WHERE created_at < %s
                    """,
                    (cutoff_time,),
                )
                row = await cur.fetchone()
                count = row[0] if row else 0
                
                if count == 0:
                    logger.info("checkpoint_cleanup_no_old_checkpoints")
                    return
                
                # Delete writes associated with old checkpoints
                await cur.execute(
                    """
                    DELETE FROM checkpoint_writes
                    WHERE (thread_id, checkpoint_ns, checkpoint_id) IN (
                        SELECT thread_id, checkpoint_ns, checkpoint_id
                        FROM checkpoints
                        WHERE created_at < %s
                    )
                    """,
                    (cutoff_time,),
                )
                writes_deleted = cur.rowcount
                
                # Delete the old checkpoints
                await cur.execute(
                    """
                    DELETE FROM checkpoints
                    WHERE created_at < %s
                    """,
                    (cutoff_time,),
                )
                checkpoints_deleted = cur.rowcount
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            logger.info(
                "checkpoint_cleanup_completed",
                checkpoints_deleted=checkpoints_deleted,
                writes_deleted=writes_deleted,
                duration_ms=duration_ms,
            )
        
        except Exception:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.exception(
                "checkpoint_cleanup_failed",
                duration_ms=duration_ms,
            )
            raise


def get_checkpointer_manager() -> CheckpointerManager:
    """Return a singleton CheckpointerManager instance."""
    global _manager
    if _manager is None:
        _manager = CheckpointerManager()
    return _manager
