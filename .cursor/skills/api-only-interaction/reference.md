# API Reference

Base URL: `http://localhost:8000/api/v1`

## Auth

### POST /auth/login
```json
// Request
{"emirates_id": "784-1990-1234567-1"}

// Response 200
{
  "applicant_id": "uuid",
  "application_id": "uuid",
  "is_new_applicant": true,
  "current_phase": "authentication",
  "state_snapshot": null
}
```

## Applications

### GET /applications/{id}
Returns: `id`, `applicant_id`, `status`, `current_phase`, `eligibility_score`, `validation_confidence`, `decision`, `decision_explanation`, `created_at`, `updated_at`

### POST /applications/{id}/chat
Multipart form-data: `text` (string), `files` (list of files)
Returns: `message`, `phase`, `uploaded_documents`, `decision`, `decision_card`, `interrupt`

### GET /applications/{id}/documents
Returns: list of documents with `document_type`, `processing_status`, `uploaded_at`

### POST /applications/{id}/documents
Multipart form-data: `file` (single file), `document_type` (optional string)

### DELETE /applications/{id}/documents/{doc_id}

## Eligibility

### GET /eligibility/{id}
Returns: `eligibility_score`, `factors`

### POST /eligibility/{id}/compute
Returns: `eligibility_score`, `factors`, `features_used`

### GET /eligibility/{id}/explanation
Returns: `explanation` (string), `eligibility_score`

## Health

### GET /health/langgraph
Returns: `status` (healthy/degraded/unhealthy), `components`, `timestamp`

### GET /health/llm
Returns: `status`, `provider`, `model`, `latency_ms`, `tokens`

## Error Responses

| Status | Condition | Response |
|---|---|---|
| 400 | Invalid Emirates ID | `{"detail": "Invalid Emirates ID format or checksum"}` |
| 404 | Application not found | `{"detail": "Application not found"}` |
| 404 | Eligibility not computed | `{"detail": "Eligibility not computed for this application"}` |
