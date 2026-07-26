"""Test session recovery - re-authentication with same Emirates ID."""
import requests
from src.utils.emirates_id import luhn_check_digit

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
        resp = requests.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"emirates_id": emirates_id},
            timeout=30
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Applicant ID: {data['applicant_id']}")
            print(f"Application ID: {data['application_id']}")
            print(f"Phase: {data['current_phase']}")
            print(f"Is new: {data['is_new_applicant']}")
            return data
        else:
            print(f"Error: {resp.text}")
            return {}
    except Exception as e:
        print(f"Exception: {e}")
        return {}


def test_chat(application_id: str, message: str) -> dict:
    """Send chat message."""
    print(f"\nSending chat message to {application_id}")
    try:
        resp = requests.post(
            f"{API_BASE}/api/v1/applications/{application_id}/chat",
            data={"text": message},
            timeout=30
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Phase: {data['phase']}")
            print(f"Message: {data['message'][:100]}...")
            return data
        else:
            print(f"Error: {resp.text}")
            return {}
    except Exception as e:
        print(f"Exception: {e}")
        return {}


def main():
    """Test session recovery."""
    print("=" * 70)
    print("SESSION RECOVERY TEST")
    print("=" * 70)
    
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
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
