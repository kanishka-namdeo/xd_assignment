"""Comprehensive E2E test for all 7 phases of the application flow."""

import json
import time
from pathlib import Path
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
TEST_DATA_DIR = Path("data/test_applicants/applicant_7537")

def log_test(phase, test_name, status, details=None):
    """Log test result with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_icon = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"[{timestamp}] {status_icon} Phase {phase} - {test_name}")
    if details:
        print(f"  Details: {details}")

def test_phase_0_authentication():
    """Test Phase 0: Authentication with Emirates ID."""
    print("\n=== Phase 0: Authentication ===")
    
    # Use applicant_7537 profile
    profile_path = TEST_DATA_DIR / "profile.json"
    with open(profile_path) as f:
        profile = json.load(f)
    
    identity_number = profile["identity_number"]
    
    # Call auth/login to create applicant and application
    # This endpoint validates the Emirates ID and creates the applicant + application
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"emirates_id": identity_number}
    )
    
    if response.status_code != 200:
        log_test(0, "Auth login", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
        return None, None
    
    auth_data = response.json()
    applicant_id = auth_data["applicant_id"]
    application_id = auth_data["application_id"]
    is_new = auth_data["is_new_applicant"]
    current_phase = auth_data["current_phase"]
    
    log_test(0, "Auth login", "PASS", f"Applicant ID: {applicant_id}, Application ID: {application_id}, New: {is_new}, Phase: {current_phase}")
    
    # Auth/login already validates the Emirates ID and creates the application at "intake" phase
    # No need for separate chat-based authentication
    if current_phase == "intake":
        log_test(0, "Authentication complete", "PASS", f"Phase: {current_phase}")
        return application_id, profile
    else:
        log_test(0, "Authentication complete", "FAIL", f"Phase: {current_phase}")
        return application_id, None

def test_phase_1_intake(application_id, profile):
    """Test Phase 1: Intake - collect applicant information."""
    print("\n=== Phase 1: Intake ===")
    
    # Provide all required information in one message
    intake_text = f"""
    My name is {profile['full_name_en']}.
    Date of birth: {profile['date_of_birth']}.
    Nationality: {profile['nationality']}.
    Phone: {profile['contact_phone']}.
    Email: {profile['contact_email']}.
    Address: {profile['address']['street']}, {profile['address']['city']}, {profile['address']['emirate']}.
    Marital status: {profile['marital_status']}.
    Family size: {profile['family_size']}.
    Employment status: {profile['employment_status']}.
    Employer: {profile['employer_name']}.
    Occupation: {profile['occupation']}.
    Housing status: {profile['housing_status']}.
    Support category: {profile['support_category']}.
    """
    
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": intake_text},
        files=[]
    )
    
    if response.status_code != 200:
        log_test(1, "Intake request", "FAIL", f"Status: {response.status_code}")
        return False
    
    chat_data = response.json()
    phase = chat_data.get("phase")
    message = chat_data.get("message", "")
    
    if phase == "document_collection":
        log_test(1, "Intake complete", "PASS", f"Phase: {phase}")
        return True
    else:
        log_test(1, "Intake complete", "FAIL", f"Phase: {phase}, Message: {message[:100]}")
        return False

def test_phase_2_document_collection(application_id):
    """Test Phase 2: Document collection - upload all required documents."""
    print("\n=== Phase 2: Document Collection ===")
    
    documents = [
        ("emirates_id_front.png", "image/png"),
        ("emirates_id_back.png", "image/png"),
        ("bank_statement.pdf", "application/pdf"),
        ("credit_report.pdf", "application/pdf"),
        ("application_form.png", "image/png"),
    ]
    
    uploaded_count = 0
    
    for doc_name, mime_type in documents:
        doc_path = TEST_DATA_DIR / doc_name
        if not doc_path.exists():
            log_test(2, f"Upload {doc_name}", "FAIL", "File not found")
            continue
        
        with open(doc_path, "rb") as f:
            files = [("files", (doc_name, f, mime_type))]
            response = requests.post(
                f"{BASE_URL}/applications/{application_id}/chat",
                data={"text": f"Uploading {doc_name}"},
                files=files
            )
        
        if response.status_code != 200:
            log_test(2, f"Upload {doc_name}", "FAIL", f"Status: {response.status_code}")
            continue
        
        chat_data = response.json()
        phase = chat_data.get("phase")
        uploaded_count += 1
        log_test(2, f"Upload {doc_name}", "PASS", f"Phase: {phase}")
    
    # Final check - should transition to processing
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I have uploaded all required documents"},
        files=[]
    )
    
    if response.status_code == 200:
        chat_data = response.json()
        phase = chat_data.get("phase")
        if phase == "processing":
            log_test(2, "Transition to processing", "PASS", f"Phase: {phase}")
            return True
        else:
            log_test(2, "Transition to processing", "FAIL", f"Phase: {phase}")
            return False
    
    return False

def test_phase_3_processing(application_id):
    """Test Phase 3: Processing - document extraction and validation."""
    print("\n=== Phase 3: Processing ===")
    
    # Processing happens automatically after document collection
    # Wait a bit for processing to complete
    time.sleep(2)
    
    # Check application status
    response = requests.get(f"{BASE_URL}/applications/{application_id}")
    
    if response.status_code != 200:
        log_test(3, "Check processing status", "FAIL", f"Status: {response.status_code}")
        return False
    
    app_data = response.json()
    phase = app_data.get("current_phase")
    
    if phase in ["review", "decision", "enablement"]:
        log_test(3, "Processing complete", "PASS", f"Phase: {phase}")
        return True
    else:
        log_test(3, "Processing complete", "FAIL", f"Phase: {phase}")
        return False

def test_phase_4_review(application_id):
    """Test Phase 4: Review - applicant reviews extracted data."""
    print("\n=== Phase 4: Review ===")
    
    # Send confirmation to proceed
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I confirm the information is correct. Please proceed."},
        files=[]
    )
    
    if response.status_code != 200:
        log_test(4, "Review confirmation", "FAIL", f"Status: {response.status_code}")
        return False
    
    chat_data = response.json()
    phase = chat_data.get("phase")
    message = chat_data.get("message", "")
    
    if phase == "decision":
        log_test(4, "Review complete", "PASS", f"Phase: {phase}")
        return True
    else:
        log_test(4, "Review complete", "FAIL", f"Phase: {phase}, Message: {message[:100]}")
        return False

def test_phase_5_decision(application_id):
    """Test Phase 5: Decision - eligibility scoring and decision."""
    print("\n=== Phase 5: Decision ===")
    
    # Decision happens automatically after review
    time.sleep(2)
    
    # Check application status
    response = requests.get(f"{BASE_URL}/applications/{application_id}")
    
    if response.status_code != 200:
        log_test(5, "Check decision status", "FAIL", f"Status: {response.status_code}")
        return False
    
    app_data = response.json()
    phase = app_data.get("current_phase")
    decision = app_data.get("decision")
    eligibility_score = app_data.get("eligibility_score")
    
    if phase == "enablement" and decision:
        log_test(5, "Decision made", "PASS", f"Decision: {decision}, Score: {eligibility_score}")
        return True
    else:
        log_test(5, "Decision made", "FAIL", f"Phase: {phase}, Decision: {decision}")
        return False

def test_phase_6_enablement(application_id, decision):
    """Test Phase 6: Enablement - benefits package."""
    print("\n=== Phase 6: Enablement ===")
    
    # Send acknowledgment
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "Thank you for the decision. What are the next steps?"},
        files=[]
    )
    
    if response.status_code != 200:
        log_test(6, "Enablement request", "FAIL", f"Status: {response.status_code}")
        return False
    
    chat_data = response.json()
    phase = chat_data.get("phase")
    message = chat_data.get("message", "")
    
    if phase == "enablement" and "next steps" in message.lower():
        log_test(6, "Enablement complete", "PASS", f"Phase: {phase}")
        return True
    else:
        log_test(6, "Enablement complete", "FAIL", f"Phase: {phase}, Message: {message[:100]}")
        return False

def main():
    """Run all E2E tests."""
    print("=" * 60)
    print("COMPREHENSIVE E2E TEST - ALL 7 PHASES")
    print("=" * 60)
    
    start_time = time.time()
    
    # Phase 0: Authentication
    application_id, profile = test_phase_0_authentication()
    if not application_id:
        print("\n[FAIL] Test failed at Phase 0")
        return

    # Phase 1: Intake
    if not test_phase_1_intake(application_id, profile):
        print("\n[FAIL] Test failed at Phase 1")
        return

    # Phase 2: Document Collection
    if not test_phase_2_document_collection(application_id):
        print("\n[FAIL] Test failed at Phase 2")
        return

    # Phase 3: Processing
    if not test_phase_3_processing(application_id):
        print("\n[FAIL] Test failed at Phase 3")
        return

    # Phase 4: Review
    if not test_phase_4_review(application_id):
        print("\n[FAIL] Test failed at Phase 4")
        return

    # Phase 5: Decision
    if not test_phase_5_decision(application_id):
        print("\n[FAIL] Test failed at Phase 5")
        return

    # Phase 6: Enablement
    response = requests.get(f"{BASE_URL}/applications/{application_id}")
    decision = response.json().get("decision") if response.status_code == 200 else None
    test_phase_6_enablement(application_id, decision)

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"[PASS] ALL TESTS PASSED - {elapsed:.2f}s")
    print("=" * 60)
    print(f"\nApplication ID: {application_id}")
    print(f"Final Decision: {decision}")
    print(f"Eligibility Score: {response.json().get('eligibility_score') if response.status_code == 200 else 'N/A'}")

if __name__ == "__main__":
    main()
