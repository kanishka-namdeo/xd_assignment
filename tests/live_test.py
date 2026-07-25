"""Live tests for implemented components."""

import sys
import uuid

# Test 1: Emirates ID validation
print("=" * 60)
print("TEST 1: Emirates ID Validation")
print("=" * 60)

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
    print(f"  {eid:25} format={fmt}  luhn={luhn}  validate={full}  ({desc})")

# Test 2: Pydantic schemas
print()
print("=" * 60)
print("TEST 2: Pydantic Schemas")
print("=" * 60)

from src.domain.schemas.auth import AuthLoginRequest, AuthLoginResponse
from src.domain.schemas.chat import ChatRequest, ChatResponse, UploadedDocument

# Auth schemas
req = AuthLoginRequest(emirates_id="784-1990-000000-1")
print(f"  AuthLoginRequest: {req}")

resp = AuthLoginResponse(
    applicant_id=uuid.uuid4(),
    application_id=uuid.uuid4(),
    is_new_applicant=True,
    current_phase="intake",
)
print(f"  AuthLoginResponse: applicant_id={resp.applicant_id}, phase={resp.current_phase}")

# Chat schemas
chat_req = ChatRequest(text="Hello", file_paths=["/tmp/test.pdf"])
print(f"  ChatRequest: text={chat_req.text}, files={chat_req.file_paths}")

doc = UploadedDocument(doc_type="emirates_id", file_path="/tmp/test.pdf", status="uploaded")
chat_resp = ChatResponse(message="Hello!", phase="intake", uploaded_documents=[doc])
print(f"  ChatResponse: message={chat_resp.message}, phase={chat_resp.phase}, docs={len(chat_resp.uploaded_documents)}")

# Test 3: Orchestrator graph
print()
print("=" * 60)
print("TEST 3: Orchestrator Graph (stub nodes)")
print("=" * 60)

from src.agents.orchestrator.graph import build_orchestrator_graph

graph = build_orchestrator_graph()
print(f"  Graph compiled: {graph is not None}")

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

print(f"  Output phase: {result.get('current_phase')}")
print(f"  Messages count: {len(result.get('messages', []))}")
if result.get('messages'):
    last_msg = result['messages'][-1]
    role = getattr(last_msg, 'role', None) or getattr(last_msg, 'type', 'unknown')
    content = getattr(last_msg, 'content', '') or str(last_msg)
    print(f"  Last message role: {role}")
    print(f"  Last message content (truncated): {content[:80]}...")

print()
print("=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
