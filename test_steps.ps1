# Step 2: Intake - submit full personal details with support_category keyword
$applicationId = "b9f85883-f6ab-4400-bcbd-15f2c682f4d8"
$body = @{
    message = "I am applying for family support due to unknown_parentage. My name is Hassan Al-Muala, born on October 3, 2001. I am married with 3 family members. I am employed as an IT Specialist at Dubai Establishment with a monthly salary of 10,389.05 AED. I live in Fujairah, Ajman. My phone is +971 5705457738 and email is acne1840@duck.com."
} | ConvertTo-Json

$start = Get-Date
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/applications/$applicationId/chat" -Method POST -Body $body -ContentType 'application/json'
$end = Get-Date
$response | ConvertTo-Json -Depth 10
Write-Host ''
Write-Host "LATENCY_MS: $(($end - $start).TotalMilliseconds)"
