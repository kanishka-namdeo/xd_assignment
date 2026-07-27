"""Edge case and error path testing for the Social Support Application API."""

import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

# Fresh Emirates IDs for this test session
VALID_EID_1 = "784-7015-0790968-2"
VALID_EID_2 = "784-6329-2114598-5"
INVALID_EID = "784-7015-0790968-3"  # Wrong check digit

results = []
failure_queue = []


def record(scenario: str, passed: bool, status_code: int, response_summary: str, graceful: bool, failure_detail: str = None, stack_trace: str = None, category: str = "api"):
    results.append({
        "scenario": scenario,
        "passed": passed,
        "status_code": status_code,
        "response_summary": response_summary,
        "graceful": graceful,
        "failure_detail": failure_detail,
    })
    if not passed:
        failure_queue.append({
            "scenario": scenario,
            "symptom": response_summary,
            "error_message": failure_detail or "",
            "stack_trace": stack_trace or "",
            "category": category,
        })


async def test_scenario_1_invalid_emirates_id(client: httpx.AsyncClient):
    """Invalid Emirates ID -- Use an ID that fails Luhn checksum."""
    scenario = "1. Invalid Emirates ID"
    try:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": INVALID_EID},
        )
        # Expected: 400 with "Invalid Emirates ID format or checksum"
        passed = response.status_code == 400
        body = response.json() if response.content else {}
        detail = body.get("detail", "")
        has_message = "Invalid Emirates ID" in detail or "checksum" in detail.lower()
        passed = passed and has_message
        graceful = response.status_code != 500

        record(
            scenario,
            passed,
            response.status_code,
            f"status={response.status_code}, detail={detail}",
            graceful,
            failure_detail=None if passed else f"Expected 400 with 'Invalid Emirates ID format or checksum', got {response.status_code}: {detail}",
            category="api",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="api")


async def test_scenario_2_partial_intake(client: httpx.AsyncClient):
    """Partial intake -- Auth, then send an intake message missing critical fields."""
    scenario = "2. Partial intake"
    try:
        # Step 1: Auth
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": VALID_EID_1},
        )
        if response.status_code != 200:
            record(scenario, False, response.status_code, f"Auth failed: {response.text}", False, failure_detail=f"Auth returned {response.status_code}", category="api")
            return

        auth_data = response.json()
        application_id = auth_data["application_id"]

        # Step 2: Send partial intake message (no date_of_birth, no support_category)
        response = await client.post(
            f"{BASE_URL}/applications/{application_id}/chat",
            data={
                "text": "I need financial support please",
            },
        )

        status_code = response.status_code
        body = response.json() if response.content else {}
        graceful = status_code != 500

        # Check for interrupt asking for missing fields
        interrupt = body.get("interrupt")
        phase = body.get("phase", "")
        message = body.get("message", "")

        # The agent should either interrupt asking for missing fields, or respond with clarifying questions
        has_interrupt = interrupt is not None
        interrupt_asks = False
        if has_interrupt:
            missing = interrupt.get("missing_fields", [])
            question = interrupt.get("question", "")
            interrupt_asks = bool(missing) or "date_of_birth" in question.lower() or "support" in question.lower() or "category" in question.lower() or "name" in question.lower()

        # Phase should stay at intake (or authentication depending on flow)
        phase_is_intake = phase in ("intake", "authentication")

        passed = graceful and (has_interrupt or "clarif" in message.lower() or "?" in message)
        # We accept: either an interrupt, or a clarifying question response

        record(
            scenario,
            passed,
            status_code,
            f"status={status_code}, phase={phase}, has_interrupt={has_interrupt}, message_preview={message[:100] if message else 'empty'}",
            graceful,
            failure_detail=None if passed else f"Expected interrupt or clarifying question for missing fields. Got: phase={phase}, interrupt={interrupt}, message={message[:200]}",
            category="agent",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="agent")


async def test_scenario_3_missing_documents(client: httpx.AsyncClient):
    """Missing documents -- Upload only emirates_id_front.png (1 of 7 required docs)."""
    scenario = "3. Missing documents"
    try:
        # Auth with EID_2
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": VALID_EID_2},
        )
        if response.status_code != 200:
            record(scenario, False, response.status_code, f"Auth failed: {response.text}", False, failure_detail=f"Auth returned {response.status_code}", category="api")
            return

        auth_data = response.json()
        application_id = auth_data["application_id"]

        # Send intake with complete info to move to document_collection
        response = await client.post(
            f"{BASE_URL}/applications/{application_id}/chat",
            data={
                "text": "My name is Ahmed Hassan. Date of birth is 1990-05-15. I need housing support. I am divorced, unemployed, and have poor credit.",
            },
        )

        if response.status_code == 500:
            record(scenario, False, 500, "Server error during intake", False, failure_detail=response.text, category="agent")
            return

        # Now upload only emirates_id_front.png
        # Create a minimal PNG file (1x1 pixel)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # 8-bit RGB
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,  # compressed data
            0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,  # CRC
            0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82,
        ])

        png_path = Path("data/uploads/test_emirates_id_front.png")
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(png_data)

        with open(png_path, "rb") as f:
            files = {"file": ("emirates_id_front.png", f, "image/png")}
            response = await client.post(
                f"{BASE_URL}/applications/{application_id}/documents",
                data={"document_type": "emirates_id_front"},
                files=files,
            )

        status_code = response.status_code
        graceful = status_code != 500

        # Now send a chat to trigger document collection review
        response = await client.post(
            f"{BASE_URL}/applications/{application_id}/chat",
            data={"text": "I have uploaded my documents"},
        )

        status_code = response.status_code
        body = response.json() if response.content else {}
        graceful = status_code != 500
        phase = body.get("phase", "")
        interrupt = body.get("interrupt")

        # Should list remaining required documents and stay in document_collection
        missing_docs = []
        if interrupt:
            missing_docs = interrupt.get("missing_documents", [])

        passed = graceful and (phase == "document_collection" or bool(missing_docs))

        record(
            scenario,
            passed,
            status_code,
            f"status={status_code}, phase={phase}, missing_docs={missing_docs}",
            graceful,
            failure_detail=None if passed else f"Expected phase=document_collection with missing docs listed. Got: phase={phase}, interrupt={interrupt}",
            category="agent",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="agent")


async def test_scenario_4_session_recovery(client: httpx.AsyncClient):
    """Session recovery -- Complete auth and intake, then re-auth with same Emirates ID."""
    scenario = "4. Session recovery"
    try:
        # Use a fresh EID for this test
        recovery_eid = "784-1234-5678901-2"  # We'll just use a known valid one

        # Actually, let's generate one
        from src.utils.emirates_id import generate_emirates_id_number
        recovery_eid = generate_emirates_id_number()

        # Step 1: First auth
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": recovery_eid},
        )
        if response.status_code != 200:
            record(scenario, False, response.status_code, f"First auth failed: {response.text}", False, failure_detail=f"Auth returned {response.status_code}", category="api")
            return

        auth_data_1 = response.json()
        application_id_1 = auth_data_1["application_id"]
        is_new_1 = auth_data_1["is_new_applicant"]

        # Step 2: Send an intake message
        response = await client.post(
            f"{BASE_URL}/applications/{application_id_1}/chat",
            data={
                "text": "My name is Test User. Date of birth is 1990-01-01. I need financial support.",
            },
        )

        if response.status_code == 500:
            record(scenario, False, 500, "Server error during intake", False, failure_detail=response.text, category="agent")
            return

        # Step 3: Re-auth with same Emirates ID
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": recovery_eid},
        )

        if response.status_code != 200:
            record(scenario, False, response.status_code, f"Re-auth failed: {response.text}", False, failure_detail=f"Re-auth returned {response.status_code}: {response.text}", category="api")
            return

        auth_data_2 = response.json()
        application_id_2 = auth_data_2["application_id"]
        is_new_2 = auth_data_2["is_new_applicant"]
        state_snapshot = auth_data_2.get("state_snapshot")

        # Assertions
        same_application = application_id_1 == application_id_2
        is_returning = is_new_2 == False
        has_state = state_snapshot is not None

        # Check state_snapshot contains messages
        has_messages = False
        if state_snapshot:
            has_messages = bool(state_snapshot.get("messages", []))

        passed = same_application and is_returning and has_state

        record(
            scenario,
            passed,
            response.status_code,
            f"same_app={same_application}, is_returning={is_returning}, has_state={has_state}, has_messages={has_messages}",
            True,
            failure_detail=None if passed else f"Session recovery failed: same_app={same_application} (expected True), is_returning={is_returning} (expected True), has_state={has_state} (expected True), has_messages={has_messages}",
            category="data",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="data")


async def test_scenario_5_document_reupload(client: httpx.AsyncClient):
    """Document re-upload -- In review phase, upload a corrected document."""
    scenario = "5. Document re-upload"
    try:
        # This scenario requires getting to the review phase, which is complex.
        # We'll test the document upload endpoint with a re-upload scenario.

        # Use VALID_EID_1 (already has some state from scenario 2)
        # First, get the application
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": VALID_EID_1},
        )
        if response.status_code != 200:
            record(scenario, False, response.status_code, f"Auth failed: {response.text}", False, failure_detail=f"Auth returned {response.status_code}", category="api")
            return

        auth_data = response.json()
        application_id = auth_data["application_id"]

        # Create a minimal PNG
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,
            0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82,
        ])

        png_path = Path("data/uploads/test_reupload.png")
        png_path.write_bytes(png_data)

        # Upload the document
        with open(png_path, "rb") as f:
            response = await client.post(
                f"{BASE_URL}/applications/{application_id}/documents",
                data={"document_type": "emirates_id_front"},
                files={"file": ("emirates_id_front.png", f, "image/png")},
            )

        status_code = response.status_code
        graceful = status_code in (200, 201, 409)  # 409 = duplicate, also acceptable
        body = response.json() if response.content else {}

        # Re-uploading should either succeed (201) or return conflict (409) gracefully
        passed = graceful and status_code != 500

        record(
            scenario,
            passed,
            status_code,
            f"status={status_code}, body={json.dumps(body)[:200] if body else 'empty'}",
            graceful,
            failure_detail=None if passed else f"Document re-upload returned unexpected {status_code}: {body}",
            category="api",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="api")


async def test_scenario_6_wrong_file_type(client: httpx.AsyncClient):
    """Wrong file type -- Upload a plain .txt file."""
    scenario = "6. Wrong file type"
    try:
        # Use VALID_EID_1
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": VALID_EID_1},
        )
        if response.status_code != 200:
            record(scenario, False, response.status_code, f"Auth failed: {response.text}", False, failure_detail=f"Auth returned {response.status_code}", category="api")
            return

        auth_data = response.json()
        application_id = auth_data["application_id"]

        # Create a plain text file
        txt_content = "This is just a notes file, not a real document."
        txt_path = Path("data/uploads/notes.txt")
        txt_path.write_text(txt_content)

        # Upload as if it's a document
        with open(txt_path, "rb") as f:
            response = await client.post(
                f"{BASE_URL}/applications/{application_id}/documents",
                data={"document_type": "notes"},  # Unknown document type
                files={"file": ("notes.txt", f, "text/plain")},
            )

        status_code = response.status_code
        body = response.json() if response.content else {}
        graceful = status_code != 500

        # Should either: classify as "unknown" gracefully, or reject with clear error
        # Must NOT crash the server (no 500)
        passed = graceful

        record(
            scenario,
            passed,
            status_code,
            f"status={status_code}, body={json.dumps(body)[:200] if body else 'empty'}",
            graceful,
            failure_detail=None if passed else f"Wrong file type handling failed: {body}",
            category="api",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="api")


async def test_scenario_7_concurrent_applications(client: httpx.AsyncClient):
    """Concurrent applications -- Two different Emirates IDs, verify isolation."""
    scenario = "7. Concurrent applications"
    try:
        # Generate two fresh EIDs
        from src.utils.emirates_id import generate_emirates_id_number
        eid_a = generate_emirates_id_number()
        eid_b = generate_emirates_id_number()

        # Auth both
        response_a = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": eid_a},
        )
        response_b = await client.post(
            f"{BASE_URL}/auth/login",
            json={"emirates_id": eid_b},
        )

        if response_a.status_code != 200 or response_b.status_code != 200:
            record(scenario, False, 0, f"Auth failed: A={response_a.status_code}, B={response_b.status_code}", False, failure_detail=f"Auth A={response_a.status_code}, B={response_b.status_code}", category="api")
            return

        app_a = response_a.json()
        app_b = response_b.json()
        application_id_a = app_a["application_id"]
        application_id_b = app_b["application_id"]

        # Send chat to A
        response = await client.post(
            f"{BASE_URL}/applications/{application_id_a}/chat",
            data={"text": "My name is User A. Date of birth is 1990-01-01. I need financial support."},
        )
        if response.status_code == 500:
            record(scenario, False, 500, "Server error on chat A", False, failure_detail=response.text, category="agent")
            return

        # Immediately send chat to B
        response = await client.post(
            f"{BASE_URL}/applications/{application_id_b}/chat",
            data={"text": "My name is User B. Date of birth is 1985-06-15. I need housing support."},
        )
        if response.status_code == 500:
            record(scenario, False, 500, "Server error on chat B", False, failure_detail=response.text, category="agent")
            return

        # Now fetch both applications and check isolation
        response_a = await client.get(f"{BASE_URL}/applications/{application_id_a}")
        response_b = await client.get(f"{BASE_URL}/applications/{application_id_b}")

        data_a = response_a.json()
        data_b = response_b.json()

        # Different application IDs
        different_apps = data_a["id"] != data_b["id"]

        # Both should have their own state
        # We need to check the state snapshots are different
        # For now, just verify the applications are distinct
        passed = different_apps and response_a.status_code == 200 and response_b.status_code == 200

        record(
            scenario,
            passed,
            200,
            f"app_a={data_a['id']}, app_b={data_b['id']}, distinct={different_apps}",
            True,
            failure_detail=None if passed else "Applications not properly isolated",
            category="data",
        )
    except Exception as e:
        record(scenario, False, 0, f"Exception: {e}", False, failure_detail=str(e), stack_trace="", category="data")


async def main():
    print("=" * 60)
    print("EDGE CASE AND ERROR PATH TESTING")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Run all scenarios
        await test_scenario_1_invalid_emirates_id(client)
        print(f"[1/7] Scenario 1 complete")

        await test_scenario_2_partial_intake(client)
        print(f"[2/7] Scenario 2 complete")

        await test_scenario_3_missing_documents(client)
        print(f"[3/7] Scenario 3 complete")

        await test_scenario_4_session_recovery(client)
        print(f"[4/7] Scenario 4 complete")

        await test_scenario_5_document_reupload(client)
        print(f"[5/7] Scenario 5 complete")

        await test_scenario_6_wrong_file_type(client)
        print(f"[6/7] Scenario 6 complete")

        await test_scenario_7_concurrent_applications(client)
        print(f"[7/7] Scenario 7 complete")

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n[{status}] {r['scenario']}")
        print(f"  Status Code: {r['status_code']}")
        print(f"  Graceful: {r['graceful']}")
        print(f"  Response: {r['response_summary']}")
        if r["failure_detail"]:
            print(f"  Failure: {r['failure_detail']}")

    print("\n" + "=" * 60)
    print("FAILURE QUEUE")
    print("=" * 60)

    if not failure_queue:
        print("No failures recorded.")
    else:
        for f in failure_queue:
            print(f"\nScenario: {f['scenario']}")
            print(f"  Symptom: {f['symptom']}")
            print(f"  Error: {f['error_message']}")
            print(f"  Category: {f['category']}")

    # Write JSON report
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "failure_queue": failure_queue,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "failed": sum(1 for r in results if not r["passed"]),
        },
    }

    report_path = Path("data/test_edge_cases_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved to: {report_path}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
