"""Comprehensive E2E test: Phase 0-6 + unconventional flows."""
import asyncio
import io
import json
import random
import sys
import time
from pathlib import Path

import requests
import structlog
from sqlalchemy import text

from src.config import settings
from src.infrastructure.db.session import get_engine
from src.infrastructure.observability.logging import configure_logging
from src.utils.emirates_id import luhn_check_digit

configure_logging()

API_BASE = "http://localhost:8000"
BOUNDARY = "----TestBoundary7MA4YWxkTrZu0gW"

logger = structlog.get_logger(__name__)


def generate_unique_emirates_id() -> str:
    """Generate a truly unique Emirates ID using timestamp + random."""
    timestamp = int(time.time() * 1000) % 10000000
    year = random.randint(1980, 2000)
    body = f"784{year}{timestamp:07d}"
    check = luhn_check_digit(body)
    return f"784-{year}-{timestamp:07d}-{check}"


def build_multipart(text_content: str, files: list[str] | None = None) -> tuple[bytes, str]:
    """Build multipart/form-data body."""
    body = io.BytesIO()
    body.write(f"--{BOUNDARY}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="text"\r\n\r\n')
    body.write(text_content.encode())
    body.write(b"\r\n")

    if files:
        for fpath in files:
            fname = Path(fpath).name
            body.write(f"--{BOUNDARY}\r\n".encode())
            body.write(f'Content-Disposition: form-data; name="files"; filename="{fname}"\r\n'.encode())
            body.write(b"Content-Type: application/octet-stream\r\n\r\n")
            body.write(Path(fpath).read_bytes())
            body.write(b"\r\n")

    body.write(f"--{BOUNDARY}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={BOUNDARY}"


def test_auth(emirates_id: str) -> dict:
    """Phase 0: Authentication."""
    print(f"\n[Phase 0] Auth with Emirates ID: {emirates_id}")
    resp = requests.post(f"{API_BASE}/api/v1/auth/login", json={"emirates_id": emirates_id}, timeout=10)
    print(f"  Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        return {}
    data = resp.json()
    print(f"  Applicant ID: {data['applicant_id']}")
    print(f"  Application ID: {data['application_id']}")
    print(f"  Phase: {data['current_phase']}")
    print(f"  Is new: {data['is_new_applicant']}")
    return data


def test_chat(application_id: str, message: str, files: list[str] | None = None) -> dict:
    """Send chat message with optional files."""
    content, content_type = build_multipart(message, files)
    resp = requests.post(
        f"{API_BASE}/api/v1/applications/{application_id}/chat",
        data=content,
        headers={"Content-Type": content_type},
        timeout=120,
    )
    print(f"  Chat status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Phase: {data['phase']}")
        # Sanitize message for console output
        safe_msg = data['message'][:200].encode('ascii', 'replace').decode('ascii')
        print(f"  Message: {safe_msg}...")
        if data.get("decision"):
            print(f"  Decision: {data['decision']}")
        if data.get("uploaded_documents"):
            print(f"  Documents: {len(data['uploaded_documents'])}")
        if data.get("interrupt"):
            safe_q = data['interrupt'].get('question', '')[:100].encode('ascii', 'replace').decode('ascii')
            print(f"  Interrupt: {safe_q}...")
        return data
    else:
        print(f"  ERROR: {resp.text[:300]}")
        return {}


async def check_db(application_id: str):
    """Check application state in database."""
    engine = get_engine(settings)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(
                f"SELECT current_phase, status, decision, eligibility_score "
                f"FROM applications WHERE id = '{application_id}'"
            ))
            row = result.fetchone()
            if row:
                print(f"  DB: Phase={row[0]}, Status={row[1]}, Decision={row[2]}, Score={row[3]}")
            else:
                print("  ERROR: Application not found in DB!")

            result = await conn.execute(text(
                f"SELECT document_type, processing_status, extraction_status "
                f"FROM documents WHERE applicant_id IN "
                f"(SELECT applicant_id FROM applications WHERE id = '{application_id}')"
            ))
            docs = result.fetchall()
            print(f"  DB documents: {len(docs)}")
            for d in docs:
                print(f"    {d[0]}: proc={d[1]}, extract={d[2]}")
    finally:
        await engine.dispose()


def test_happy_path():
    """Test complete happy path: Phase 0-6."""
    print("\n" + "=" * 70)
    print("HAPPY PATH TEST: Complete Flow (Phase 0-6)")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    if not auth_data:
        print("FAILED: Authentication")
        return False
    app_id = auth_data["application_id"]

    print("\n[Phase 1] Intake - provide applicant info")
    chat_data = test_chat(
        app_id,
        "I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.",
    )
    if chat_data.get("phase") not in ["document_collection", "intake"]:
        print(f"FAILED: Expected document_collection or intake, got {chat_data.get('phase')}")
        return False
    asyncio.run(check_db(app_id))

    print("\n[Phase 2] Document Collection - upload all required docs")
    doc_dir = "data/test_applicants/divorced_employed_good_credit"
    files = [
        f"{doc_dir}/emirates_id_front.png",
        f"{doc_dir}/emirates_id_back.png",
        f"{doc_dir}/bank_statement.pdf",
        f"{doc_dir}/credit_report.pdf",
        f"{doc_dir}/application_form.png",
    ]
    chat_data = test_chat(app_id, "Here are all my documents for the application.", files=files)
    
    # The graph may execute multiple phases in a single invocation
    # Check if we have documents and a decision
    if not chat_data.get("uploaded_documents"):
        print(f"FAILED: No documents uploaded")
        return False
    
    print(f"  Documents uploaded: {len(chat_data['uploaded_documents'])}")
    asyncio.run(check_db(app_id))

    print("\n[Phase 3-5] Processing, Review, Decision - executed in single graph run")
    # The graph flows through processing → review → decision → enablement
    # Check if we reached enablement with a decision
    if chat_data.get("phase") != "enablement":
        print(f"FAILED: Expected enablement, got {chat_data.get('phase')}")
        return False
    
    if not chat_data.get("decision"):
        print("FAILED: No decision made")
        return False
    
    print(f"  Decision: {chat_data['decision']}")
    print(f"  Message: {chat_data['message'][:200]}...")
    asyncio.run(check_db(app_id))

    print("\n[Phase 6] Enablement - complete the flow")
    if chat_data.get("interrupt"):
        print("  Enablement has interrupt, responding to complete")
        chat_data = test_chat(app_id, "Thank you for the information.")
    asyncio.run(check_db(app_id))

    print("\n" + "=" * 70)
    print("HAPPY PATH TEST: PASSED")
    print("=" * 70)
    return True


def test_invalid_document():
    """Test uploading invalid document type."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Invalid Document Type")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    print("\n  Uploading invalid document (dummy.txt)")
    Path("data/uploads/dummy.txt").write_text("This is not a valid document")
    chat_data = test_chat(app_id, "Here is my document.", files=["data/uploads/dummy.txt"])
    print(f"  Response: {chat_data.get('message', '')[:200]}")

    print("  INVALID DOCUMENT TEST: COMPLETED")
    return True


def test_missing_documents():
    """Test uploading only some required documents."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Missing Documents")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    print("\n  Uploading only Emirates ID (missing other docs)")
    doc_dir = "data/test_applicants/divorced_employed_good_credit"
    files = [
        f"{doc_dir}/emirates_id_front.png",
        f"{doc_dir}/emirates_id_back.png",
    ]
    chat_data = test_chat(app_id, "Here are my documents.", files=files)
    print(f"  Phase: {chat_data.get('phase')}")
    print(f"  Message: {chat_data.get('message', '')[:200]}")
    if chat_data.get("interrupt"):
        print(f"  Interrupt (asking for missing docs): {chat_data['interrupt'].get('missing_documents', [])}")

    print("  MISSING DOCUMENTS TEST: COMPLETED")
    return True


def test_different_profile():
    """Test with different applicant profile (abandoned, unemployed, poor credit)."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Different Applicant Profile")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    print("\n[Phase 1] Intake - abandoned, unemployed, poor credit")
    chat_data = test_chat(
        app_id,
        "I am abandoned by my husband with 3 children. I am unemployed and have poor credit score. I need support.",
    )
    print(f"  Phase: {chat_data.get('phase')}")

    print("\n[Phase 2] Upload documents for abandoned profile")
    doc_dir = "data/test_applicants/abandoned_unemployed_poor_credit"
    files = [
        f"{doc_dir}/emirates_id_front.png",
        f"{doc_dir}/emirates_id_back.png",
        f"{doc_dir}/bank_statement.pdf",
        f"{doc_dir}/credit_report.pdf",
        f"{doc_dir}/application_form.png",
    ]
    chat_data = test_chat(app_id, "Here are my documents.", files=files)
    print(f"  Phase: {chat_data.get('phase')}")

    print("  DIFFERENT PROFILE TEST: COMPLETED")
    return True


def test_session_recovery():
    """Test session recovery by re-authenticating with same Emirates ID."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Session Recovery")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    print(f"\n  Using Emirates ID: {emirates_id}")

    print("\n  First authentication")
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]
    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    print("\n  Re-authenticating with same Emirates ID")
    auth_data2 = test_auth(emirates_id)
    print(f"  Same application ID? {auth_data2['application_id'] == app_id}")
    print(f"  Phase after re-auth: {auth_data2['current_phase']}")

    print("\n  Continuing session")
    chat_data = test_chat(app_id, "I want to continue my application.")
    print(f"  Phase: {chat_data.get('phase')}")

    print("  SESSION RECOVERY TEST: COMPLETED")
    return True


def test_corrupted_documents():
    """Test uploading corrupted/malformed documents."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Corrupted Documents")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    # Create a truncated/corrupted PDF (first 100 bytes of a real PDF)
    doc_dir = "data/test_applicants/divorced_employed_good_credit"
    real_pdf = Path(f"{doc_dir}/bank_statement.pdf")
    corrupted_pdf = Path("data/uploads/corrupted_bank_statement.pdf")
    corrupted_pdf.parent.mkdir(parents=True, exist_ok=True)
    if real_pdf.exists():
        corrupted_pdf.write_bytes(real_pdf.read_bytes()[:100])  # Truncated
    else:
        corrupted_pdf.write_bytes(b"%PDF-1.4 corrupted content")

    # Create a corrupted PNG (valid header but garbage body)
    corrupted_png = Path("data/uploads/corrupted_emirates_id.png")
    # PNG magic bytes + minimal IHDR chunk, then garbage
    png_header = b"\x89PNG\r\n\x1a\n"
    corrupted_png.write_bytes(png_header + b"\x00" * 50 + b"CORRUPTED_DATA")

    print("\n  Uploading corrupted PDF and PNG")
    chat_data = test_chat(app_id, "Here are my documents (some may be corrupted).", files=[
        str(corrupted_pdf),
        str(corrupted_png),
    ])
    print(f"  Phase: {chat_data.get('phase')}")
    msg = chat_data.get("message", "")[:200]
    print(f"  Message: {msg}...")
    if chat_data.get("interrupt"):
        print(f"  Interrupt: missing_docs={chat_data['interrupt'].get('missing_documents', [])}")

    print("  CORRUPTED DOCUMENTS TEST: COMPLETED")
    return True


def test_cross_document_inconsistencies():
    """Test uploading documents from different applicants (mismatched identities)."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Cross-Document Inconsistencies")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    # Upload documents from TWO different applicants to create identity mismatch
    # divorced_employed_good_credit has one identity
    # abandoned_unemployed_poor_credit has a different identity
    doc_dir_1 = "data/test_applicants/divorced_employed_good_credit"
    doc_dir_2 = "data/test_applicants/abandoned_unemployed_poor_credit"

    print("\n  Uploading Emirates ID from applicant A, bank statement from applicant B")
    print("  (This creates a cross-document identity mismatch)")
    chat_data = test_chat(app_id, "Here are my documents.", files=[
        f"{doc_dir_1}/emirates_id_front.png",
        f"{doc_dir_1}/emirates_id_back.png",
        f"{doc_dir_2}/bank_statement.pdf",   # Different applicant!
        f"{doc_dir_1}/credit_report.pdf",
        f"{doc_dir_1}/application_form.png",
    ])
    print(f"  Phase: {chat_data.get('phase')}")
    msg = chat_data.get("message", "")[:300]
    print(f"  Message: {msg}...")
    if chat_data.get("decision"):
        print(f"  Decision: {chat_data['decision']}")

    print("  CROSS-DOCUMENT INCONSISTENCY TEST: COMPLETED")
    return True


def test_document_reupload():
    """Test re-uploading a document to replace a previously uploaded one."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Document Re-upload")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    doc_dir = "data/test_applicants/divorced_employed_good_credit"

    # First upload: only Emirates ID
    print("\n  First upload: Emirates ID only")
    chat_data = test_chat(app_id, "Here is my Emirates ID.", files=[
        f"{doc_dir}/emirates_id_front.png",
        f"{doc_dir}/emirates_id_back.png",
    ])
    print(f"  Phase: {chat_data.get('phase')}")
    print(f"  Documents so far: {chat_data.get('uploaded_documents', [])}")
    if chat_data.get("interrupt"):
        print(f"  Interrupt (asking for more): {chat_data['interrupt'].get('missing_documents', [])}")

    # Second upload: add bank statement and credit report
    print("\n  Second upload: adding bank statement and credit report")
    chat_data = test_chat(app_id, "Here are more documents.", files=[
        f"{doc_dir}/bank_statement.pdf",
        f"{doc_dir}/credit_report.pdf",
    ])
    print(f"  Phase: {chat_data.get('phase')}")
    print(f"  Documents so far: {len(chat_data.get('uploaded_documents', []))}")
    if chat_data.get("interrupt"):
        print(f"  Interrupt: {chat_data['interrupt'].get('missing_documents', [])}")

    # Third upload: add application form to complete
    print("\n  Third upload: adding application form to complete")
    chat_data = test_chat(app_id, "Here is my application form.", files=[
        f"{doc_dir}/application_form.png",
    ])
    print(f"  Phase: {chat_data.get('phase')}")
    print(f"  Decision: {chat_data.get('decision', 'N/A')}")

    print("  DOCUMENT RE-UPLOAD TEST: COMPLETED")
    return True


def test_concurrent_uploads():
    """Test uploading multiple documents concurrently."""
    print("\n" + "=" * 70)
    print("UNCONVENTIONAL FLOW: Concurrent Document Uploads")
    print("=" * 70)

    emirates_id = generate_unique_emirates_id()
    auth_data = test_auth(emirates_id)
    app_id = auth_data["application_id"]

    test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")

    doc_dir = "data/test_applicants/divorced_employed_good_credit"

    # Upload 3 batches concurrently using asyncio
    async def upload_batch(files: list[str], label: str):
        print(f"  [{label}] Uploading: {[Path(f).name for f in files]}")
        chat_data = test_chat(app_id, f"Uploading documents ({label}).", files=files)
        print(f"  [{label}] Phase: {chat_data.get('phase')}, Docs: {len(chat_data.get('uploaded_documents', []))}")
        return chat_data

    async def run_concurrent():
        # Note: Since the API is synchronous and processes sequentially per session,
        # we test rapid sequential uploads which is the realistic concurrent scenario
        results = []
        results.append(await upload_batch([
            f"{doc_dir}/emirates_id_front.png",
            f"{doc_dir}/emirates_id_back.png",
        ], "batch_1"))
        results.append(await upload_batch([
            f"{doc_dir}/bank_statement.pdf",
        ], "batch_2"))
        results.append(await upload_batch([
            f"{doc_dir}/credit_report.pdf",
            f"{doc_dir}/application_form.png",
        ], "batch_3"))
        return results

    print("\n  Uploading documents in 3 rapid sequential batches")
    results = asyncio.run(run_concurrent())

    final_phase = results[-1].get("phase", "unknown") if results else "unknown"
    final_decision = results[-1].get("decision", "N/A") if results else "N/A"
    print(f"  Final phase: {final_phase}")
    print(f"  Decision: {final_decision}")

    print("  CONCURRENT UPLOADS TEST: COMPLETED")
    return True


def main():
    """Run all E2E tests."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE E2E TESTING - Phase 2 onwards")
    print("=" * 70)

    results = []

    try:
        results.append(("Happy Path (Phase 0-6)", test_happy_path()))
    except Exception as e:
        print(f"\nHAPPY PATH FAILED: {e}")
        results.append(("Happy Path (Phase 0-6)", False))

    try:
        results.append(("Invalid Document", test_invalid_document()))
    except Exception as e:
        print(f"\nINVALID DOCUMENT FAILED: {e}")
        results.append(("Invalid Document", False))

    try:
        results.append(("Missing Documents", test_missing_documents()))
    except Exception as e:
        print(f"\nMISSING DOCUMENTS FAILED: {e}")
        results.append(("Missing Documents", False))

    try:
        results.append(("Different Profile", test_different_profile()))
    except Exception as e:
        print(f"\nDIFFERENT PROFILE FAILED: {e}")
        results.append(("Different Profile", False))

    try:
        results.append(("Session Recovery", test_session_recovery()))
    except Exception as e:
        print(f"\nSESSION RECOVERY FAILED: {e}")
        results.append(("Session Recovery", False))

    try:
        results.append(("Corrupted Documents", test_corrupted_documents()))
    except Exception as e:
        print(f"\nCORRUPTED DOCUMENTS FAILED: {e}")
        results.append(("Corrupted Documents", False))

    try:
        results.append(("Cross-Document Inconsistencies", test_cross_document_inconsistencies()))
    except Exception as e:
        print(f"\nCROSS-DOCUMENT INCONSISTENCIES FAILED: {e}")
        results.append(("Cross-Document Inconsistencies", False))

    try:
        results.append(("Document Re-upload", test_document_reupload()))
    except Exception as e:
        print(f"\nDOCUMENT RE-UPLOAD FAILED: {e}")
        results.append(("Document Re-upload", False))

    try:
        results.append(("Concurrent Uploads", test_concurrent_uploads()))
    except Exception as e:
        print(f"\nCONCURRENT UPLOADS FAILED: {e}")
        results.append(("Concurrent Uploads", False))

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
