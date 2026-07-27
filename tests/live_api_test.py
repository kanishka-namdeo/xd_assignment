"""Live API tests using FastAPI TestClient with mocked DB."""

import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import structlog

from fastapi.testclient import TestClient

from src.main import app
from src.infrastructure.observability.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)

client = TestClient(app)

logger.info("live_api_tests_started")
t0 = time.time()

# Test 1: Auth endpoint with invalid Emirates ID
logger.info("live_api_test_invalid_eid")
response = client.post("/api/v1/auth/login", json={"emirates_id": "invalid"})
logger.info("live_api_test_invalid_eid_result", status_code=response.status_code, detail=response.json().get("detail"))
assert response.status_code == 400
assert "Invalid" in response.json()["detail"]

# Test 2: Auth endpoint with valid Emirates ID (mocked DB)
logger.info("live_api_test_valid_eid_mocked")
import uuid as uuid_mod
with patch("src.services.auth_service.AuthService.login", return_value={
    "applicant_id": str(uuid_mod.uuid4()),
    "application_id": str(uuid_mod.uuid4()),
    "current_phase": "intake",
    "is_new_applicant": True,
    "state_snapshot": None,
    "identity_number": "784-1990-000000-0",
    "applicant_info": None,
}):
    t1 = time.time()
    response = client.post("/api/v1/auth/login", json={"emirates_id": "784-1990-000000-0"})
    duration_ms = (time.time() - t1) * 1000
    logger.info("live_api_test_valid_eid_result", status_code=response.status_code, duration_ms=round(duration_ms, 1))
    assert response.status_code == 200
    assert response.json()["is_new_applicant"] == True
    assert response.json()["current_phase"] == "intake"

# Test 3: Chat endpoint with mocked DB and orchestrator
logger.info("live_api_test_chat_mocked")
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

    t1 = time.time()
    response = client.post("/api/v1/applications/test-id/chat", json={"text": "Hello"})
    duration_ms = (time.time() - t1) * 1000
    logger.info("live_api_test_chat_result", status_code=response.status_code, duration_ms=round(duration_ms, 1))
    assert response.status_code == 200
    assert response.json()["message"] == "Hello! How can I help you?"
    assert response.json()["phase"] == "intake"

# Test 4: Chat endpoint with non-existent application
logger.info("live_api_test_chat_not_found")
with patch("src.api.v1.chat.ApplicationRepository") as mock_repo:
    mock_repo.return_value.get_by_id = AsyncMock(return_value=None)

    t1 = time.time()
    response = client.post("/api/v1/applications/nonexistent/chat", json={"text": "Hello"})
    duration_ms = (time.time() - t1) * 1000
    logger.info("live_api_test_chat_not_found_result", status_code=response.status_code, duration_ms=round(duration_ms, 1))
    assert response.status_code == 404

# Test 5: OpenAPI schema
logger.info("live_api_test_openapi")
t1 = time.time()
response = client.get("/openapi.json")
duration_ms = (time.time() - t1) * 1000
assert response.status_code == 200
paths = response.json().get("paths", {})
logger.info("live_api_test_openapi_result", endpoint_count=len(paths), duration_ms=round(duration_ms, 1))

# Test 6: Orchestrator graph end-to-end
logger.info("live_api_test_orchestrator_graph")
from src.agents.orchestrator.graph import build_orchestrator_graph

graph = build_orchestrator_graph()
config = {"configurable": {"thread_id": "test-1"}}

phases = ["intake", "document_collection", "processing", "review", "decision", "enablement"]
for phase in phases:
    t1 = time.time()
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
    duration_ms = (time.time() - t1) * 1000
    output_phase = result.get("current_phase")
    logger.info("live_api_test_orchestrator_phase", input_phase=phase, output_phase=output_phase, duration_ms=round(duration_ms, 1))

# Test 7: Emirates ID validation
logger.info("live_api_test_emirates_id_validation")
from src.utils.emirates_id import validate
assert validate("784-1990-000000-0") == True
assert validate("invalid") == False
assert validate("784-1990-000000-9") == False
logger.info("live_api_test_emirates_id_validation_result", valid_id=True, invalid_id=False, bad_checksum=False)

total_duration_ms = (time.time() - t0) * 1000
logger.info("live_api_tests_completed", total_duration_ms=round(total_duration_ms, 1))
