"""
Use streaming endpoint to observe phase transitions.
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"

print("=" * 60)
print("STREAMING E2E TEST")
print("=" * 60)

# Send a message to trigger processing via streaming
print("\n>>> Sending chat message to trigger processing...")

start = time.time()

# Try the regular chat endpoint first with a very long timeout
print("Using regular chat endpoint with 600s timeout...")

try:
    resp = requests.post(
        f"{BASE_URL}/applications/{APPLICATION_ID}/chat",
        data={"text": "I have uploaded all my required documents. Please proceed with processing my application."},
        timeout=600,
    )
    latency = (time.time() - start) * 1000

    print(f"\n  Status: {resp.status_code}")
    print(f"  Latency: {latency:.1f}ms")
    print(f"  Response: {resp.text[:2000]}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"\n  Phase: {data.get('phase', data.get('current_phase'))}")
        print(f"  Message: {data.get('message', '')[:300]}")
        print(f"  Interrupt: {data.get('interrupt')}")
        print(f"  Decision: {data.get('decision')}")
except requests.exceptions.ReadTimeout:
    print(f"\n  READ TIMEOUT after 600s")
    # Check application state
    state_resp = requests.get(
        f"{BASE_URL}/applications/{APPLICATION_ID}",
        timeout=30,
    )
    print(f"  Current state: {state_resp.text[:500]}")
except Exception as e:
    print(f"\n  ERROR: {e}")

print("\n>>> Checking final application state...")
state_resp = requests.get(
    f"{BASE_URL}/applications/{APPLICATION_ID}",
    timeout=30,
)
print(f"  State: {state_resp.text}")
