import re
import json

explanation = """

Based on my analysis of the application, here is the final decision:

```json
{
  "decision": "soft_decline",
  "explanation": "Application has been soft declined.",
  "formatted_card": {
    "explanation": "Your application has been soft declined due to incomplete validation."
  }
}
```
"""

json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', explanation)
if json_match:
    json_str = json_match.group(1)
    print('JSON extracted:', json_str[:100])
    try:
        parsed = json.loads(json_str)
        print('Parsed successfully')
        if 'formatted_card' in parsed:
            print('Found formatted_card')
            print('Explanation:', parsed['formatted_card'].get('explanation'))
    except Exception as e:
        print('Parse error:', e)
else:
    print('No match found')
