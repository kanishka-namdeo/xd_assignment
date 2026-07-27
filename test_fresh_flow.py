"""Fresh E2E test with new applicant after commit fix."""
import time

import requests
import json
import asyncio
import structlog
from pathlib import Path
from sqlalchemy import text
from src.infrastructure.db.session import get_engine
from src.config import settings
from src.infrastructure.observability.logging import configure_logging

configure_logging()

logger = structlog.get_logger(__name__)

API_BASE = "http://localhost:8000"

def test_auth(emirates_id: str) -> dict:
    """Test authentication and return response data."""
    start = time.time()
    resp = requests.post(f"{API_BASE}/api/v1/auth/login", json={"emirates_id": emirates_id})
    duration_ms = (time.time() - start) * 1000
    print(f"Auth status: {resp.status_code}")
    data = resp.json()
    print(f"  Applicant: {data['applicant_id']}")
    print(f"  Application: {data['application_id']}")
    print(f"  Phase: {data['current_phase']}")
    print(f"  Is new: {data['is_new_applicant']}")
    logger.info("auth_login", status_code=resp.status_code, duration_ms=round(duration_ms, 2), application_id=data.get("application_id"), is_new=data.get("is_new_applicant"))
    return data

def test_chat(application_id: str, message: str, files: list[str] | None = None) -> dict:
    """Test chat endpoint with optional file uploads."""
    boundary = "----TestBoundary"

    if files:
        import io
        body = io.BytesIO()
        text_part = f'--{boundary}\r\nContent-Disposition: form-data; name="text"\r\n\r\n{message}\r\n'
        body.write(text_part.encode('utf-8'))

        for fpath in files:
            fname = Path(fpath).name
            header = f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{fname}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            body.write(header.encode('utf-8'))
            body.write(Path(fpath).read_bytes())
            body.write(b'\r\n')

        body.write(f'--{boundary}--\r\n'.encode('utf-8'))
        content = body.getvalue()
        content_type = f"multipart/form-data; boundary={boundary}"
    else:
        text_part = f'--{boundary}\r\nContent-Disposition: form-data; name="text"\r\n\r\n{message}\r\n--{boundary}--\r\n'
        content = text_part.encode('utf-8')
        content_type = f"multipart/form-data; boundary={boundary}"

    start = time.time()
    resp = requests.post(
        f"{API_BASE}/api/v1/applications/{application_id}/chat",
        data=content,
        headers={"Content-Type": content_type},
        timeout=120
    )
    duration_ms = (time.time() - start) * 1000
    print(f"Chat status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Phase: {data['phase']}")
        print(f"  Message: {data['message'][:150]}...")
        if data.get('decision'):
            print(f"  Decision: {data['decision']}")
        if data.get('uploaded_documents'):
            print(f"  Documents: {len(data['uploaded_documents'])}")
        logger.info("chat_message", application_id=application_id, status_code=resp.status_code, duration_ms=round(duration_ms, 2), phase=data.get("phase"), document_count=len(data.get('uploaded_documents', [])))
        return data
    else:
        print(f"  Error: {resp.text[:300]}")
        logger.warning("chat_error", application_id=application_id, status_code=resp.status_code, duration_ms=round(duration_ms, 2))
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
                logger.info("db_state_check", application_id=application_id, phase=row[0], status=row[1], decision=row[2], eligibility_score=row[3])
                print(f"DB check - Phase: {row[0]}, Status: {row[1]}, Decision: {row[2]}, Score: {row[3]}")
            else:
                logger.warning("application_not_found", application_id=application_id)
                print("ERROR: Application not found in DB!")

            # Check documents
            result = await conn.execute(text(
                f"SELECT document_type, processing_status, extraction_status "
                f"FROM documents WHERE applicant_id IN "
                f"(SELECT applicant_id FROM applications WHERE id = '{application_id}')"
            ))
            docs = result.fetchall()
            logger.info("db_documents_check", application_id=application_id, document_count=len(docs))
            print(f"DB documents: {len(docs)}")
            for d in docs:
                print(f"  {d[0]}: proc={d[1]}, extract={d[2]}")
    finally:
        await engine.dispose()

def main():
    print("=" * 60)
    print("Fresh E2E Flow Test (New Applicant)")
    print("=" * 60)

    start_time = time.time()
    logger.info("test_start", script="test_fresh_flow")

    # Step 1: Auth with completely new Emirates ID
    print("\n--- Step 1: Authentication (New Applicant) ---")
    auth_data = test_auth("784-1985-9998887-4")
    app_id = auth_data['application_id']

    # Step 2: Intake
    print("\n--- Step 2: Intake ---")
    chat_data = test_chat(app_id, "I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.")

    # Check DB after intake
    print("\n--- DB Check after Intake ---")
    asyncio.run(check_db(app_id))

    # Step 3: Document upload
    print("\n--- Step 3: Document Upload ---")
    doc_dir = "data/test_applicants/divorced_employed_good_credit"
    files = [
        f"{doc_dir}/emirates_id_front.png",
        f"{doc_dir}/emirates_id_back.png",
        f"{doc_dir}/bank_statement.pdf",
        f"{doc_dir}/credit_report.pdf",
        f"{doc_dir}/application_form.png",
    ]
    chat_data = test_chat(app_id, "Here are all my documents for the application.", files=files)

    # Check DB after processing
    print("\n--- DB Check after Processing ---")
    asyncio.run(check_db(app_id))

    duration_ms = (time.time() - start_time) * 1000
    logger.info("e2e_flow_complete", application_id=app_id, duration_ms=round(duration_ms, 2))

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    logger.info("test_complete", script="test_fresh_flow", application_id=app_id, duration_ms=round(duration_ms, 2))

if __name__ == "__main__":
    main()
