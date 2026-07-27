import requests
import json
from pathlib import Path

# Load session
session = json.loads(Path('data/.test_session.json').read_text())
app_id = session['application_id']
print(f'Application ID: {app_id}')

# Upload documents
profile_dir = Path('data/fresh_accounts/applicant_20260727')
files = []
for f in profile_dir.glob('*'):
    if f.is_file() and f.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.xlsx', '.docx']:
        ext = f.suffix.lstrip('.')
        files.append(('files', (f.name, open(f, 'rb'), f'application/{ext}')))

print(f'Uploading {len(files)} files...')
r = requests.post(
    f'http://localhost:8000/api/v1/applications/{app_id}/chat',
    data={'text': 'Here are my documents for the application.'},
    files=files
)

print(f'Status: {r.status_code}')
data = r.json()
print(f'Phase: {data.get("phase")}')
print(f'Message: {data.get("message", "")[:200]}')

# Close file handles
for _, (_, fh, _) in files:
    fh.close()
