"""Live API tests using FastAPI TestClient with mocked DB."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

print("=" * 60)
print("TEST: API Endpoints (mocked DB)")
print("=" * 60)

# Test 1: Auth endpoint with invalid Emirates ID
print("\n1. POST /api/v1/auth/login (invalid Emirates ID)")
response = client.post("/api/v1/auth/login", json={"emirates_id": "invalid"})
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
assert response.status_code == 400
assert "Invalid" in response.json()["detail"]

# Test 2: Auth endpoint with valid Emirates ID (mocked DB)
print("\n2. POST /api/v1/auth/login (valid Emirates ID, mocked DB)")
import uuid as uuid_mod
with patch("src.api.v1.auth.ApplicantRepository") as mock_app_repo, \
     patch("src.api.v1.auth.ApplicationRepository") as mock_appl_repo:

    mock_app_repo.return_value.get_by_identity_number = AsyncMock(return_value=None)
    mock_app_repo.return_value.create = AsyncMock(return_value=MagicMock(id=uuid_mod.uuid4(), identity_number="784-1990-000000-0"))
    mock_appl_repo.return_value.create = AsyncMock(return_value=MagicMock(id=uuid_mod.uuid4(), applicant_id=uuid_mod.uuid4(), current_phase="intake"))

    response = client.post("/api/v1/auth/login", json={"emirates_id": "784-1990-000000-0"})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["is_new_applicant"] == True
    assert response.json()["current_phase"] == "intake"

# Test 3: Chat endpoint with mocked DB and orchestrator
print("\n3. POST /api/v1/applications/test-id/chat (mocked DB + orchestrator)")
with patch("src.api.v1.chat.ApplicationRepository") as mock_repo, \
     patch("src.api.v1.chat.run_orchestrator") as mock_run:

    mock_repo.return_value.get_by_id = AsyncMock(return_value=MagicMock(id=uuid_mod.uuid4(), applicant_id=uuid_mod.uuid4(), current_phase="intake"))
    mock_repo.return_value.update = AsyncMock()
    mock_run.return_value = {
        "messages": [{"role": "assistant", "content": "Hello! How can I help you?"}],
        "current_phase": "intake",
        "uploaded_documents": [],
        "decision": None,
    }

    response = client.post("/api/v1/applications/test-id/chat", json={"text": "Hello"})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello! How can I help you?"
    assert response.json()["phase"] == "intake"

# Test 4: Chat endpoint with non-existent application
print("\n4. POST /api/v1/applications/nonexistent/chat (not found)")
with patch("src.api.v1.chat.ApplicationRepository") as mock_repo:
    mock_repo.return_value.get_by_id = AsyncMock(return_value=None)

    response = client.post("/api/v1/applications/nonexistent/chat", json={"text": "Hello"})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 404

# Test 5: OpenAPI schema
print("\n5. GET /openapi.json")
response = client.get("/openapi.json")
print(f"   Status: {response.status_code}")
assert response.status_code == 200
paths = response.json().get("paths", {})
print(f"   Endpoints: {list(paths.keys())}")

# Test 6: Orchestrator graph end-to-end
print("\n6. Orchestrator graph end-to-end (all phases)")
from src.agents.orchestrator.graph import build_orchestrator_graph

graph = build_orchestrator_graph()
config = {"configurable": {"thread_id": "test-1"}}

phases = ["intake", "document_collection", "processing", "review", "decision", "enablement"]
for phase in phases:
    result = graph.invoke({
        "messages": [{"role": "user", "content": "test message"}],
        "current_phase": phase,
        "applicant_id": "test-app",
        "application_id": "test-appl",
        "uploaded_files": [],
        "uploaded_documents": [],
        "discrepancies": [],
        "extracted_data": {},
        "validation_errors": [],
        "eligibility_score": None,
        "decision": None,
        "decision_explanation": None,
    }, config=config)
    output_phase = result.get("current_phase")
    last_msg = result.get("messages", [])[-1]
    content = getattr(last_msg, 'content', str(last_msg))[:40]
    print(f"   {phase:22} -> {output_phase:22} | {content}...")

# Test 7: Emirates ID validation
print("\n7. Emirates ID validation")
from src.utils.emirates_id import validate
assert validate("784-1990-000000-0") == True
assert validate("invalid") == False
assert validate("784-1990-000000-9") == False
print("   Valid ID: 784-1990-000000-0 -> True")
print("   Invalid ID: invalid -> False")
print("   Bad checksum: 784-1990-000000-9 -> False")

print()
print("=" * 60)
print("ALL API TESTS PASSED")
print("=" * 60)
