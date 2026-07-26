"""Reset application state for fresh E2E test."""
import asyncio
import sys
import psycopg
from src.config import settings

# Windows asyncio event loop compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def reset():
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("localhost", "127.0.0.1")
    conn = await psycopg.AsyncConnection.connect(db_url, autocommit=True)
    async with conn.cursor() as cur:
        thread_id = "62dd82ca-2eb8-459c-8f05-fa90fe29f3c2"
        await cur.execute(f"DELETE FROM checkpoints WHERE thread_id = '{thread_id}'")
        await cur.execute(f"DELETE FROM checkpoint_writes WHERE thread_id = '{thread_id}'")
        await cur.execute(f"DELETE FROM checkpoint_blobs WHERE thread_id = '{thread_id}'")
        await cur.execute(f"UPDATE applications SET state_snapshot = NULL, current_phase = 'intake' WHERE id = '{thread_id}'")
        print("Reset complete")
    await conn.close()


asyncio.run(reset())
