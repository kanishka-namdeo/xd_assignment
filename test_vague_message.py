import requests
import json

# Test vague message handling after the fix
url = "http://localhost:8000/api/v1/applications/dd1b9976-8bb7-4682-9f10-6f69961178e2/chat"
data = {
    "text": "I need help"
}

print("Sending vague message...")
response = requests.post(url, data=data)

print(f"Status Code: {response.status_code}")
print(f"\nResponse:")
print(json.dumps(response.json(), indent=2))
