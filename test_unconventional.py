"""Test unconventional flows - invalid documents, missing docs, edge cases."""
import requests
from pathlib import Path
import json

def test_invalid_document_type():
    """Test uploading unsupported file types."""
    print("\n=== Test: Invalid Document Type ===")
    
    # Create a new applicant
    auth_response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'emirates_id': '784-1990-1234567-6'}
    )
    app_id = auth_response.json()['application_id']
    
    # Intake
    requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'}
    )
    
    # Try uploading invalid file types
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
    
    data = response.json()
    print(f'Status: {response.status_code}')
    print(f'Phase: {data.get("phase")}')
    print(f'Message: {data.get("message", "")[:200]}')
    print(f'Documents: {len(data.get("uploaded_documents", []))}')
    
    return app_id

def test_missing_documents():
    """Test proceeding with incomplete document set."""
    print("\n=== Test: Missing Required Documents ===")
    
    # Create a new applicant
    auth_response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'emirates_id': '784-1985-9876543-2'}
    )
    app_id = auth_response.json()['application_id']
    
    # Intake
    requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'}
    )
    
    # Upload only some documents (missing credit_report and application_form)
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
    
    data = response.json()
    print(f'Status: {response.status_code}')
    print(f'Phase: {data.get("phase")}')
    print(f'Message: {data.get("message", "")[:200]}')
    print(f'Documents: {len(data.get("uploaded_documents", []))}')
    
    for _, f in partial_files:
        f.close()
    
    return app_id

def test_empty_upload():
    """Test chat without any document upload."""
    print("\n=== Test: Empty Upload (Chat Only) ===")
    
    # Create a new applicant
    auth_response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'emirates_id': '784-1980-5555555-5'}
    )
    app_id = auth_response.json()['application_id']
    
    # Intake
    requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I am divorced with 2 children. I work as admin assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'}
    )
    
    # Send message without documents
    response = requests.post(
        f'http://localhost:8000/api/v1/applications/{app_id}/chat',
        data={'text': 'I need more time to gather my documents'}
    )
    
    data = response.json()
    print(f'Status: {response.status_code}')
    print(f'Phase: {data.get("phase")}')
    print(f'Message: {data.get("message", "")[:200]}')
    print(f'Has interrupt: {data.get("interrupt") is not None}')
    
    return app_id

if __name__ == '__main__':
    print("=" * 60)
    print("Unconventional Flow Tests")
    print("=" * 60)
    
    try:
        test_invalid_document_type()
    except Exception as e:
        print(f"Error in invalid document test: {e}")
    
    try:
        test_missing_documents()
    except Exception as e:
        print(f"Error in missing documents test: {e}")
    
    try:
        test_empty_upload()
    except Exception as e:
        print(f"Error in empty upload test: {e}")
    
    print("\n" + "=" * 60)
    print("Unconventional Flow Tests Complete")
    print("=" * 60)
