import time

import requests
import structlog
from src.infrastructure.observability.logging import configure_logging

configure_logging()

logger = structlog.get_logger(__name__)

app_id = '62dd82ca-2eb8-459c-8f05-fa90fe29f3c2'
base = f'http://localhost:8000/api/v1/applications/{app_id}/chat'

logger.info("test_start", script="test_upload_all", application_id=app_id)

# Upload all 4 documents at once
files = [
    ('files', ('emirates_id_front.png', open('data/test_applicants/divorced_employed_good_credit/emirates_id_front.png', 'rb'), 'image/png')),
    ('files', ('bank_statement.pdf', open('data/test_applicants/divorced_employed_good_credit/bank_statement.pdf', 'rb'), 'application/pdf')),
    ('files', ('credit_report.pdf', open('data/test_applicants/divorced_employed_good_credit/credit_report.pdf', 'rb'), 'application/pdf')),
    ('files', ('application_form.png', open('data/test_applicants/divorced_employed_good_credit/application_form.png', 'rb'), 'image/png')),
]
data = {'text': 'Here are all my documents'}

start = time.time()
r = requests.post(base, files=files, data=data, timeout=120)
duration_ms = (time.time() - start) * 1000

logger.info("document_upload_all", application_id=app_id, status_code=r.status_code, duration_ms=round(duration_ms, 2), phase=r.json().get("phase"))

print(f'Status: {r.status_code}')
resp = r.json()
print(f'Phase: {resp.get("phase")}')
print(f'Message: {resp.get("message")}')
for doc in resp.get('uploaded_documents', []):
    print(f'  {doc["doc_type"]}: {doc["file_path"]} ({doc["status"]})')
if resp.get('interrupt'):
    print(f'Interrupt: {resp["interrupt"]}')
logger.info("test_complete", script="test_upload_all", application_id=app_id)
