"""Test session recovery - re-authentication with same Emirates ID."""
import time

import requests
import structlog
from src.infrastructure.observability.logging import configure_logging
from src.utils.emirates_id import luhn_check_digit

configure_logging()

logger = structlog.get_logger(__name__)

API_BASE = "http://localhost:8000"


def generate_unique_emirates_id() -> str:
    """Generate a truly unique Emirates ID."""
    import time
    timestamp = int(time.time() * 1000) % 10000000
    year = 1990
    body = f"784{year}{timestamp:07d}"
    check = luhn_check_digit(body)
    return f"784-{year}-{timestamp:07d}-{check}"


def test_auth(emirates_id: str) -> dict:
    """Test authentication."""
    print(f"\nAuthenticating with Emirates ID: {emirates_id}")
    try:
        start = time.time()
        resp = requests.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"emirates_id": emirates_id},
            timeout=30
        )
        duration_ms = (time.time() - start) * 1000
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Applicant ID: {data['applicant_id']}")
            print(f"Application ID: {data['application_id']}")
            print(f"Phase: {data['current_phase']}")
            print(f"Is new: {data['is_new_applicant']}")
            logger.info("auth_login", status_code=resp.status_code, duration_ms=round(duration_ms, 2), application_id=data.get("application_id"), is_new=data.get("is_new_applicant"))
            return data
        else:
            print(f"Error: {resp.text}")
            logger.warning("auth_failed", status_code=resp.status_code, duration_ms=round(duration_ms, 2))
            return {}
    except Exception as e:
        logger.exception("auth_exception")
        print(f"Exception: {e}")
        return {}


def test_chat(application_id: str, message: str) -> dict:
    """Send chat message."""
    print(f"\nSending chat message to {application_id}")
    try:
        start = time.time()
        resp = requests.post(
            f"{API_BASE}/api/v1/applications/{application_id}/chat",
            data={"text": message},
            timeout=30
        )
        duration_ms = (time.time() - start) * 1000
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Phase: {data['phase']}")
            print(f"Message: {data['message'][:100]}...")
            logger.info("chat_message", application_id=application_id, status_code=resp.status_code, duration_ms=round(duration_ms, 2), phase=data.get("phase"))
            return data
        else:
            print(f"Error: {resp.text}")
            logger.warning("chat_error", application_id=application_id, status_code=resp.status_code, duration_ms=round(duration_ms, 2))
            return {}
    except Exception as e:
        logger.exception("chat_exception")
        print(f"Exception: {e}")
        return {}


def main():
    """Test session recovery."""
    print("=" * 70)
    print("SESSION RECOVERY TEST")
    print("=" * 70)

    start_time = time.time()
    logger.info("test_start", script="test_session_recovery")

    # Generate unique Emirates ID
    emirates_id = generate_unique_emirates_id()

    # First authentication
    print("\n[Step 1] First authentication")
    auth_data = test_auth(emirates_id)
    if not auth_data:
        print("FAILED: First authentication")
        return
    app_id = auth_data['application_id']

    # Send intake message
    print("\n[Step 2] Send intake message")
    chat_data = test_chat(app_id, "I am divorced with 2 children. I work as admin assistant.")
    if not chat_data:
        print("FAILED: Intake message")
        return

    # Re-authenticate with same Emirates ID
    print("\n[Step 3] Re-authenticate with same Emirates ID")
    auth_data2 = test_auth(emirates_id)
    if not auth_data2:
        print("FAILED: Re-authentication")
        return

    # Check if same application
    if auth_data2['application_id'] == app_id:
        print("SUCCESS: Same application ID returned")
    else:
        print(f"FAILED: Different application ID: {auth_data2['application_id']}")

    duration_ms = (time.time() - start_time) * 1000
    logger.info("session_recovery_test_complete", duration_ms=round(duration_ms, 2), recovered=auth_data2['application_id'] == app_id)

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    logger.info("test_complete", script="test_session_recovery", recovered=auth_data2['application_id'] == app_id)


if __name__ == "__main__":
    main()
