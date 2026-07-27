"""
Live end-to-end API test for the Social Support Application.
Tests all 7 phases with real LLM requests.
"""

import requests
import time
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
PROFILE_DIR = Path("D:/test_misc/xd_assignment/data/fresh_accounts/applicant_990945")
EMIRATES_ID = "784-1960-1005207-2"

# Tracker for results
results = []
agent_messages = []
overall_start = time.time()


def log_step(step_name, passed, latency_ms, response_summary, failure_reason=None):
    """Log a test step result."""
    result = {
        "step": step_name,
        "passed": passed,
        "latency_ms": round(latency_ms, 1),
        "response_summary": response_summary,
        "failure_reason": failure_reason,
    }
    results.append(result)
    status = "PASS" if passed else "FAIL"
    print(f"\n{'='*60}")
    print(f"[{status}] Step: {step_name}")
    print(f"  Latency: {latency_ms:.1f}ms")
    print(f"  Summary: {response_summary}")
    if failure_reason:
        print(f"  FAILURE: {failure_reason}")
    print(f"{'='*60}")
    return result


def read_profile():
    """Read the profile.json for applicant details."""
    profile_path = PROFILE_DIR / "profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def step_1_auth():
    """Step 1: Auth — POST /auth/login with Emirates ID."""
    print("\n>>> STEP 1: Authentication")
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"emirates_id": EMIRATES_ID},
        timeout=30,
    )
    latency = (time.time() - start) * 1000

    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")

    if resp.status_code != 200:
        return log_step(
            "Auth",
            False,
            latency,
            f"Status {resp.status_code}: {resp.text[:200]}",
            f"Expected 200, got {resp.status_code}",
        )

    data = resp.json()
    application_id = data.get("application_id")
    current_phase = data.get("current_phase")

    if not application_id:
        return log_step(
            "Auth",
            False,
            latency,
            str(data),
            "application_id not present in response",
        )

    if current_phase not in ("authentication", "intake"):
        return log_step(
            "Auth",
            False,
            latency,
            str(data),
            f"current_phase '{current_phase}' not in (authentication, intake)",
        )

    return log_step(
        "Auth",
        True,
        latency,
        f"application_id={application_id}, phase={current_phase}",
    ), application_id, data


def step_2_intake(application_id, profile):
    """Step 2: Intake — POST /chat with personal details and support_category."""
    print("\n>>> STEP 2: Intake")

    # Build intake message with full personal details and support_category keyword
    full_name = profile.get("full_name_en", "Applicant")
    dob = profile.get("date_of_birth", "1990-01-01")
    support_category = profile.get("support_category", "divorced")
    marital_status = profile.get("marital_status", "single")
    employment = profile.get("employment_status", "unemployed")
    salary = profile.get("monthly_salary", "0")
    city = profile.get("address", {}).get("city", "Dubai")

    intake_message = (
        f"My name is {full_name}. I was born on {dob}. "
        f"I am {marital_status} and my support category is {support_category}. "
        f"I am currently {employment} with a monthly income of {salary} AED. "
        f"I live in {city}. I need financial support."
    )

    print(f"  Sending intake message: {intake_message[:100]}...")

    max_retries = 5
    retry_count = 0
    last_response = None

    while retry_count < max_retries:
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/applications/{application_id}/chat",
            data={"text": intake_message},
            timeout=120,
        )
        latency = (time.time() - start) * 1000

        print(f"  Attempt {retry_count + 1}: Status {resp.status_code}, Latency {latency:.1f}ms")
        print(f"  Response: {resp.text[:500]}")

        if resp.status_code != 200:
            return log_step(
                "Intake",
                False,
                latency,
                f"Status {resp.status_code}: {resp.text[:200]}",
                f"Expected 200, got {resp.status_code}",
            )

        data = resp.json()
        phase = data.get("phase") or data.get("current_phase")
        message = data.get("message", "")
        interrupt = data.get("interrupt")

        # Store agent message
        if message:
            agent_messages.append({"step": "intake", "message": message})

        # Check if phase advanced to document_collection
        if phase == "document_collection":
            return log_step(
                "Intake",
                True,
                latency,
                f"phase={phase}, interrupt={interrupt is not None}",
            ), data

        # If interrupt returned, answer follow-up questions
        if interrupt:
            question = interrupt.get("question", "")
            missing_fields = interrupt.get("missing_fields", [])
            print(f"  Interrupt: {question[:100] if question else 'N/A'}")
            print(f"  Missing fields: {missing_fields}")

            # Build a comprehensive answer addressing missing fields
            if missing_fields:
                # Provide all missing info at once
                answer_parts = []
                if "date_of_birth" in missing_fields:
                    answer_parts.append(f"My date of birth is {dob}.")
                if "nationality" in missing_fields:
                    answer_parts.append(f"I am {profile.get('nationality', 'Qatari')}.")
                if "contact_phone" in missing_fields:
                    answer_parts.append(f"My phone is {profile.get('contact_phone', 'N/A')}.")
                if "contact_email" in missing_fields:
                    answer_parts.append(f"My email is {profile.get('contact_email', 'N/A')}.")
                if "address" in missing_fields:
                    addr = profile.get("address", {})
                    answer_parts.append(f"I live at {addr.get('street', 'N/A')}, {addr.get('city', 'N/A')}.")
                if "marital_status" in missing_fields:
                    answer_parts.append(f"My marital status is {marital_status}.")
                if "family_size" in missing_fields:
                    answer_parts.append(f"My family size is {profile.get('family_size', 1)}.")
                if "employment_status" in missing_fields:
                    answer_parts.append(f"I am {employment}.")
                if "employer_name" in missing_fields:
                    answer_parts.append(f"My employer is {profile.get('employer_name', 'N/A')}.")
                if "occupation" in missing_fields:
                    answer_parts.append(f"I work as a {profile.get('occupation', 'N/A')}.")
                if "monthly_salary" in missing_fields or "income" in str(missing_fields).lower():
                    answer_parts.append(f"My monthly income is {salary} AED.")
                if "housing_status" in missing_fields:
                    answer_parts.append(f"My housing status is {profile.get('housing_status', 'rented')}.")

                if answer_parts:
                    intake_message = " ".join(answer_parts)
                else:
                    intake_message = "I have provided all my information. Please proceed."
            else:
                intake_message = "I have provided all the information you need. Please proceed with my application."

            retry_count += 1
            last_response = data
            continue

        # If no interrupt and not document_collection, something unexpected
        if phase not in ("document_collection", "intake"):
            return log_step(
                "Intake",
                False,
                latency,
                str(data),
                f"Unexpected phase: {phase}",
            )

        # Still in intake without interrupt — send more info
        retry_count += 1
        last_response = data

    # Exhausted retries
    final_phase = last_response.get("phase") if last_response else "unknown"
    return log_step(
        "Intake",
        False,
        0,
        str(last_response) if last_response else "No response",
        f"Did not advance to document_collection after {max_retries} attempts. Final phase: {final_phase}",
    ), last_response


def step_3_document_upload(application_id):
    """Step 3: Document Upload — POST /chat as multipart with all documents."""
    print("\n>>> STEP 3: Document Upload")

    # Required documents from profile directory
    doc_files = [
        ("emirates_id_front.png", "image/png"),
        ("emirates_id_back.png", "image/png"),
        ("bank_statement.pdf", "application/pdf"),
        ("credit_report.pdf", "application/pdf"),
        ("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("assets_liabilities.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("application_form.png", "image/png"),
    ]

    files = []
    for fname, mime in doc_files:
        fpath = PROFILE_DIR / fname
        if fpath.exists():
            files.append(("files", (fname, open(fpath, "rb"), mime)))
            print(f"  Added: {fname}")
        else:
            print(f"  MISSING: {fname}")

    if not files:
        return log_step(
            "Document Upload",
            False,
            0,
            "No document files found",
            "Profile directory missing documents",
        )

    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "Here are all my required documents for the application."},
        files=files,
        timeout=180,
    )
    latency = (time.time() - start) * 1000

    # Close file handles
    for _, (_, fh, _) in files:
        fh.close()

    print(f"  Status: {resp.status_code}")
    print(f"  Latency: {latency:.1f}ms")
    print(f"  Response: {resp.text[:800]}")

    if resp.status_code != 200:
        return log_step(
            "Document Upload",
            False,
            latency,
            f"Status {resp.status_code}: {resp.text[:200]}",
            f"Expected 200, got {resp.status_code}",
        )

    data = resp.json()
    uploaded_docs = data.get("uploaded_documents", [])
    message = data.get("message", "")
    phase = data.get("phase") or data.get("current_phase")

    if message:
        agent_messages.append({"step": "document_upload", "message": message})

    # Check for unknown doc types
    unknown_docs = [d for d in uploaded_docs if d.get("doc_type") == "unknown"]
    doc_types = [d.get("doc_type") for d in uploaded_docs]

    print(f"  Uploaded documents: {doc_types}")

    if unknown_docs:
        return log_step(
            "Document Upload",
            False,
            latency,
            f"Uploaded: {doc_types}, phase={phase}",
            f"{len(unknown_docs)} document(s) classified as 'unknown'",
        )

    # Verify files saved
    upload_dir = Path(f"D:/test_misc/xd_assignment/data/uploads/{application_id}")
    if upload_dir.exists():
        saved_files = list(upload_dir.glob("*"))
        print(f"  Files saved: {len(saved_files)} in {upload_dir}")
    else:
        print(f"  WARNING: Upload directory not found: {upload_dir}")

    return log_step(
        "Document Upload",
        True,
        latency,
        f"Uploaded {len(uploaded_docs)} docs: {doc_types}, phase={phase}",
    ), data


def step_4_processing(application_id):
    """Step 4: Processing — Poll until phase is no longer 'processing'."""
    print("\n>>> STEP 4: Processing")

    start = time.time()
    max_wait = 90
    poll_interval = 3
    final_phase = None
    last_data = None

    for attempt in range(max_wait // poll_interval):
        elapsed = time.time() - start
        if elapsed > max_wait:
            break

        resp = requests.get(
            f"{BASE_URL}/applications/{application_id}",
            timeout=30,
        )
        data = resp.json()
        current_phase = data.get("current_phase", "unknown")
        final_phase = current_phase
        last_data = data

        print(f"  Poll {attempt + 1} ({elapsed:.1f}s): phase={current_phase}")

        if current_phase not in ("processing", "document_collection"):
            print(f"  Processing complete: phase={current_phase}")
            break

        time.sleep(poll_interval)

    latency = (time.time() - start) * 1000
    print(f"  Final phase: {final_phase} after {latency:.1f}ms")

    if final_phase in ("review", "decision", "enablement"):
        return log_step(
            "Processing",
            True,
            latency,
            f"Final phase: {final_phase}",
        ), final_phase, last_data

    if final_phase == "processing":
        return log_step(
            "Processing",
            False,
            latency,
            f"Still processing after {max_wait}s",
            f"Timeout: phase stuck at 'processing'",
        ), final_phase, last_data

    return log_step(
        "Processing",
        False,
        latency,
        f"Final phase: {final_phase}",
        f"Unexpected phase: {final_phase}",
    ), final_phase, last_data


def step_5_review(application_id, current_phase):
    """Step 5: Review — Address discrepancies if in review phase."""
    print("\n>>> STEP 5: Review")

    if current_phase == "decision":
        return log_step(
            "Review",
            True,
            0,
            "Skipped — already in decision phase",
        ), None

    if current_phase != "review":
        return log_step(
            "Review",
            False,
            0,
            f"Phase is {current_phase}, expected 'review'",
            f"Not in review phase",
        ), None

    # Get application details to find discrepancies
    resp = requests.get(
        f"{BASE_URL}/applications/{application_id}",
        timeout=30,
    )
    data = resp.json()

    # Check for interrupt with discrepancies
    interrupt = data.get("interrupt") or data.get("_pending_interrupt")
    discrepancies = interrupt.get("discrepancies", []) if interrupt else []
    missing_docs = interrupt.get("missing_documents", []) if interrupt else []
    question = interrupt.get("question", "") if interrupt else ""

    print(f"  Discrepancies: {len(discrepancies)}")
    print(f"  Missing documents: {len(missing_docs)}")
    print(f"  Question: {question[:100] if question else 'N/A'}")

    if discrepancies:
        for disc in discrepancies[:3]:
            print(f"    - {disc.get('description', disc)[:80]}")

    # Send clarifying message
    clarification = "I confirm that all the information I provided is accurate and complete. "
    if discrepancies:
        clarification += "Any discrepancies are due to legitimate reasons such as timing differences or data entry variations. "
    clarification += "Please proceed with my application."

    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": clarification},
        timeout=120,
    )
    latency = (time.time() - start) * 1000

    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")

    if resp.status_code != 200:
        return log_step(
            "Review",
            False,
            latency,
            f"Status {resp.status_code}: {resp.text[:200]}",
            f"Expected 200, got {resp.status_code}",
        )

    data = resp.json()
    message = data.get("message", "")
    phase = data.get("phase") or data.get("current_phase")

    if message:
        agent_messages.append({"step": "review", "message": message})

    # Poll until phase advances to decision
    if phase == "review":
        print("  Still in review, polling...")
        for attempt in range(10):
            time.sleep(3)
            resp = requests.get(
                f"{BASE_URL}/applications/{application_id}",
                timeout=30,
            )
            data = resp.json()
            phase = data.get("current_phase", "unknown")
            print(f"    Poll {attempt + 1}: phase={phase}")
            if phase != "review":
                break

    if phase == "decision":
        return log_step(
            "Review",
            True,
            latency,
            f"Advanced to decision phase",
        ), data

    return log_step(
        "Review",
        False,
        latency,
        f"Final phase: {phase}",
        f"Did not advance to decision",
    ), data


def step_6_decision(application_id):
    """Step 6: Decision — Assert decision and eligibility_score."""
    print("\n>>> STEP 6: Decision")

    start = time.time()
    resp = requests.get(
        f"{BASE_URL}/applications/{application_id}",
        timeout=30,
    )
    latency = (time.time() - start) * 1000

    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:800]}")

    if resp.status_code != 200:
        return log_step(
            "Decision",
            False,
            latency,
            f"Status {resp.status_code}: {resp.text[:200]}",
            f"Expected 200, got {resp.status_code}",
        )

    data = resp.json()
    decision = data.get("decision")
    eligibility_score = data.get("eligibility_score")

    valid_decisions = ("approved", "manual_review", "soft_decline")

    if decision not in valid_decisions:
        return log_step(
            "Decision",
            False,
            latency,
            str(data),
            f"decision '{decision}' not in {valid_decisions}",
        )

    if eligibility_score is None:
        return log_step(
            "Decision",
            False,
            latency,
            str(data),
            "eligibility_score not present",
        )

    try:
        score = float(eligibility_score)
        if not (0 <= score <= 1):
            return log_step(
                "Decision",
                False,
                latency,
                str(data),
                f"eligibility_score {score} not in [0, 1]",
            )
    except (ValueError, TypeError):
        return log_step(
            "Decision",
            False,
            latency,
            str(data),
            f"eligibility_score '{eligibility_score}' is not a number",
        )

    return log_step(
        "Decision",
        True,
        latency,
        f"decision={decision}, eligibility_score={eligibility_score}",
    ), decision, eligibility_score, data


def step_7_enablement(application_id):
    """Step 7: Enablement — Ask for personalized recommendations."""
    print("\n>>> STEP 7: Enablement")

    # First check current phase
    resp = requests.get(
        f"{BASE_URL}/applications/{application_id}",
        timeout=30,
    )
    data = resp.json()
    current_phase = data.get("current_phase", "unknown")

    print(f"  Current phase: {current_phase}")

    # If not in enablement, we may need to advance
    if current_phase not in ("enablement", "decision"):
        return log_step(
            "Enablement",
            False,
            0,
            f"Phase is {current_phase}, not in enablement",
            f"Application not in enablement phase",
        )

    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/applications/{application_id}/chat",
        data={"text": "What support am I eligible for? Please tell me about the programs and benefits available to me."},
        timeout=120,
    )
    latency = (time.time() - start) * 1000

    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:800]}")

    if resp.status_code != 200:
        return log_step(
            "Enablement",
            False,
            latency,
            f"Status {resp.status_code}: {resp.text[:200]}",
            f"Expected 200, got {resp.status_code}",
        )

    data = resp.json()
    message = data.get("message", "")
    recommendations = data.get("enablement_recommendations") or data.get("recommendations", [])

    if message:
        agent_messages.append({"step": "enablement", "message": message})

    # Check for personalized content
    has_recommendations = bool(recommendations) or len(message) > 50

    # Look for personalized keywords
    personalized_keywords = ["eligible", "support", "program", "benefit", "financial", "assistance", "housing", "rent", "allowance"]
    message_lower = message.lower()
    found_keywords = [kw for kw in personalized_keywords if kw in message_lower]

    print(f"  Found keywords: {found_keywords}")
    print(f"  Recommendations count: {len(recommendations) if isinstance(recommendations, list) else 'N/A'}")

    if has_recommendations or len(found_keywords) >= 2:
        return log_step(
            "Enablement",
            True,
            latency,
            f"Response contains recommendations ({len(found_keywords)} keywords matched)",
        ), message

    return log_step(
        "Enablement",
        False,
        latency,
        f"Message length: {len(message)}",
        "Response does not appear to contain personalized recommendations",
    ), message


def generate_report():
    """Generate the final structured report."""
    overall_latency = (time.time() - overall_start) * 1000

    # Find decision and score
    decision = None
    eligibility_score = None
    for r in results:
        if r["step"] == "Decision" and r["passed"]:
            summary = r["response_summary"]
            if "decision=" in summary:
                import re
                decision_match = re.search(r"decision=(\w+)", summary)
                score_match = re.search(r"eligibility_score=([\d.]+)", summary)
                if decision_match:
                    decision = decision_match.group(1)
                if score_match:
                    eligibility_score = float(score_match.group(1))

    report = {
        "timestamp": datetime.now().isoformat(),
        "emirates_id": EMIRATES_ID,
        "profile_path": str(PROFILE_DIR),
        "per_step_results": results,
        "overall": {
            "total_end_to_end_latency_ms": round(overall_latency, 1),
            "decision": decision,
            "eligibility_score": eligibility_score,
            "steps_passed": sum(1 for r in results if r["passed"]),
            "steps_total": len(results),
        },
        "agent_messages": agent_messages,
    }

    return report


def main():
    """Run all E2E test steps."""
    print("=" * 60)
    print("LIVE E2E API TEST")
    print(f"Base URL: {BASE_URL}")
    print(f"Emirates ID: {EMIRATES_ID}")
    print(f"Profile: {PROFILE_DIR}")
    print(f"Start time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Read profile
    profile = read_profile()
    # Use safe ASCII output to avoid Windows encoding issues
    print(f"\nProfile loaded: {profile.get('full_name_en', 'N/A').encode('ascii', 'replace').decode()}")
    print(f"Support category: {profile.get('support_category', 'N/A')}")

    # Step 1: Auth
    auth_result = step_1_auth()
    if not auth_result[0]["passed"]:
        print("\nAUTH FAILED — stopping test")
        report = generate_report()
        print("\n" + json.dumps(report, indent=2))
        return report

    _, application_id, _ = auth_result

    # Step 2: Intake
    intake_result = step_2_intake(application_id, profile)
    if not intake_result[0]["passed"]:
        print("\nINTAKE FAILED — continuing anyway to test document upload")

    # Step 3: Document Upload
    upload_result = step_3_document_upload(application_id)
    if not upload_result[0]["passed"]:
        print("\nDOCUMENT UPLOAD FAILED — stopping test")
        report = generate_report()
        print("\n" + json.dumps(report, indent=2))
        return report

    # Step 4: Processing
    proc_result = step_4_processing(application_id)
    final_phase, _ = proc_result[1], proc_result[2]

    if not proc_result[0]["passed"]:
        print("\nPROCESSING FAILED or TIMED OUT")
        # Still try to check decision
        if final_phase in ("review", "decision"):
            print(f"  Phase is {final_phase}, continuing...")
        else:
            report = generate_report()
            print("\n" + json.dumps(report, indent=2))
            return report

    # Step 5: Review (if applicable)
    if final_phase == "review":
        review_result = step_5_review(application_id, final_phase)
    elif final_phase == "decision":
        log_step("Review", True, 0, "Skipped — already in decision phase")
    else:
        log_step("Review", False, 0, f"Phase is {final_phase}", "Not in review or decision")

    # Step 6: Decision
    decision_result = step_6_decision(application_id)
    if not decision_result[0]["passed"]:
        print("\nDECISION CHECK FAILED")

    # Step 7: Enablement
    step_7_enablement(application_id)

    # Generate final report
    report = generate_report()

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(json.dumps(report, indent=2))

    # Save report to file
    report_path = Path("D:/test_misc/xd_assignment/evals/live_e2e_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_path}")

    return report


if __name__ == "__main__":
    report = main()
