"""
Long-running streaming test with event observation.
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"
PROFILE_DIR = Path("D:/test_misc/xd_assignment/data/fresh_accounts/applicant_990945")

print("=" * 60)
print("LONG STREAMING TEST")
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
files = []
for fname, mime in doc_files:
    fpath = PROFILE_DIR / fname
    if fpath.exists():
        files.append(("files", (fname, open(fpath, "rb"), mime)))

print(f"\n>>> Sending {len(files)} documents via streaming endpoint...")
print("  This may take several minutes for processing...")

start = time.time()

try:
    resp = requests.post(
        f"{BASE_URL}/applications/{APPLICATION_ID}/chat/stream",
        data={"text": "Here are all my required documents. Please process them."},
        files=files,
        stream=True,
        timeout=900,  # 15 minutes
    )

    print(f"  Response status: {resp.status_code}")

    if resp.status_code == 200:
        print("\n>>> Streaming events (waiting for processing to complete):")
        event_count = 0
        last_event_time = time.time()
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
                        now = time.time()
                        elapsed = now - start
                        print(f"  [{elapsed:.1f}s] Event {event_count}: type={event_type}")

                        # Print key event details
                        if event_type in ("phase_transition", "processing_complete", "extraction_complete", "validation_complete", "error", "node_enter", "node_exit"):
                            print(f"    Data: {json.dumps(event, indent=2)[:500]}")

                        if event_count > 100:
                            print("  ... (too many events)")
                            break
                    except json.JSONDecodeError:
                        print(f"  Raw: {decoded[:100]}")

    elapsed = time.time() - start
    print(f"\n  Total streaming time: {elapsed:.1f}s")
    print(f"  Total events received: {event_count}")

except requests.exceptions.ReadTimeout:
    elapsed = time.time() - start
    print(f"\n  READ TIMEOUT after {elapsed:.1f}s")

except Exception as e:
    elapsed = time.time() - start
    print(f"\n  ERROR after {elapsed:.1f}s: {e}")
    import traceback
    traceback.print_exc()

# Close file handles
for _, (_, fh, _) in files:
    fh.close()

# Check final state
print("\n>>> Final application state:")
try:
    resp = requests.get(
        f"{BASE_URL}/applications/{APPLICATION_ID}",
        timeout=30,
    )
    print(f"  {resp.text}")
except Exception as e:
    print(f"  Error checking state: {e}")
