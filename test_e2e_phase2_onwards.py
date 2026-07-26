"""Comprehensive E2E testing from Phase 2 onwards."""

import json
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000/api/v1"
TEST_DATA_DIR = Path("data/test_applicants/divorced_employed_good_credit")


def load_profile() -> dict:
    """Load test applicant profile."""
    profile_path = TEST_DATA_DIR / "profile.json"
    with open(profile_path) as f:
        return json.load(f)


def phase0_authenticate(emirates_id: str) -> dict:
    """Phase 0: Authenticate applicant."""
    print("\n" + "=" * 80)
    print("PHASE 0: AUTHENTICATION")
    print("=" * 80)
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"emirates_id": emirates_id},
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return None
    
    data = response.json()
    print(f"Applicant ID: {data['applicant_id']}")
    print(f"Application ID: {data['application_id']}")
    print(f"Is New: {data['is_new_applicant']}")
    print(f"Current Phase: {data['current_phase']}")
    
    return data


def phase1_intake(application_id: str, profile: dict) -> dict:
    """Phase 1: Intake - provide applicant information."""
    print("\n" + "=" * 80)
    print("PHASE 1: INTAKE")
    print("=" * 80)
    
    applicant = profile["applicant"]
    
    # Build intake message with all required information
    intake_msg = f"""
I am applying for social support.

Personal Information:
- Full Name (English): {applicant['full_name_en']}
- Full Name (Arabic): {applicant['full_name_ar']}
- Date of Birth: {applicant['date_of_birth']}
- Nationality: {applicant['nationality']}
- Gender: {applicant['gender']}
- Marital Status: {applicant['marital_status']}
- Family Size: {applicant['family_size']}
- Phone: {applicant['contact_phone']}
- Email: {applicant['contact_email']}
- Address: {applicant['address']['street']}, {applicant['address']['city']}, {applicant['address']['emirate']}
- PO Box: {applicant['address']['po_box']}

Employment:
- Status: {applicant['employment_status']}
- Employer: {applicant['employer_name']}
- Occupation: {applicant['occupation']}
- Monthly Salary: {applicant['monthly_salary']} AED
- Other Income: {applicant['other_income']} AED

Housing:
- Status: {applicant['housing_status']}
- Monthly Rent: {applicant['monthly_rent']} AED

Support Category: {applicant['support_category']}

I confirm all information is accurate and I have signed the declaration.
"""
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": intake_msg.strip()},
        files=[],
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return None
    
    data = response.json()
    print(f"Response: {data['message'][:200]}...")
    print(f"Phase: {data['phase']}")
    print(f"Documents: {len(data['uploaded_documents'])}")
    
    return data


def phase2_upload_documents(application_id: str) -> dict:
    """Phase 2: Upload all required documents."""
    print("\n" + "=" * 80)
    print("PHASE 2: DOCUMENT COLLECTION")
    print("=" * 80)
    
    documents = [
        ("emirates_id_front.png", "emirates_id"),
        ("emirates_id_back.png", "emirates_id"),
        ("bank_statement.pdf", "bank_statement"),
        ("credit_report.pdf", "credit_report"),
        ("application_form.png", "application_form"),
    ]
    
    results = []
    
    for filename, doc_type in documents:
        file_path = TEST_DATA_DIR / filename
        
        if not file_path.exists():
            print(f"WARNING: {filename} not found, skipping")
            continue
        
        print(f"\nUploading {filename} ({doc_type})...")
        
        start = time.time()
        with open(file_path, "rb") as f:
            files = {"files": (filename, f, "application/octet-stream")}
            response = requests.post(
                f"{BASE_URL}/applications/{application_id}/chat",
                data={"text": f"I am uploading my {doc_type.replace('_', ' ')}", "document_type": doc_type},
                files=files,
            )
        duration_ms = (time.time() - start) * 1000
        
        print(f"  Status: {response.status_code}")
        print(f"  Duration: {duration_ms:.2f}ms")
        
        if response.status_code != 200:
            print(f"  ERROR: {response.text}")
            continue
        
        data = response.json()
        print(f"  Phase: {data['phase']}")
        print(f"  Documents: {len(data['uploaded_documents'])}")
        
        results.append({
            "filename": filename,
            "doc_type": doc_type,
            "response": data,
        })
    
    return results[-1] if results else None


def phase3_process_documents(application_id: str) -> dict:
    """Phase 3: Trigger document processing and extraction."""
    print("\n" + "=" * 80)
    print("PHASE 3: DOCUMENT PROCESSING")
    print("=" * 80)
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I have uploaded all required documents. Please process them."},
        files=[],
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return None
    
    data = response.json()
    print(f"Response: {data['message'][:300]}...")
    print(f"Phase: {data['phase']}")
    
    return data


def phase4_review(application_id: str) -> dict:
    """Phase 4: Review extracted data."""
    print("\n" + "=" * 80)
    print("PHASE 4: REVIEW")
    print("=" * 80)
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I have reviewed the extracted information and confirm it is correct."},
        files=[],
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return None
    
    data = response.json()
    print(f"Response: {data['message'][:300]}...")
    print(f"Phase: {data['phase']}")
    
    return data


def phase5_decision(application_id: str) -> dict:
    """Phase 5: Get eligibility decision."""
    print("\n" + "=" * 80)
    print("PHASE 5: DECISION")
    print("=" * 80)
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "Please provide the eligibility decision."},
        files=[],
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return None
    
    data = response.json()
    print(f"Response: {data['message'][:300]}...")
    print(f"Phase: {data['phase']}")
    print(f"Decision: {data.get('decision')}")
    
    if data.get("decision_card"):
        print(f"Decision Card: {json.dumps(data['decision_card'], indent=2)}")
    
    return data


def phase6_enablement(application_id: str) -> dict:
    """Phase 6: Get enablement recommendations."""
    print("\n" + "=" * 80)
    print("PHASE 6: ENABLEMENT")
    print("=" * 80)
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "What benefits and support are available to me?"},
        files=[],
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return None
    
    data = response.json()
    print(f"Response: {data['message'][:500]}...")
    print(f"Phase: {data['phase']}")
    
    return data


def test_invalid_document(application_id: str):
    """Test uploading invalid document type."""
    print("\n" + "=" * 80)
    print("UNCONVENTIONAL FLOW: Invalid Document Type")
    print("=" * 80)
    
    # Create a dummy text file
    dummy_file = Path("data/test_applicants/dummy.txt")
    dummy_file.write_text("This is not a valid document")
    
    start = time.time()
    with open(dummy_file, "rb") as f:
        files = {"files": ("dummy.txt", f, "text/plain")}
        response = requests.post(
            f"{BASE_URL}/applications/{application_id}/chat",
            data={"text": "Here is my document"},
            files=files,
        )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    print(f"Response: {response.json().get('message', '')[:200]}")
    
    dummy_file.unlink()


def test_missing_documents(application_id: str):
    """Test proceeding with missing required documents."""
    print("\n" + "=" * 80)
    print("UNCONVENTIONAL FLOW: Missing Documents")
    print("=" * 80)
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I don't have all the documents. Can I proceed anyway?"},
        files=[],
    )
    duration_ms = (time.time() - start) * 1000
    
    print(f"Status: {response.status_code}")
    print(f"Duration: {duration_ms:.2f}ms")
    print(f"Response: {response.json().get('message', '')[:300]}")


def main():
    """Run comprehensive E2E tests."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE E2E TESTING - PHASE 2 ONWARDS")
    print("=" * 80)
    
    # Load profile
    profile = load_profile()
    emirates_id = profile["applicant"]["identity_number"]
    print(f"\nTest Profile: {profile['profile_name']}")
    print(f"Emirates ID: {emirates_id}")
    print(f"Expected Decision: {profile['expected_decision']}")
    
    # Phase 0: Authentication
    auth_data = phase0_authenticate(emirates_id)
    if not auth_data:
        print("\nFATAL: Authentication failed")
        return
    
    application_id = auth_data["application_id"]
    
    # Phase 1: Intake
    intake_data = phase1_intake(application_id, profile)
    if not intake_data:
        print("\nFATAL: Intake failed")
        return
    
    # Phase 2: Document Upload
    upload_data = phase2_upload_documents(application_id)
    if not upload_data:
        print("\nFATAL: Document upload failed")
        return
    
    # Phase 3: Document Processing
    process_data = phase3_process_documents(application_id)
    if not process_data:
        print("\nFATAL: Document processing failed")
        return
    
    # Phase 4: Review
    review_data = phase4_review(application_id)
    if not review_data:
        print("\nFATAL: Review failed")
        return
    
    # Phase 5: Decision
    decision_data = phase5_decision(application_id)
    if not decision_data:
        print("\nFATAL: Decision failed")
        return
    
    # Phase 6: Enablement
    enablement_data = phase6_enablement(application_id)
    if not enablement_data:
        print("\nFATAL: Enablement failed")
        return
    
    # Unconventional flows
    print("\n" + "=" * 80)
    print("TESTING UNCONVENTIONAL FLOWS")
    print("=" * 80)
    
    test_invalid_document(application_id)
    test_missing_documents(application_id)
    
    print("\n" + "=" * 80)
    print("E2E TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
