"""
Continue E2E test from application_id after document upload timeout.
"""

import requests
import time
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
APPLICATION_ID = "54ef66f2-fe21-42f2-8bda-49ce73d6bbbf"

results = []
agent_messages = []


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


def get_application():
    """Get current application state."""
    resp = requests.get(
        f"{BASE_URL}/applications/{APPLICATION_ID}",
        timeout=30,
    )
    return resp.json()


def send_chat(message, timeout_sec=300):
    """Send a chat message."""
    resp = requests.post(
        f"{BASE_URL}/applications/{APPLICATION_ID}/chat",
        data={"text": message},
        timeout=timeout_sec,
    )
    return resp


def step_3_verify_documents():
    """Step 3: Verify documents were uploaded and classified."""
    print("\n>>> STEP 3: Verify Document Upload")

    upload_dir = Path(f"D:/test_misc/xd_assignment/data/uploads/{APPLICATION_ID}")
    if not upload_dir.exists():
        return log_step(
            "Document Upload",
            False,
            0,
            "Upload directory not found",
            f"Directory {upload_dir} does not exist",
        )

    saved_files = list(upload_dir.glob("*"))
    file_names = [f.name for f in saved_files]

    print(f"  Files saved: {file_names}")

    expected = {
        "emirates_id_front.png",
        "emirates_id_back.png",
        "bank_statement.pdf",
        "credit_report.pdf",
        "resume.docx",
        "assets_liabilities.xlsx",
        "application_form.png",
    }

    saved_set = set(file_names)
    missing = expected - saved_set

    if missing:
        return log_step(
            "Document Upload",
            False,
            0,
            f"Saved: {file_names}",
            f"Missing files: {missing}",
        )

    return log_step(
        "Document Upload",
        True,
        0,
        f"All 7 documents saved: {file_names}",
    )


def step_4_processing():
    """Step 4: Processing — Poll until phase is no longer 'processing' or 'document_collection'."""
    print("\n>>> STEP 4: Processing")

    start = time.time()
    max_wait = 180
    poll_interval = 5
    final_phase = None
    last_data = None

    for attempt in range(max_wait // poll_interval):
        elapsed = time.time() - start
        if elapsed > max_wait:
            break

        data = get_application()
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

    if final_phase == "processing" or final_phase == "document_collection":
        return log_step(
            "Processing",
            False,
            latency,
            f"Still {final_phase} after {max_wait}s",
            f"Timeout: phase stuck at '{final_phase}'",
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
    data = get_application()

    # Check for interrupt with discrepancies
    interrupt = data.get("interrupt") or data.get("_pending_interrupt")
    discrepancies = interrupt.get("discrepancies", []) if interrupt else []
    missing_docs = interrupt.get("missing_documents", []) if interrupt else []
    question = interrupt.get("question", "") if interrupt else ""

    print(f"  Discrepancies: {len(discrepancies)}")
    print(f"  Missing documents: {len(missing_docs)}")
    print(f"  Question: {question[:100] if question else 'N/A'}")

    # Send clarifying message
    clarification = "I confirm that all the information I provided is accurate and complete. "
    if discrepancies:
        clarification += "Any discrepancies are due to legitimate reasons such as timing differences or data entry variations. "
    clarification += "Please proceed with my application."

    start = time.time()
    resp = send_chat(clarification)
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
            data = get_application()
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


def step_6_decision():
    """Step 6: Decision — Assert decision and eligibility_score."""
    print("\n>>> STEP 6: Decision")

    start = time.time()
    data = get_application()
    latency = (time.time() - start) * 1000

    print(f"  Response: {json.dumps(data, indent=2)}")

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


def step_7_enablement():
    """Step 7: Enablement — Ask for personalized recommendations."""
    print("\n>>> STEP 7: Enablement")

    # First check current phase
    data = get_application()
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
        ), None

    start = time.time()
    resp = send_chat(
        "What support am I eligible for? Please tell me about the programs and benefits available to me.",
        timeout_sec=120,
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
        ), None

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
        "application_id": APPLICATION_ID,
        "emirates_id": "784-1960-1005207-2",
        "per_step_results": results,
        "overall": {
            "decision": decision,
            "eligibility_score": eligibility_score,
            "steps_passed": sum(1 for r in results if r["passed"]),
            "steps_total": len(results),
        },
        "agent_messages": agent_messages,
    }

    return report


def main():
    """Run continuation E2E test steps."""
    print("=" * 60)
    print("CONTINUATION E2E API TEST")
    print(f"Application ID: {APPLICATION_ID}")
    print(f"Start time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Verify initial state
    app = get_application()
    print(f"\nCurrent phase: {app.get('current_phase')}")

    # Step 3: Verify document upload
    step_3_verify_documents()

    # Trigger processing by sending a chat message
    print("\n>>> Triggering processing...")
    resp = send_chat(
        "I have uploaded all my required documents. Please proceed with processing my application.",
        timeout_sec=300,
    )
    print(f"  Trigger response status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Response phase: {data.get('phase', data.get('current_phase', 'N/A'))}")
        print(f"  Response message: {data.get('message', '')[:200]}")
        if data.get("message"):
            agent_messages.append({"step": "document_upload", "message": data.get("message", "")})

    # Step 4: Processing
    proc_result = step_4_processing()
    final_phase = proc_result[1]

    if not proc_result[0]["passed"]:
        print("\nPROCESSING FAILED or TIMED OUT")
        report = generate_report()
        print("\n" + json.dumps(report, indent=2, ensure_ascii=False))
        return report

    # Step 5: Review (if applicable)
    if final_phase == "review":
        review_result = step_5_review(APPLICATION_ID, final_phase)
    elif final_phase == "decision":
        log_step("Review", True, 0, "Skipped — already in decision phase")
    else:
        log_step("Review", False, 0, f"Phase is {final_phase}", "Not in review or decision")

    # Step 6: Decision
    decision_result = step_6_decision()
    if not decision_result[0]["passed"]:
        print("\nDECISION CHECK FAILED")

    # Step 7: Enablement
    step_7_enablement()

    # Generate final report
    report = generate_report()

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Save report to file
    report_path = Path("D:/test_misc/xd_assignment/evals/live_e2e_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_path}")

    return report


if __name__ == "__main__":
    report = main()
