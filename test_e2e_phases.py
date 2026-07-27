"""Comprehensive E2E test for all 7 phases of the application flow."""

import json
import time
from pathlib import Path
import requests
from datetime import datetime

import structlog
from src.infrastructure.observability.logging import configure_logging

configure_logging()

logger = structlog.get_logger(__name__)

BASE_URL = "http://localhost:8000/api/v1"
TEST_DATA_DIR = Path("data/test_applicants/applicant_7537")


def log_test(phase, test_name, status, details=None):
    """Log test result with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_icon = "[PASS]" if status == "PASS" else "[FAIL]"
    event = f"phase_{phase}_{'pass' if status == 'PASS' else 'fail'}"
    log_kwargs = {
        "phase": phase,
        "test": test_name,
        "status": status,
    }
    if details:
        log_kwargs["details"] = details
    logger.info(event, **log_kwargs)
    print(f"[{timestamp}] {status_icon} Phase {phase} - {test_name}")
    if details:
        print(f"  Details: {details}")


def test_phase_0_authentication():
    """Test Phase 0: Authentication with Emirates ID."""
    logger.info("test_start", phase=0, name="authentication")
    print("\n=== Phase 0: Authentication ===")

    start = time.time()

    profile_path = TEST_DATA_DIR / "profile.json"
    with open(profile_path) as f:
        profile = json.load(f)

    identity_number = profile["identity_number"]

    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"emirates_id": identity_number}
    )

    duration_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        log_test(0, "Auth login", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
        logger.error("auth_login_failed", status_code=response.status_code, duration_ms=round(duration_ms, 2))
        return None, None

    auth_data = response.json()
    applicant_id = auth_data["applicant_id"]
    application_id = auth_data["application_id"]
    is_new = auth_data["is_new_applicant"]
    current_phase = auth_data["current_phase"]

    log_test(0, "Auth login", "PASS", f"Applicant ID: {applicant_id}, Application ID: {application_id}, New: {is_new}, Phase: {current_phase}")

    logger.info("auth_login_complete", application_id=application_id, applicant_id=applicant_id, is_new=is_new, phase=current_phase, duration_ms=round(duration_ms, 2))

    if current_phase == "intake":
        log_test(0, "Authentication complete", "PASS", f"Phase: {current_phase}")
        logger.info("phase_transition", from_phase="authentication", to_phase=current_phase, application_id=application_id)
        return application_id, profile
    else:
        log_test(0, "Authentication complete", "FAIL", f"Phase: {current_phase}")
        logger.error("unexpected_phase", expected="intake", actual=current_phase, application_id=application_id)
        return application_id, None


def test_phase_1_intake(application_id, profile):
    """Test Phase 1: Intake - collect applicant information."""
    logger.info("test_start", phase=1, name="intake", application_id=application_id)
    print("\n=== Phase 1: Intake ===")

    start = time.time()

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

    duration_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        log_test(1, "Intake request", "FAIL", f"Status: {response.status_code}")
        logger.error("intake_failed", application_id=application_id, status_code=response.status_code, duration_ms=round(duration_ms, 2))
        return False

    chat_data = response.json()
    phase = chat_data.get("phase")
    message = chat_data.get("message", "")

    if phase == "document_collection":
        log_test(1, "Intake complete", "PASS", f"Phase: {phase}")
        logger.info("phase_transition", from_phase="intake", to_phase=phase, application_id=application_id, duration_ms=round(duration_ms, 2))
        return True
    else:
        log_test(1, "Intake complete", "FAIL", f"Phase: {phase}, Message: {message[:100]}")
        logger.error("unexpected_phase", expected="document_collection", actual=phase, application_id=application_id, duration_ms=round(duration_ms, 2))
        return False


def test_phase_2_document_collection(application_id):
    """Test Phase 2: Document collection - upload all required documents."""
    logger.info("test_start", phase=2, name="document_collection", application_id=application_id)
    print("\n=== Phase 2: Document Collection ===")

    documents = [
        ("emirates_id_front.png", "image/png"),
        ("emirates_id_back.png", "image/png"),
        ("bank_statement.pdf", "application/pdf"),
        ("credit_report.pdf", "application/pdf"),
        ("application_form.png", "image/png"),
    ]

    uploaded_count = 0
    start = time.time()

    for doc_name, mime_type in documents:
        doc_path = TEST_DATA_DIR / doc_name
        if not doc_path.exists():
            log_test(2, f"Upload {doc_name}", "FAIL", "File not found")
            logger.warning("document_file_not_found", doc_name=doc_name, application_id=application_id)
            continue

        upload_start = time.time()
        with open(doc_path, "rb") as f:
            files = [("files", (doc_name, f, mime_type))]
            response = requests.post(
                f"{BASE_URL}/applications/{application_id}/chat",
                data={"text": f"Uploading {doc_name}"},
                files=files
            )
        upload_duration_ms = (time.time() - upload_start) * 1000

        if response.status_code != 200:
            log_test(2, f"Upload {doc_name}", "FAIL", f"Status: {response.status_code}")
            logger.error("document_upload_failed", doc_name=doc_name, application_id=application_id, status_code=response.status_code, duration_ms=round(upload_duration_ms, 2))
            continue

        chat_data = response.json()
        phase = chat_data.get("phase")
        uploaded_count += 1
        log_test(2, f"Upload {doc_name}", "PASS", f"Phase: {phase}")
        logger.info("document_uploaded", doc_name=doc_name, application_id=application_id, phase=phase, duration_ms=round(upload_duration_ms, 2))

    # Final check - should transition to processing
    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I have uploaded all required documents"},
        files=[]
    )

    total_duration_ms = (time.time() - start) * 1000

    if response.status_code == 200:
        chat_data = response.json()
        phase = chat_data.get("phase")
        if phase == "processing":
            log_test(2, "Transition to processing", "PASS", f"Phase: {phase}")
            logger.info("phase_transition", from_phase="document_collection", to_phase=phase, application_id=application_id, documents_uploaded=uploaded_count, duration_ms=round(total_duration_ms, 2))
            return True
        else:
            log_test(2, "Transition to processing", "FAIL", f"Phase: {phase}")
            logger.error("unexpected_phase", expected="processing", actual=phase, application_id=application_id, duration_ms=round(total_duration_ms, 2))
            return False

    logger.error("chat_request_failed", application_id=application_id, status_code=response.status_code, duration_ms=round(total_duration_ms, 2))
    return False


def test_phase_3_processing(application_id):
    """Test Phase 3: Processing - document extraction and validation."""
    logger.info("test_start", phase=3, name="processing", application_id=application_id)
    print("\n=== Phase 3: Processing ===")

    start = time.time()

    time.sleep(2)

    response = requests.get(f"{BASE_URL}/applications/{application_id}")

    duration_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        log_test(3, "Check processing status", "FAIL", f"Status: {response.status_code}")
        logger.error("status_check_failed", application_id=application_id, status_code=response.status_code, duration_ms=round(duration_ms, 2))
        return False

    app_data = response.json()
    phase = app_data.get("current_phase")

    if phase in ["review", "decision", "enablement"]:
        log_test(3, "Processing complete", "PASS", f"Phase: {phase}")
        logger.info("processing_complete", application_id=application_id, phase=phase, duration_ms=round(duration_ms, 2))
        return True
    else:
        log_test(3, "Processing complete", "FAIL", f"Phase: {phase}")
        logger.error("processing_incomplete", application_id=application_id, phase=phase, duration_ms=round(duration_ms, 2))
        return False


def test_phase_4_review(application_id):
    """Test Phase 4: Review - applicant reviews extracted data."""
    logger.info("test_start", phase=4, name="review", application_id=application_id)
    print("\n=== Phase 4: Review ===")

    start = time.time()

    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "I confirm the information is correct. Please proceed."},
        files=[]
    )

    duration_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        log_test(4, "Review confirmation", "FAIL", f"Status: {response.status_code}")
        logger.error("review_failed", application_id=application_id, status_code=response.status_code, duration_ms=round(duration_ms, 2))
        return False

    chat_data = response.json()
    phase = chat_data.get("phase")
    message = chat_data.get("message", "")

    if phase == "decision":
        log_test(4, "Review complete", "PASS", f"Phase: {phase}")
        logger.info("phase_transition", from_phase="review", to_phase=phase, application_id=application_id, duration_ms=round(duration_ms, 2))
        return True
    else:
        log_test(4, "Review complete", "FAIL", f"Phase: {phase}, Message: {message[:100]}")
        logger.error("unexpected_phase", expected="decision", actual=phase, application_id=application_id, duration_ms=round(duration_ms, 2))
        return False


def test_phase_5_decision(application_id):
    """Test Phase 5: Decision - eligibility scoring and decision."""
    logger.info("test_start", phase=5, name="decision", application_id=application_id)
    print("\n=== Phase 5: Decision ===")

    start = time.time()

    time.sleep(2)

    response = requests.get(f"{BASE_URL}/applications/{application_id}")

    duration_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        log_test(5, "Check decision status", "FAIL", f"Status: {response.status_code}")
        logger.error("decision_status_check_failed", application_id=application_id, status_code=response.status_code, duration_ms=round(duration_ms, 2))
        return False

    app_data = response.json()
    phase = app_data.get("current_phase")
    decision = app_data.get("decision")
    eligibility_score = app_data.get("eligibility_score")

    if phase == "enablement" and decision:
        log_test(5, "Decision made", "PASS", f"Decision: {decision}, Score: {eligibility_score}")
        logger.info("decision_reached", application_id=application_id, decision=decision, eligibility_score=eligibility_score, duration_ms=round(duration_ms, 2))
        return True
    else:
        log_test(5, "Decision made", "FAIL", f"Phase: {phase}, Decision: {decision}")
        logger.error("decision_not_reached", application_id=application_id, phase=phase, decision=decision, duration_ms=round(duration_ms, 2))
        return False


def test_phase_6_enablement(application_id, decision):
    """Test Phase 6: Enablement - benefits package."""
    logger.info("test_start", phase=6, name="enablement", application_id=application_id)
    print("\n=== Phase 6: Enablement ===")

    start = time.time()

    response = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "Thank you for the decision. What are the next steps?"},
        files=[]
    )

    duration_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        log_test(6, "Enablement request", "FAIL", f"Status: {response.status_code}")
        logger.error("enablement_request_failed", application_id=application_id, status_code=response.status_code, duration_ms=round(duration_ms, 2))
        return False

    chat_data = response.json()
    phase = chat_data.get("phase")
    message = chat_data.get("message", "")

    if phase == "enablement" and "next steps" in message.lower():
        log_test(6, "Enablement complete", "PASS", f"Phase: {phase}")
        logger.info("enablement_complete", application_id=application_id, decision=decision, duration_ms=round(duration_ms, 2))
        return True
    else:
        log_test(6, "Enablement complete", "FAIL", f"Phase: {phase}, Message: {message[:100]}")
        logger.error("enablement_incomplete", application_id=application_id, phase=phase, duration_ms=round(duration_ms, 2))
        return False


def main():
    """Run all E2E tests."""
    logger.info("e2e_test_suite_start", suite="comprehensive_7_phases")
    print("=" * 60)
    print("COMPREHENSIVE E2E TEST - ALL 7 PHASES")
    print("=" * 60)

    start_time = time.time()

    try:
        # Phase 0: Authentication
        application_id, profile = test_phase_0_authentication()
        if not application_id:
            logger.error("e2e_test_suite_failed", phase=0)
            print("\n[FAIL] Test failed at Phase 0")
            return

        # Phase 1: Intake
        if not test_phase_1_intake(application_id, profile):
            logger.error("e2e_test_suite_failed", phase=1, application_id=application_id)
            print("\n[FAIL] Test failed at Phase 1")
            return

        # Phase 2: Document Collection
        if not test_phase_2_document_collection(application_id):
            logger.error("e2e_test_suite_failed", phase=2, application_id=application_id)
            print("\n[FAIL] Test failed at Phase 2")
            return

        # Phase 3: Processing
        if not test_phase_3_processing(application_id):
            logger.error("e2e_test_suite_failed", phase=3, application_id=application_id)
            print("\n[FAIL] Test failed at Phase 3")
            return

        # Phase 4: Review
        if not test_phase_4_review(application_id):
            logger.error("e2e_test_suite_failed", phase=4, application_id=application_id)
            print("\n[FAIL] Test failed at Phase 4")
            return

        # Phase 5: Decision
        if not test_phase_5_decision(application_id):
            logger.error("e2e_test_suite_failed", phase=5, application_id=application_id)
            print("\n[FAIL] Test failed at Phase 5")
            return

        # Phase 6: Enablement
        response = requests.get(f"{BASE_URL}/applications/{application_id}")
        decision = response.json().get("decision") if response.status_code == 200 else None
        test_phase_6_enablement(application_id, decision)

        elapsed = time.time() - start_time

        logger.info("e2e_test_suite_complete", application_id=application_id, decision=decision, total_duration_ms=round(elapsed * 1000, 2))
        print("\n" + "=" * 60)
        print(f"[PASS] ALL TESTS PASSED - {elapsed:.2f}s")
        print("=" * 60)
        print(f"\nApplication ID: {application_id}")
        print(f"Final Decision: {decision}")
        print(f"Eligibility Score: {response.json().get('eligibility_score') if response.status_code == 200 else 'N/A'}")

    except Exception as exc:
        elapsed = time.time() - start_time
        logger.exception("e2e_test_suite_error", total_duration_ms=round(elapsed * 1000, 2))
        print(f"\n[ERROR] Unexpected error: {exc}")


if __name__ == "__main__":
    main()
