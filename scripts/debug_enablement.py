"""Debug enablement phase error."""

import requests
import asyncio
import sys
import os

# Fix Windows asyncio event loop for psycopg
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add project root to path
sys.path.insert(0, os.path.abspath("."))

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"

print(">>> Checking application state...")
resp = requests.get(f"{BASE_URL}/applications/{APPLICATION_ID}")
app = resp.json()
print(f"  Phase: {app.get('current_phase')}")
print(f"  Decision: {app.get('decision')}")
print(f"  Score: {app.get('eligibility_score')}")

# Try to invoke the graph directly to see the error
print("\n>>> Invoking graph directly...")

async def test_graph():
    from src.services.agent_runner import run
    from src.agents.state import ApplicantState

    # Build graph input from application state
    graph_input = {
        "messages": [{"role": "user", "content": "What support am I eligible for?"}],
        "current_phase": "enablement",
        "applicant_id": str(app["applicant_id"]),
        "application_id": APPLICATION_ID,
        "uploaded_files": [],
        "decision": app.get("decision", "manual_review"),
        "eligibility_score": app.get("eligibility_score", 0.73),
        "applicant_info": {
            "support_category": "divorced",
            "family_size": 1,
        },
    }

    try:
        result = await run(graph_input)
        print(f"  Result keys: {list(result.keys())}")
        print(f"  Phase: {result.get('current_phase')}")
        print(f"  Messages: {result.get('messages', [])}")
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

# Run the async test
result = asyncio.run(test_graph())

if result:
    print("\n>>> SUCCESS: Enablement phase works")
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        content = last_msg.content if hasattr(last_msg, "content") else last_msg.get("content", "")
        print(f"  Agent response: {content[:300]}")
else:
    print("\n>>> FAILED: Enablement phase has an error")
