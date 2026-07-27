"""Test unconventional flows - invalid documents, missing docs, edge cases."""
import requests
from pathlib import Path
import json

import structlog
from src.infrastructure.observability.logging import configure_logging

configure_logging()

logger = structlog.get_logger(__name__)


def test_invalid_document_type():
    """Test uploading unsupported file types."""
    logger.info("test_start", name="invalid_document_type")
    print("\n=== Test: Invalid Document Type ===")

    start = time.time()

    auth_response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'emirates_id': '784-1990-1234567-6'}
    )

    app_id = auth_response.json()['application_id']

    logger.info("auth_login", application_id=app_id, status_code=auth_response.status_code)

    requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'}
    )

    invalid_files = [
        ('test.txt', b'This is a text file', 'text/plain'),
        ('test.exe', b'EXE content', 'application/octet-stream'),
        ('test.zip', b'ZIP content', 'application/zip'),
    ]

    response = requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'Here are my documents'},
        files=[('files', (name, content, mime)) for name, content, mime in invalid_files]
    )

    duration_ms = (time.time() - start) * 1000

    data = response.json()
    print(f'Status: {response.status_code}')
    print(f'Phase: {data.get("phase")}')
    print(f'Message: {data.get("message", "")[:200]}')
    print(f'Documents: {len(data.get("uploaded_documents", []))}')

    logger.info("invalid_document_upload", application_id=app_id, status_code=response.status_code, duration_ms=round(duration_ms, 2), uploaded_count=len(data.get("uploaded_documents", [])), phase=data.get("phase"))

    return app_id


def test_missing_documents():
    """Test proceeding with incomplete document set."""
    logger.info("test_start", name="missing_documents")
    print("\n=== Test: Missing Required Documents ===")

    start = time.time()

    auth_response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'emirates_id': '784-1985-9876543-2'}
    )
    app_id = auth_response.json()['application_id']

    logger.info("auth_login", application_id=app_id, status_code=auth_response.status_code)

    requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'}
    )

    doc_dir = 'data/test_applicants/divorced_employed_good_credit'
    partial_files = [
        ('emirates_id_front.png', open(f'{doc_dir}/emirates_id_front.png', 'rb')),
        ('bank_statement.pdf', open(f'{doc_dir}/bank_statement.pdf', 'rb')),
    ]

    response = requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'Here are some of my documents'},
        files=[('files', (name, f)) for name, f in partial_files]
    )

    duration_ms = (time.time() - start) * 1000

    data = response.json()
    print(f'Status: {response.status_code}')
    print(f'Phase: {data.get("phase")}')
    print(f'Message: {data.get("message", "")[:200]}')
    print(f'Documents: {len(data.get("uploaded_documents", []))}')

    logger.info("partial_document_upload", application_id=app_id, status_code=response.status_code, duration_ms=round(duration_ms, 2), uploaded_count=len(data.get("uploaded_documents", [])), phase=data.get("phase"))

    for _, f in partial_files:
        f.close()

    return app_id


def test_empty_upload():
    """Test chat without any document upload."""
    logger.info("test_start", name="empty_upload")
    print("\n=== Test: Empty Upload (Chat Only) ===")

    start = time.time()

    auth_response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'emirates_id': '784-1980-5555555-5'}
    )
    app_id = auth_response.json()['application_id']

    logger.info("auth_login", application_id=app_id, status_code=auth_response.status_code)

    requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'}
    )

    response = requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I need more time to gather my documents'}
    )

    duration_ms = (time.time() - start) * 1000

    data = response.json()
    print(f'Status: {response.status_code}')
    print(f'Phase: {data.get("phase")}')
    print(f'Message: {data.get("message", "")[:200]}')
    print(f'Has interrupt: {data.get("interrupt") is not None}')

    logger.info("chat_only_no_documents", application_id=app_id, status_code=response.status_code, duration_ms=round(duration_ms, 2), phase=data.get("phase"), has_interrupt=data.get("interrupt") is not None)

    return app_id


if __name__ == '__main__':
    import time

    logger.info("unconventional_test_suite_start")
    print("=" * 60)
    print("Unconventional Flow Tests")
    print("=" * 60)

    try:
        test_invalid_document_type()
    except Exception as e:
        logger.exception("test_error", test="invalid_document_type")
        print(f"Error in invalid document test: {e}")

    try:
        test_missing_documents()
    except Exception as e:
        logger.exception("test_error", test="missing_documents")
        print(f"Error in missing documents test: {e}")

    try:
        test_empty_upload()
    except Exception as e:
        logger.exception("test_error", test="empty_upload")
        print(f"Error in empty upload test: {e}")

    logger.info("unconventional_test_suite_complete")
    print("\n" + "=" * 60)
    print("Unconventional Flow Tests Complete")
    print("=" * 60)
