import requests
import json

url = "http://localhost:8000/api/v1/applications/dd1b9976-8bb7-4682-9f10-6f69961178e2/chat"

# Send as form data, not JSON
data = {"text": "I have uploaded all my documents. Please process my application."}

response = requests.post(url, data=data)
result = response.json()

print("Decision card:")
print(json.dumps(result.get("decision_card"), indent=2, ensure_ascii=False))
