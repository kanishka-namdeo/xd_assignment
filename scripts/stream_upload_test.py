"""
Use streaming endpoint to upload documents and observe processing.
"""

import requests
import json
import time
from pathlib import Path
from typing import Iterator

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"
PROFILE_DIR = Path("D:/test_misc/xd_assignment/data/fresh_accounts/applicant_990945")

print("=" * 60)
print("STREAMING DOCUMENT UPLOAD TEST")
print("=" * 60)

# Documents to upload
doc_files = [
    ("emirates_id_front.png", "image/png"),
    ("emirates_id_back.png", "image/png"),
    ("bank_statement.pdf", "application/pdf"),
    ("credit_report.pdf", "application/pdf"),
    ("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("assets_liabilities.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("application_form.png", "image/png"),
]

# Build multipart form data
print("\n>>> Preparing file upload...")
files = []
for fname, mime in doc_files:
    fpath = PROFILE_DIR / fname
    if fpath.exists():
        files.append(("files", (fname, open(fpath, "rb"), mime)))
        print(f"  Added: {fname}")

# Use the streaming endpoint
print(f"\n>>> POST /applications/{APPLICATION_ID}/chat/stream")
print("  Sending all documents...")

start = time.time()

try:
    resp = requests.post(
        f"{BASE_URL}/applications/{APPLICATION_ID}/chat/stream",
        data={"text": "Here are all my required documents. Please process them."},
        files=files,
        stream=True,
        timeout=600,
    )

    print(f"  Response status: {resp.status_code}")
    print(f"  Headers: {dict(resp.headers)}")

    if resp.status_code == 200:
        print("\n>>> Streaming events:")
        event_count = 0
        for line in resp.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    data_str = decoded[6:]
                    if data_str == "[DONE]":
                        print("  [DONE]")
                        break
                    try:
                        event = json.loads(data_str)
                        event_count += 1
                        event_type = event.get("type", "unknown")
                        print(f"  Event {event_count}: type={event_type}")
                        if event_type in ("phase_transition", "processing_complete", "error"):
                            print(f"    Data: {json.dumps(event, indent=2)[:300]}")
                        if event_count > 50:
                            print("  ... (too many events, stopping)")
                            break
                    except json.JSONDecodeError:
                        print(f"  Raw: {decoded[:100]}")

    elapsed = time.time() - start
    print(f"\n  Total time: {elapsed:.1f}s")

except requests.exceptions.ReadTimeout:
    elapsed = time.time() - start
    print(f"\n  READ TIMEOUT after {elapsed:.1f}s")

    # Check application state
    print("\n>>> Checking application state...")
    state_resp = requests.get(
        f"{BASE_URL}/applications/{APPLICATION_ID}",
        timeout=30,
    )
    print(f"  State: {state_resp.text[:500]}")

except Exception as e:
    elapsed = time.time() - start
    print(f"\n  ERROR after {elapsed:.1f}s: {e}")

# Close file handles
for _, (_, fh, _) in files:
    fh.close()

print("\n>>> Final application state:")
resp = requests.get(
    f"{BASE_URL}/applications/{APPLICATION_ID}",
    timeout=30,
)
print(f"  {resp.text}")
