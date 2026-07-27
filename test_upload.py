"""Test document upload with resume fix."""
import time

import requests
import structlog
from pathlib import Path
from src.infrastructure.observability.logging import configure_logging

configure_logging()

logger = structlog.get_logger(__name__)

app_id = '3d70382a-249f-4389-a16c-93c541de7049'
doc_dir = 'data/test_applicants/divorced_employed_good_credit'

files = [
    ('emirates_id_front.png', open(f'{doc_dir}/emirates_id_front.png', 'rb')),
    ('emirates_id_back.png', open(f'{doc_dir}/emirates_id_back.png', 'rb')),
    ('bank_statement.pdf', open(f'{doc_dir}/bank_statement.pdf', 'rb')),
    ('credit_report.pdf', open(f'{doc_dir}/credit_report.pdf', 'rb')),
    ('application_form.png', open(f'{doc_dir}/application_form.png', 'rb')),
]

print('=== Document Upload Test ===')
start = time.time()
response = requests.post(
    f'http://localhost:8000/api/v1/applications/{app_id}/chat',
    data={'text': 'Here are all my documents for the application.'},
    files=[('files', (name, f, 'application/octet-stream')) for name, f in files]
)
duration_ms = (time.time() - start) * 1000

logger.info("document_upload", application_id=app_id, status_code=response.status_code, duration_ms=round(duration_ms, 2), document_count=len(files))

print('Status:', response.status_code)
data = response.json()
print('Phase:', data.get('phase'))
print('Message:', data.get('message', '')[:300])
print('Documents uploaded:', len(data.get('uploaded_documents', [])))
if data.get('uploaded_documents'):
    for doc in data['uploaded_documents']:
        doc_type = doc.get('doc_type', 'unknown')
        status = doc.get('status', 'unknown')
        print(f'  - {doc_type}: {status}')

for _, f in files:
    f.close()
