import re
import json

explanation = """Based on my analysis of the application, here is the final decision:

```json
{
  "decision": "soft_decline",
  "explanation": "Application dd1b9976-8bb7-4682-9f10-6f69961178e2 has been soft declined.",
  "formatted_card": {
    "title": "Application Decision",
    "decision": "soft_decline",
    "explanation": "Your application has been soft declined due to incomplete validation."
  }
}
```"""

print("Testing regex pattern...")
json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', explanation)
if json_match:
    print("[OK] Regex matched!")
    json_str = json_match.group(1)
    print(f"Extracted JSON: {json_str[:100]}...")
    
    try:
        parsed = json.loads(json_str)
        print("[OK] JSON parsed successfully!")
        
        if "formatted_card" in parsed:
            print("[OK] Found formatted_card key!")
            formatted = parsed["formatted_card"]
            if "explanation" in formatted:
                print(f"[OK] Clean explanation: {formatted['explanation']}")
        else:
            print("[FAIL] No formatted_card key found")
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON decode error: {e}")
else:
    print("[FAIL] Regex did not match!")
