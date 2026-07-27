import requests
import json

# Test that documents are not duplicated after multiple requests
url = "http://localhost:8000/api/v1/applications/dd1b9976-8bb7-4682-9f10-6f69961178e2/chat"
data = {
    "text": "What happens next?"
}

print("Sending follow-up message...")
response = requests.post(url, data=data)

print(f"Status Code: {response.status_code}")
result = response.json()

# Check document count
doc_count = len(result.get("uploaded_documents", []))
print(f"\nDocument count: {doc_count}")

# Check for duplicates
file_paths = [doc["file_path"] for doc in result.get("uploaded_documents", [])]
unique_paths = set(file_paths)
print(f"Unique file paths: {len(unique_paths)}")

if doc_count == len(unique_paths):
    print("SUCCESS: No duplicates found!")
else:
    print(f"FAILED: Found {doc_count - len(unique_paths)} duplicate entries")

# Show the response message
print(f"\nResponse message: {result.get('message', '')[:200]}...")
