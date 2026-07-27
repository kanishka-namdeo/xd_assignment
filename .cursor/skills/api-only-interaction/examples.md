# Examples

## Happy Path (Approved Profile)

```powershell
# 1. Generate account
.\.venv\Scripts\python.exe scripts/api_client.py generate-account --seed 42

# 2. Run full flow
.\.venv\Scripts\python.exe scripts/api_client.py full-flow `
  --emirates-id 784-1990-1234567-1 `
  --profile-dir data/fresh_accounts/applicant_42 `
  --verbose
```

Expected: decision=`approved`, score > 0.7.

## Step-by-Step (Manual Control)

```powershell
# Auth
$auth = .\.venv\Scripts\python.exe scripts/api_client.py login --emirates-id <eid> | ConvertFrom-Json
$app_id = $auth.data.application_id

# Intake
.\.venv\Scripts\python.exe scripts/api_client.py intake --app-id $app_id --profile-dir <path>

# Upload
.\.venv\Scripts\python.exe scripts/api_client.py upload-docs --app-id $app_id --profile-dir <path>

# Process
.\.venv\Scripts\python.exe scripts/api_client.py process --app-id $app_id

# Review (if needed)
.\.venv\Scripts\python.exe scripts/api_client.py review --app-id $app_id

# Decision
.\.venv\Scripts\python.exe scripts/api_client.py decision --app-id $app_id

# Enablement
.\.venv\Scripts\python.exe scripts/api_client.py enablement --app-id $app_id
```

## Session Recovery

```powershell
# First session: auth + intake + partial docs
# ... then stop

# Later: re-auth with same Emirates ID
$auth = .\.venv\Scripts\python.exe scripts/api_client.py login --emirates-id <eid> | ConvertFrom-Json
# is_new_applicant = false, same application_id
# Continue from saved phase
```

## Eligibility Check

```powershell
.\.venv\Scripts\python.exe scripts/api_client.py eligibility --app-id <app_id>
```

## Status Check

```powershell
.\.venv\Scripts\python.exe scripts/api_client.py status --app-id <app_id>
```
