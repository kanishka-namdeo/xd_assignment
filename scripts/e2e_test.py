"""End-to-end test script for the 7-phase applicant flow."""
import asyncio
import json
from pathlib import Path
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
PROFILE_DIR = Path("data/test_applicants/divorced_employed_good_credit")


async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Auth
        print("=" * 60)
        print("Step 1: Authentication")
        profile = json.loads((PROFILE_DIR / "profile.json").read_text(encoding="utf-8"))
        identity_number = profile["applicant"]["identity_number"]
        print(f"  Identity: {identity_number}")

        r = await client.post(f"{BASE_URL}/auth/login", json={"emirates_id": identity_number})
        print(f"  Status: {r.status_code}")
        auth_data = r.json()
        print(f"  Response: {json.dumps(auth_data, indent=2)}")

        if r.status_code != 200:
            print("  FAIL: Auth failed")
            return

        app_id = auth_data["application_id"]
        print(f"  Application ID: {app_id}")
        print(f"  Current Phase: {auth_data['current_phase']}")

        # Step 2: Chat - intake
        print("\n" + "=" * 60)
        print("Step 2: Intake Chat")
        intake_text = (
            f"My name is {profile['applicant']['full_name_en']}, "
            f"DOB {profile['applicant']['date_of_birth']}, "
            f"nationality {profile['applicant']['nationality']}, "
            f"phone {profile['applicant']['contact_phone']}, "
            f"email {profile['applicant']['contact_email']}, "
            f"marital status {profile['applicant']['marital_status']}, "
            f"family size {profile['applicant']['family_size']}, "
            f"employment {profile['applicant']['employment_status']}, "
            f"employer {profile['applicant']['employer_name']}, "
            f"occupation {profile['applicant']['occupation']}, "
            f"housing {profile['applicant']['housing_status']}, "
            f"support category {profile['applicant']['support_category']}"
        )
        print(f"  Sending: {intake_text[:100]}...")

        r = await client.post(
            f"{BASE_URL}/applications/{app_id}/chat",
            data={"text": intake_text},
        )
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            chat_data = r.json()
            print(f"  Phase: {chat_data.get('phase')}")
            print(f"  Message: {chat_data.get('message', '')[:200]}")
            print(f"  Decision: {chat_data.get('decision')}")
            print(f"  Interrupt: {chat_data.get('interrupt')}")
        else:
            print(f"  Error: {r.text}")

        # Step 3: Upload documents
        print("\n" + "=" * 60)
        print("Step 3: Document Upload")
        doc_files = {
            "emirates_id_front.png": "image/png",
            "bank_statement.pdf": "application/pdf",
            "credit_report.pdf": "application/pdf",
            "application_form.png": "image/png",
        }
        files = []
        for fname, ftype in doc_files.items():
            fpath = PROFILE_DIR / fname
            if fpath.exists():
                files.append(("files", (fname, fpath.read_bytes(), ftype)))
                print(f"  Found: {fname} ({fpath.stat().st_size} bytes)")
            else:
                print(f"  MISSING: {fname}")

        if files:
            print(f"  Uploading {len(files)} files...")
            r = await client.post(
                f"{BASE_URL}/applications/{app_id}/chat",
                data={"text": "Here are my supporting documents."},
                files=files,
            )
            print(f"  Status: {r.status_code}")
            if r.status_code == 200:
                chat_data = r.json()
                print(f"  Phase: {chat_data.get('phase')}")
                print(f"  Message: {chat_data.get('message', '')[:200]}")
                print(f"  Documents: {len(chat_data.get('uploaded_documents', []))}")
                print(f"  Decision: {chat_data.get('decision')}")
            else:
                print(f"  Error: {r.text[:500]}")

        print("\n" + "=" * 60)
        print("E2E test complete")


if __name__ == "__main__":
    asyncio.run(main())
