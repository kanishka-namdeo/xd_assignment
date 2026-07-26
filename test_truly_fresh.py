"""Fresh E2E test with truly new applicant."""
import requests
import json
import asyncio
import random
from pathlib import Path
from sqlalchemy import text
from src.infrastructure.db.session import get_engine
from src.config import settings
from src.utils.emirates_id import luhn_check_digit

API_BASE = "http://localhost:8000"

def generate_new_emirates_id() -> str:
    """Generate a unique Emirates ID."""
    year = random.randint(1980, 2000)
    seq = random.randint(1000000, 9999999)
    body = f"784{year}{seq}"
    check = luhn_check_digit(body)
    return f"784-{year}-{seq}-{check}"

def test_auth(emirates_id: str) -> dict:
    """Test authentication and return response data."""
    resp = requests.post(f"{API_BASE}/api/v1/auth/login", json={"emirates_id": emirates_id})
    print(f"Auth status: {resp.status_code}")
    data = resp.json()
    print(f"  Emirates ID: {emirates_id}")
    print(f"  Applicant: {data['applicant_id']}")
    print(f"  Application: {data['application_id']}")
    print(f"  Phase: {data['current_phase']}")
    print(f"  Is new: {data['is_new_applicant']}")
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
    
    resp = requests.post(
        f"{API_BASE}/api/v1/applications/{application_id}/chat",
        data=content,
        headers={"Content-Type": content_type},
        timeout=120
    )
    print(f"Chat status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Phase: {data['phase']}")
        print(f"  Message: {data['message'][:150]}...")
        if data.get('decision'):
            print(f"  Decision: {data['decision']}")
        if data.get('uploaded_documents'):
            print(f"  Documents: {len(data['uploaded_documents'])}")
        return data
    else:
        print(f"  Error: {resp.text[:300]}")
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
                print(f"DB check - Phase: {row[0]}, Status: {row[1]}, Decision: {row[2]}, Score: {row[3]}")
            else:
                print("ERROR: Application not found in DB!")
            
            # Check documents
            result = await conn.execute(text(
                f"SELECT document_type, processing_status, extraction_status "
                f"FROM documents WHERE applicant_id IN "
                f"(SELECT applicant_id FROM applications WHERE id = '{application_id}')"
            ))
            docs = result.fetchall()
            print(f"DB documents: {len(docs)}")
            for d in docs:
                print(f"  {d[0]}: proc={d[1]}, extract={d[2]}")
    finally:
        await engine.dispose()

def main():
    print("=" * 60)
    print("Fresh E2E Flow Test (Truly New Applicant)")
    print("=" * 60)
    
    # Generate new Emirates ID
    emirates_id = generate_new_emirates_id()
    
    # Step 1: Auth with completely new Emirates ID
    print("\n--- Step 1: Authentication (New Applicant) ---")
    auth_data = test_auth(emirates_id)
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
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
