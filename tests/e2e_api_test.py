"""
E2E API Test Script - Read-Only Tester
Tests the Social Support Application API with real LLM requests.
Records all failures for the fix subagent.
"""

import requests
import time
import json
import sys
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
EMIRATES_ID = "784-1995-3493270-4"
PROFILE_DIR = Path("D:/test_misc/xd_assignment/data/fresh_accounts/applicant_953842")
UPLOAD_DIR = Path("D:/test_misc/xd_assignment/data/uploads")

# Results tracking
results = []
failure_queue = []
all_agent_messages = []
start_time = time.time()


def record_step(step_name, passed, latency_ms, response_summary, failure_reason=None, raw_response=None):
    """Record a test step result."""
    result = {
        "step": step_name,
        "passed": passed,
        "latency_ms": round(latency_ms, 2),
        "response_summary": response_summary,
        "failure_reason": failure_reason,
    }
    results.append(result)
    if not passed and failure_reason:
        failure_queue.append({
            "step": step_name,
            "symptom": response_summary,
            "error_message": failure_reason,
            "stack_trace": None,
            "category": "api" if "HTTP" in failure_reason or "status" in failure_reason else "agent"
        })
    if raw_response:
        all_agent_messages.append({"step": step_name, "response": raw_response})
    return result


def make_request(method, endpoint, **kwargs):
    """Make an HTTP request and return (response, latency_ms)."""
    url = f"{BASE_URL}{endpoint}"
    start = time.time()
    try:
        resp = requests.request(method, url, timeout=120, **kwargs)
        latency = (time.time() - start) * 1000
        return resp, latency
    except Exception as e:
        latency = (time.time() - start) * 1000
        return None, latency, str(e)


# ============================================================
# STEP 1: Auth — POST /auth/login with Emirates ID
# ============================================================
print("\n" + "="*60)
print("STEP 1: Auth — POST /auth/login")
print("="*60)

resp, latency = make_request("POST", "/auth/login", json={"emirates_id": EMIRATES_ID})

if resp is None:
    record_step("Auth", False, latency, "Connection failed", "Request exception: connection refused or timeout")
elif resp.status_code != 200:
    body = resp.text[:500] if resp.text else "empty"
    record_step("Auth", False, latency, f"HTTP {resp.status_code}: {body}", f"HTTP {resp.status_code}: {body}")
else:
    data = resp.json()
    app_id = data.get("application_id")
    phase = data.get("current_phase")
    if app_id and phase in ("authentication", "intake"):
        record_step("Auth", True, latency, f"application_id={app_id}, phase={phase}", raw_response=data)
        application_id = app_id
    else:
        record_step("Auth", False, latency, f"app_id={app_id}, phase={phase}",
                    f"Missing application_id or invalid phase. Got: {data}")

print(f"Result: {results[-1]}")
if results[-1]["passed"]:
    application_id = json.loads(results[-1]["response_summary"].split("application_id=")[1].split(",")[0]) if "application_id=" in results[-1]["response_summary"] else None
    # Re-extract from raw
    pass  # We'll get it from the raw response stored

# Get application_id from stored raw response
auth_response = None
for msg in all_agent_messages:
    if msg["step"] == "Auth":
        auth_response = msg["response"]
        break

if auth_response:
    application_id = auth_response.get("application_id")
    current_phase = auth_response.get("current_phase")
    print(f"  -> application_id={application_id}, current_phase={current_phase}")
else:
    print("  -> AUTH FAILED, cannot continue")
    application_id = None


# ============================================================
# STEP 2: Intake — POST /applications/{app_id}/chat
# ============================================================
if application_id:
    print("\n" + "="*60)
    print("STEP 2: Intake — Chat with personal details")
    print("="*60)

    # Build comprehensive intake message with support_category keyword
    intake_message = {
        "message": (
            f"My name is {EMIRATES_ID} holder. "
            f"I am applying for social support under the divorced category. "
            f"Full name: ريان الصافي. "
            f"Date of birth: 1995-06-06. "
            f"Nationality: Emirati. "
            f"Gender: Male. "
            f"Phone: (+971) 722524027. "
            f"Email: cut1823@yahoo.com. "
            f"Address: 1370 شارع الهدى, Ras Al Khaimah, Fujairah, P.O. Box 54481. "
            f"Marital status: married. Family size: 2. "
            f"Employment: employed as Security Guard at Dubai Company. "
            f"Monthly salary: 18527.68 AED. "
            f"Total monthly income: 23244.07 AED. "
            f"Housing: rented, monthly rent 17228.32 AED. "
            f"I am divorced and seeking support."
        )
    }

    max_retries = 5
    retry_count = 0
    intake_passed = False
    last_response = None

    while retry_count < max_retries:
        resp, latency = make_request("POST", f"/applications/{application_id}/chat", json=intake_message)

        if resp is None:
            record_step("Intake", False, latency, "Connection failed", "Request exception")
            break

        body = resp.json() if resp.text else {}
        phase = body.get("current_phase", "")
        interrupt = body.get("interrupt")
        agent_message = body.get("message", "")

        print(f"  Attempt {retry_count+1}: phase={phase}, interrupt={interrupt is not None}")
        print(f"  Agent message: {agent_message[:200]}...")

        if phase == "document_collection":
            record_step("Intake", True, latency, f"phase advanced to {phase}", raw_response=body)
            intake_passed = True
            break
        elif interrupt:
            # Answer interrupt questions
            retry_count += 1
            # Extract interrupt details
            discrepancies = interrupt.get("discrepancies", [])
            missing_docs = interrupt.get("missing_documents", [])
            questions = interrupt.get("questions", [])

            # Build a clarifying response
            clarifying_parts = []
            if discrepancies:
                for d in discrepancies:
                    clarifying_parts.append(f"Regarding {d.get('field', 'the discrepancy')}: {d.get('resolution', 'clarified')}")
            if missing_docs:
                for m in missing_docs:
                    clarifying_parts.append(f"Document {m.get('type', 'requested')}: will be uploaded shortly")
            if questions:
                for q in questions:
                    clarifying_parts.append(f"Answer to '{q}': provided above")

            intake_message = {"message": " ".join(clarifying_parts) if clarifying_parts else "All information provided above is accurate and complete."}
            last_response = body
            continue
        elif phase == "authentication":
            # Still in auth, need to continue
            retry_count += 1
            if "interrupt" not in str(body):
                intake_message = {"message": "I confirm all details are accurate. Please proceed."}
            last_response = body
            continue
        else:
            record_step("Intake", False, latency, f"phase={phase}", f"Unexpected phase: {phase}. Full response: {json.dumps(body)[:500]}")
            last_response = body
            break

    if not intake_passed and last_response:
        record_step("Intake", False, latency, f"phase={last_response.get('current_phase', 'unknown')}",
                    f"Did not advance to document_collection after {max_retries} attempts. Last phase: {last_response.get('current_phase')}",
                    raw_response=last_response)

    print(f"Result: {results[-1]}")
else:
    record_step("Intake", False, 0, "Skipped", "No application_id from auth step")


# ============================================================
# STEP 3: Document Upload
# ============================================================
if application_id and results[-1]["passed"]:
    print("\n" + "="*60)
    print("STEP 3: Document Upload")
    print("="*60)

    doc_files = {
        "emirates_id_front": ("emirates_id_front.png", open(PROFILE_DIR / "emirates_id_front.png", "rb"), "image/png"),
        "emirates_id_back": ("emirates_id_back.png", open(PROFILE_DIR / "emirates_id_back.png", "rb"), "image/png"),
        "bank_statement": ("bank_statement.pdf", open(PROFILE_DIR / "bank_statement.pdf", "rb"), "application/pdf"),
        "credit_report": ("credit_report.pdf", open(PROFILE_DIR / "credit_report.pdf", "rb"), "application/pdf"),
        "resume": ("resume.docx", open(PROFILE_DIR / "resume.docx", "rb"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "assets_liabilities": ("assets_liabilities.xlsx", open(PROFILE_DIR / "assets_liabilities.xlsx", "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "application_form": ("application_form.png", open(PROFILE_DIR / "application_form.png", "rb"), "image/png"),
    }

    # Use the dedicated document upload endpoint for each file
    upload_results = []
    all_uploaded = True
    unknown_docs = []

    for doc_key, (filename, file_obj, content_type) in doc_files.items():
        try:
            files = {"file": (filename, file_obj, content_type)}
            resp, latency = make_request("POST", f"/applications/{application_id}/documents", files=files)

            if resp is None:
                upload_results.append({"doc": doc_key, "status": "error", "error": "Connection failed"})
                all_uploaded = False
            elif resp.status_code not in (200, 201):
                upload_results.append({"doc": doc_key, "status": f"HTTP {resp.status_code}", "error": resp.text[:200]})
                all_uploaded = False
            else:
                data = resp.json()
                doc_type = data.get("document_type", data.get("doc_type", "unknown"))
                if doc_type == "unknown":
                    unknown_docs.append(doc_key)
                upload_results.append({"doc": doc_key, "status": "ok", "doc_type": doc_type})
        finally:
            file_obj.close()

    # Check files saved under data/uploads/{application_id}/
    upload_path = UPLOAD_DIR / application_id
    saved_files = list(upload_path.glob("*")) if upload_path.exists() else []

    if all_uploaded and not unknown_docs:
        record_step("Document Upload", True, 0,
                    f"{len(upload_results)} docs uploaded, saved to {upload_path} ({len(saved_files)} files)")
    elif unknown_docs:
        record_step("Document Upload", False, 0,
                    f"{len(upload_results)} docs uploaded but {len(unknown_docs)} classified as unknown: {unknown_docs}",
                    f"Unknown doc types: {unknown_docs}")
    else:
        failed = [r for r in upload_results if r["status"] != "ok"]
        record_step("Document Upload", False, 0,
                    f"{len(failed)} upload failures: {failed}",
                    f"Upload failures: {failed}")

    print(f"Result: {results[-1]}")
    for r in upload_results:
        print(f"  {r}")
else:
    record_step("Document Upload", False, 0, "Skipped", "Previous step failed")


# ============================================================
# STEP 4: Processing — Poll until phase != processing
# ============================================================
if application_id:
    print("\n" + "="*60)
    print("STEP 4: Processing — Poll for phase transition")
    print("="*60)

    # First, trigger processing by sending a "proceed" message if needed
    resp, _ = make_request("GET", f"/applications/{application_id}")
    if resp and resp.status_code == 200:
        current = resp.json()
        phase = current.get("current_phase", "unknown")
        print(f"  Current phase before poll: {phase}")

        if phase == "document_collection":
            # Send a message to trigger processing
            trigger_resp, _ = make_request("POST", f"/applications/{application_id}/chat", json={"message": "I have uploaded all required documents. Please proceed with processing."})
            if trigger_resp and trigger_resp.status_code == 200:
                phase = trigger_resp.json().get("current_phase", phase)
                print(f"  Phase after trigger: {phase}")

    # Poll
    max_wait = 90
    poll_interval = 3
    elapsed = 0
    processing_start = time.time()
    final_phase = None
    processing_passed = False

    while elapsed < max_wait:
        resp, latency = make_request("GET", f"/applications/{application_id}")
        if resp and resp.status_code == 200:
            data = resp.json()
            phase = data.get("current_phase", "unknown")
            print(f"  Poll {int(elapsed/poll_interval)+1}: phase={phase} ({elapsed}s)")

            if phase != "processing":
                final_phase = phase
                processing_time = (time.time() - processing_start) * 1000
                if phase in ("review", "decision", "enablement"):
                    record_step("Processing", True, processing_time, f"final phase={phase}, total_time={processing_time:.0f}ms")
                    processing_passed = True
                else:
                    record_step("Processing", False, processing_time, f"final phase={phase}", f"Processing did not advance to review/decision. Got phase: {phase}")
                break
        else:
            print(f"  Poll {int(elapsed/poll_interval)+1}: request failed")

        time.sleep(poll_interval)
        elapsed += poll_interval

    if not processing_passed and final_phase is None:
        record_step("Processing", False, max_wait * 1000, "timeout", f"Did not exit processing phase within {max_wait}s")

    print(f"Result: {results[-1]}")
else:
    record_step("Processing", False, 0, "Skipped", "No application_id")


# ============================================================
# STEP 5: Review (if phase is "review")
# ============================================================
if application_id and results[-1]["passed"] and results[-1]["response_summary"] and "review" in results[-1]["response_summary"]:
    print("\n" + "="*60)
    print("STEP 5: Review — Address discrepancies")
    print("="*60)

    # Get full application details including interrupt
    resp, latency = make_request("GET", f"/applications/{application_id}")
    if resp and resp.status_code == 200:
        data = resp.json()
        interrupt = data.get("interrupt", {})
        discrepancies = interrupt.get("discrepancies", [])
        missing_docs = interrupt.get("missing_documents", [])

        if discrepancies or missing_docs:
            # Build clarifying message
            clarifications = []
            for d in discrepancies:
                clarifications.append(f"Regarding {d.get('field', 'discrepancy')}: the correct value is as stated in my documents.")
            for m in missing_docs:
                clarifications.append(f"Document {m.get('type', 'requested')} has been uploaded.")

            clarifying_message = {"message": " ".join(clarifications) if clarifications else "All discrepancies are resolved. Please proceed."}
            resp2, lat2 = make_request("POST", f"/applications/{application_id}/chat", json=clarifying_message)

            if resp2 and resp2.status_code == 200:
                phase = resp2.json().get("current_phase")
                if phase == "decision":
                    record_step("Review", True, lat2, f"phase advanced to {phase}")
                else:
                    record_step("Review", True, lat2, f"clarification sent, phase={phase}", raw_response=resp2.json())
            else:
                record_step("Review", False, lat2, "Failed to send clarification", f"HTTP {resp2.status_code if resp2 else 'N/A'}")
        else:
            record_step("Review", True, latency, "No discrepancies found, phase=review", raw_response=data)
    else:
        record_step("Review", False, latency, "Failed to fetch application", f"HTTP {resp.status_code if resp else 'N/A'}")

    print(f"Result: {results[-1]}")
else:
    phase_info = results[-1]["response_summary"] if results[-1] else "N/A"
    record_step("Review", False, 0, f"Skipped (phase not review, got: {phase_info})", "Phase was not review after processing")


# ============================================================
# STEP 6: Decision
# ============================================================
if application_id:
    print("\n" + "="*60)
    print("STEP 6: Decision")
    print("="*60)

    # Poll until decision phase or timeout
    max_wait = 60
    elapsed = 0
    decision_found = False

    while elapsed < max_wait:
        resp, latency = make_request("GET", f"/applications/{application_id}")
        if resp and resp.status_code == 200:
            data = resp.json()
            phase = data.get("current_phase", "unknown")
            decision = data.get("decision")
            eligibility_score = data.get("eligibility_score")

            print(f"  Poll: phase={phase}, decision={decision}, eligibility_score={eligibility_score}")

            if phase == "decision" and decision:
                if decision in ("approved", "manual_review", "soft_decline") and eligibility_score is not None:
                    if 0 <= eligibility_score <= 1:
                        record_step("Decision", True, latency,
                                    f"decision={decision}, eligibility_score={eligibility_score}",
                                    raw_response=data)
                        decision_found = True
                        break
                    else:
                        record_step("Decision", False, latency, f"eligibility_score={eligibility_score} out of [0,1]",
                                    f"eligibility_score={eligibility_score} not in [0,1]")
                        decision_found = True
                        break
                else:
                    record_step("Decision", False, latency, f"decision={decision}",
                                f"Invalid decision value: {decision}")
                    decision_found = True
                    break
            elif phase in ("review", "processing"):
                # Not yet at decision, send a nudge if review
                if phase == "review":
                    resp2, _ = make_request("POST", f"/applications/{application_id}/chat", json={"message": "Please proceed with the decision."})
                elapsed += 3
                time.sleep(3)
                continue
            else:
                record_step("Decision", False, latency, f"phase={phase}", f"Unexpected phase: {phase}")
                decision_found = True
                break
        else:
            elapsed += 3
            time.sleep(3)

    if not decision_found:
        record_step("Decision", False, max_wait * 1000, "timeout", f"Did not reach decision phase within {max_wait}s")

    print(f"Result: {results[-1]}")
else:
    record_step("Decision", False, 0, "Skipped", "No application_id")


# ============================================================
# STEP 7: Enablement
# ============================================================
if application_id:
    print("\n" + "="*60)
    print("STEP 7: Enablement")
    print("="*60)

    # First check current phase
    resp, _ = make_request("GET", f"/applications/{application_id}")
    if resp and resp.status_code == 200:
        data = resp.json()
        phase = data.get("current_phase", "unknown")

        if phase == "enablement":
            enablement_msg = {"message": "What support am I eligible for?"}
            resp2, latency = make_request("POST", f"/applications/{application_id}/chat", json=enablement_msg)

            if resp2 and resp2.status_code == 200:
                response_text = resp2.json().get("message", "")
                # Check for personalized recommendations
                has_recommendations = any(kw in response_text.lower() for kw in ["eligible", "support", "recommend", "benefit", "program", "housing", "financial", "employment"])

                if has_recommendations:
                    record_step("Enablement", True, latency, "Response contains personalized recommendations", raw_response=resp2.json())
                else:
                    record_step("Enablement", False, latency, "Response lacks recommendations",
                                f"Message: {response_text[:300]}", raw_response=resp2.json())
            else:
                record_step("Enablement", False, latency, f"HTTP {resp2.status_code if resp2 else 'N/A'}",
                            f"Enablement request failed")
        else:
            record_step("Enablement", False, 0, f"phase={phase}", f"Not in enablement phase. Current: {phase}")
    else:
        record_step("Enablement", False, 0, "Failed to fetch application", "Could not determine phase")

    print(f"Result: {results[-1]}")
else:
    record_step("Enablement", False, 0, "Skipped", "No application_id")


# ============================================================
# FINAL REPORT
# ============================================================
total_time = (time.time() - start_time) * 1000

final_decision = None
final_eligibility = None
for r in results:
    if r["step"] == "Decision" and r["passed"] and r["response_summary"]:
        if "decision=" in r["response_summary"]:
            parts = r["response_summary"].split(",")
            for p in parts:
                if "decision=" in p:
                    final_decision = p.split("=")[1].strip()
                if "eligibility_score=" in p:
                    final_eligibility = float(p.split("=")[1].strip())

report = {
    "test_timestamp": datetime.now().isoformat(),
    "emirates_id": EMIRATES_ID,
    "profile_dir": str(PROFILE_DIR),
    "per_step_results": results,
    "overall": {
        "total_end_to_end_latency_ms": round(total_time, 2),
        "decision": final_decision,
        "eligibility_score": final_eligibility,
    },
    "all_agent_messages": all_agent_messages,
    "failure_queue": failure_queue,
}

report_path = Path("D:/test_misc/xd_assignment/tests/e2e_api_test_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False, default=str)

print("\n" + "="*60)
print("FINAL REPORT")
print("="*60)
print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
print(f"\nReport saved to: {report_path}")
