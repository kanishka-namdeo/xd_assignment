import requests

app_id = '62dd82ca-2eb8-459c-8f05-fa90fe29f3c2'
base = f'http://localhost:8000/api/v1/applications/{app_id}/chat'

# Upload all 4 documents at once
files = [
    ('files', ('emirates_id_front.png', open('data/test_applicants/divorced_employed_good_credit/emirates_id_front.png', 'rb'), 'image/png')),
    ('files', ('bank_statement.pdf', open('data/test_applicants/divorced_employed_good_credit/bank_statement.pdf', 'rb'), 'application/pdf')),
    ('files', ('credit_report.pdf', open('data/test_applicants/divorced_employed_good_credit/credit_report.pdf', 'rb'), 'application/pdf')),
    ('files', ('application_form.png', open('data/test_applicants/divorced_employed_good_credit/application_form.png', 'rb'), 'image/png')),
]
data = {'text': 'Here are all my documents'}
r = requests.post(base, files=files, data=data, timeout=120)
print(f'Status: {r.status_code}')
resp = r.json()
print(f'Phase: {resp.get("phase")}')
print(f'Message: {resp.get("message")}')
for doc in resp.get('uploaded_documents', []):
    print(f'  {doc["doc_type"]}: {doc["file_path"]} ({doc["status"]})')
if resp.get('interrupt'):
    print(f'Interrupt: {resp["interrupt"]}')
