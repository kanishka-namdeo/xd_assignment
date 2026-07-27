"""Test script to verify the infinite loop fix in document_collection."""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_no_infinite_loop():
    """Test that document_collection doesn't loop back when no new documents are uploaded."""
    
    # Create a test application
    print("1. Creating test application...")
    response = requests.post(f"{BASE_URL}/applications", json={
        "applicant_name": "Test User",
        "support_category": "family_support"
    })
    assert response.status_code == 200, f"Failed to create application: {response.text}"
    app_data = response.json()
    app_id = app_data["application_id"]
    print(f"   Created application: {app_id}")
    
    # Upload some test documents (simulated)
    print("\n2. Uploading test documents...")
    # We'll simulate by directly updating state via a test endpoint
    # For now, let's just trigger the document_collection node
    
    # Trigger document_collection with no new documents
    print("\n3. Triggering document_collection node (no new docs)...")
    response = requests.post(
        f"{BASE_URL}/applications/{app_id}/process",
        json={"phase": "document_collection"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   Phase after processing: {result.get('current_phase')}")
        print(f"   New documents uploaded: {result.get('new_documents_uploaded')}")
        
        # The key test: new_documents_uploaded should be False when no new docs
        if result.get('new_documents_uploaded') == False:
            print("\n✓ SUCCESS: Loop fix is working correctly!")
            print("  The flag is False when no new documents are uploaded.")
            return True
        else:
            print("\n✗ FAIL: Loop fix not working!")
            print(f"  Expected new_documents_uploaded=False, got {result.get('new_documents_uploaded')}")
            return False
    else:
        print(f"   Error: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

if __name__ == "__main__":
    try:
        success = test_no_infinite_loop()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
