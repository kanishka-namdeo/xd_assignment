"""
Upload documents one at a time using the dedicated endpoint, then trigger processing.
"""

import requests
import time
import json
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"
PROFILE_DIR = Path("D:/test_misc/xd_assignment/data/fresh_accounts/applicant_990945")

print("=" * 60)
print("DOCUMENT UPLOAD AND PROCESS TEST")
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

# Upload each document using the dedicated endpoint
print("\n>>> Uploading documents one at a time...")
for fname, mime in doc_files:
    fpath = PROFILE_DIR / fname
    if not fpath.exists():
        print(f"  SKIP (not found): {fname}")
        continue

    print(f"  Uploading: {fname}")

    with open(fpath, "rb") as f:
        files = {"file": (fname, f, mime)}
        data = {"document_type": fname}  # hint for classification

        try:
            resp = requests.post(
                f"{BASE_URL}/applications/{APPLICATION_ID}/documents",
                files=files,
                data=data,
                timeout=60,
            )
            print(f"    Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"    Response: {resp.text[:200]}")
            else:
                print(f"    Response: {resp.text[:200]}")
        except Exception as e:
            print(f"    ERROR: {e}")

    time.sleep(0.5)

# Check current state
print("\n>>> Checking application state after uploads...")
resp = requests.get(
    f"{BASE_URL}/applications/{APPLICATION_ID}",
    timeout=30,
)
print(f"  State: {resp.text[:500]}")

# Now send a chat message with empty files to trigger processing
# But first, let's check what documents are already in the state
print("\n>>> Sending chat message to trigger processing...")

# The key insight: we need to send the files AGAIN so the graph sees them as new uploads
# OR we need to manually update the state

# Let's try sending a message with all files attached
print("  Sending all files again with a chat message...")

files = []
for fname, mime in doc_files:
    fpath = PROFILE_DIR / fname
    if fpath.exists():
        files.append(("files", (fname, open(fpath, "rb"), mime)))

try:
    resp = requests.post(
        f"{BASE_URL}/applications/{APPLICATION_ID}/chat",
        data={"text": "I have uploaded all my required documents. Please proceed with processing."},
        files=files,
        timeout=600,
    )
    print(f"\n  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:1000]}")
except requests.exceptions.ReadTimeout:
    print("\n  READ TIMEOUT after 600s")
    # Check state
    resp = requests.get(
        f"{BASE_URL}/applications/{APPLICATION_ID}",
        timeout=30,
    )
    print(f"  Current state: {resp.text[:500]}")
except Exception as e:
    print(f"\n  ERROR: {e}")

# Close file handles
for _, (_, fh, _) in files:
    fh.close()

print("\n>>> Final application state:")
resp = requests.get(
    f"{BASE_URL}/applications/{APPLICATION_ID}",
    timeout=30,
)
print(f"  {resp.text}")
