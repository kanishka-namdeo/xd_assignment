"""Test enablement with detailed error capture."""

import requests
import sys
import os

# Add project root
sys.path.insert(0, os.path.abspath("."))

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"

print(">>> Testing enablement endpoint with detailed error capture...")

# First, let's manually invoke the graph to see what happens
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test_enablement():
    from src.services.chat_service import ChatService
    from src.infrastructure.db.session import get_session_factory
    from src.config import settings

    factory = get_session_factory(settings)
    session = factory()

    try:
        chat_service = ChatService(session)
        result = await chat_service.handle_chat(
            application_id=APPLICATION_ID,
            text="What support am I eligible for?",
            file_paths=[],
        )
        print(f"SUCCESS: {result}")
        return result
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await session.close()

result = asyncio.run(test_enablement())

if result:
    print(f"\nMessage: {result.message[:200]}")
    print(f"Phase: {result.phase}")
    print(f"Recommendations: {result.enablement_recommendations}")
