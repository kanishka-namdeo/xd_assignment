"""Entry point for uvicorn with Windows asyncio compatibility."""
import sys
import asyncio

# Windows asyncio event loop compatibility for psycopg async
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

async def main():
    config = uvicorn.Config("src.main:app", host="127.0.0.1", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
