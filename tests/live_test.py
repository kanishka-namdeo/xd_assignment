"""Live tests for implemented components."""

import sys
import time
import uuid

import structlog

from src.infrastructure.observability.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)

logger.info("live_test_suite_started")

# Test 1: Emirates ID validation
logger.info("live_test_emirates_id_validation_started")
t0 = time.time()
from src.utils.emirates_id import validate, validate_format, validate_luhn, luhn_check_digit

# Valid Emirates ID (784-1990-000000-0) - format valid, let's check Luhn
test_ids = [
    ("784-1990-000000-0", "valid format + luhn"),
    ("78419900000000", "valid format (no dashes)"),
    ("123-4567-890123-4", "valid format"),
    ("invalid", "invalid format"),
    ("", "empty"),
    ("784-1990-000000-9", "bad checksum"),
]

for eid, desc in test_ids:
    fmt = validate_format(eid)
    luhn = validate_luhn(eid) if fmt else False
    full = validate(eid)
    logger.info("live_test_emirates_id_validated", emirates_id=eid, format_valid=fmt, luhn_valid=luhn, valid=full, description=desc)

duration_ms = (time.time() - t0) * 1000
logger.info("live_test_emirates_id_validation_completed", duration_ms=round(duration_ms, 1))

# Test 2: Pydantic schemas
logger.info("live_test_pydantic_schemas_started")
t0 = time.time()
from src.domain.schemas.auth import AuthLoginRequest, AuthLoginResponse
from src.domain.schemas.chat import ChatRequest, ChatResponse, UploadedDocument

# Auth schemas
req = AuthLoginRequest(emirates_id="784-1990-000000-1")
resp = AuthLoginResponse(
    applicant_id=uuid.uuid4(),
    application_id=uuid.uuid4(),
    is_new_applicant=True,
    current_phase="intake",
)
logger.info("live_test_auth_schemas_validated", applicant_id=str(resp.applicant_id), phase=resp.current_phase)

# Chat schemas
chat_req = ChatRequest(text="Hello", file_paths=["/tmp/test.pdf"])
doc = UploadedDocument(doc_type="emirates_id", file_path="/tmp/test.pdf", status="uploaded")
chat_resp = ChatResponse(message="Hello!", phase="intake", uploaded_documents=[doc])
logger.info("live_test_chat_schemas_validated", phase=chat_resp.phase, doc_count=len(chat_resp.uploaded_documents))

duration_ms = (time.time() - t0) * 1000
logger.info("live_test_pydantic_schemas_completed", duration_ms=round(duration_ms, 1))

# Test 3: Orchestrator graph
logger.info("live_test_orchestrator_graph_started")
t0 = time.time()
from src.agents.orchestrator.graph import build_orchestrator_graph

graph = build_orchestrator_graph()
logger.info("live_test_graph_compiled", compiled=graph is not None)

# Run through intake phase
config = {"configurable": {"thread_id": "test-thread-1"}}
result = graph.invoke({
    "messages": [{"role": "user", "content": "Hello, I want to apply for support"}],
    "current_phase": "intake",
    "applicant_id": str(uuid.uuid4()),
    "application_id": str(uuid.uuid4()),
    "uploaded_files": [],
    "uploaded_documents": [],
    "discrepancies": [],
    "extracted_data": {},
    "validation_errors": [],
    "eligibility_score": None,
    "decision": None,
    "decision_explanation": None,
}, config=config)

logger.info(
    "live_test_graph_invoked",
    output_phase=result.get("current_phase"),
    message_count=len(result.get("messages", [])),
)

duration_ms = (time.time() - t0) * 1000
logger.info("live_test_orchestrator_graph_completed", duration_ms=round(duration_ms, 1))

logger.info("live_test_suite_completed")
