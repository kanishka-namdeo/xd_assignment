# API Design Document

**Project:** UAE Social Support Application  
**Version:** 1.0.0  
**Base Path:** `/api/v1`  

---

## 1. Design Principles

### RESTful Conventions

The API follows REST architectural constraints:

- **Resource-oriented URLs** — Nouns represent resources (`/applications`, `/documents`, `/eligibility`), not actions. Actions that cannot be modeled as CRUD use sub-resource POST endpoints (e.g., `/eligibility/{id}/compute`).
- **HTTP methods** — Standard verbs map to operations: `GET` (retrieve), `POST` (create/submit), `PATCH` (partial update), `DELETE` (remove).
- **Stateless requests** — Each request carries all information needed for processing. Session state is managed server-side via the LangGraph checkpointer; the client passes `application_id` to correlate requests.
- **HATEOAS-lite** — Responses include resource identifiers (`id`, `application_id`) that clients use to construct subsequent requests. Full HATEOAS links are not embedded; clients are expected to follow the documented workflow.

### Resource Naming

| Convention | Example |
|---|---|
| Lowercase kebab-case for path segments | `/api/v1/applications` |
| Plural nouns for collections | `/applications`, `/documents` |
| UUID path parameters | `/applications/{application_id}` |
| Sub-resource for actions | `/eligibility/{application_id}/compute` |

### Versioning Strategy

The API uses **URL path versioning** (`/api/v1`). This approach was chosen because:

- It is explicit and discoverable in browser-based API docs.
- It allows breaking changes by introducing `/api/v2` without affecting existing clients.
- It avoids header-based version negotiation complexity for a system whose primary consumers are the Streamlit frontend and internal services.

Future versions should maintain backward compatibility for at least one major version cycle. Deprecation of v1 endpoints must be announced with a 90-day notice.

---

## 2. Authentication

### Session-Based Authentication

The system uses a **passwordless, identity-based login** flow:

1. **Login** — Client submits an Emirates ID number to `POST /api/v1/auth/login`.
2. **Session creation** — The server looks up or creates an applicant record and returns:
   - `applicant_id` (UUID) — the person's identity record
   - `application_id` (UUID) — the current application session
   - `is_new_applicant` (bool) — whether this is a first-time user
   - `current_phase` (str) — the LangGraph workflow phase to resume
   - `state_snapshot` (dict | None) — serialized graph state for UI restoration
   - `identity_number`, `applicant_info` — profile data for personalization

3. **Subsequent requests** — The client includes `application_id` as a path parameter on all chat, document, and eligibility endpoints. No bearer token is exchanged; the UUID itself serves as the session handle.

### Security Considerations

- Emirates ID numbers are 15-digit identifiers. The service validates format and Luhn checksum before lookup.
- There is no token rotation or refresh mechanism. The `application_id` UUID (v4/v7) provides sufficient entropy against enumeration.
- For production deployment, consider adding:
  - HMAC-signed request tokens derived from the `application_id`
  - IP-based rate limiting on the login endpoint
  - CORS configuration restricting origins to the Streamlit frontend domain

### Request Flow

```
Client → POST /api/v1/auth/login { emirates_id: "784-1234-5678901-2" }
       ← { applicant_id, application_id, is_new_applicant, current_phase, ... }

Client → POST /api/v1/applications/{application_id}/chat { text, files }
       ← { message, phase, decision, interrupt, ... }
```

---

## 3. Endpoint Catalog

### Auth

| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Authenticate with Emirates ID | `200` |

**Request body** — `AuthLoginRequest`

```json
{
  "emirates_id": "784-1234-5678901-2"
}
```

**Response** — `AuthLoginResponse`

```json
{
  "applicant_id": "a1b2c3d4-...",
  "application_id": "e5f6g7h8-...",
  "is_new_applicant": true,
  "current_phase": "authentication",
  "state_snapshot": null,
  "identity_number": "784-1234-5678901-2",
  "applicant_info": null
}
```

---

### Applications

| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/applications` | Create a new application | `201` |
| `GET` | `/api/v1/applications/{application_id}` | Get application status | `200` |
| `PATCH` | `/api/v1/applications/{application_id}/status` | Update status and phase | `200` |
| `GET` | `/api/v1/applications/{application_id}/documents` | List uploaded documents | `200` |
| `POST` | `/api/v1/applications/{application_id}/documents` | Upload a document | `201` |
| `DELETE` | `/api/v1/applications/{application_id}/documents/{document_id}` | Delete a document | `200` |

**Create request** — `ApplicationCreateRequest`

```json
{
  "applicant_id": "a1b2c3d4-...",
  "support_category": "housing"
}
```

**Application response** — `ApplicationResponse`

```json
{
  "id": "e5f6g7h8-...",
  "applicant_id": "a1b2c3d4-...",
  "status": "in_progress",
  "current_phase": "document_collection",
  "eligibility_score": 0.72,
  "validation_confidence": 0.85,
  "decision": "approved",
  "decision_explanation": "Strong credit history and stable income.",
  "created_at": "2026-07-27T10:00:00Z",
  "updated_at": "2026-07-27T10:05:00Z"
}
```

**Document upload** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | yes | Document file (PDF, PNG, JPG, DOCX, XLSX) |
| `document_type` | string | no | Document type hint (auto-detected if omitted) |

**Document response** — `DocumentResponse`

```json
{
  "id": "d1e2f3g4-...",
  "applicant_id": "a1b2c3d4-...",
  "document_type": "bank_statement",
  "processing_status": "pending",
  "file_format": "pdf",
  "file_size_bytes": 245678,
  "file_hash": "sha256:abc123...",
  "extraction_status": null,
  "validation_status": null,
  "overall_confidence": null,
  "uploaded_at": "2026-07-27T10:00:00Z",
  "created_at": "2026-07-27T10:00:00Z"
}
```

---

### Chat

| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/applications/{application_id}/chat` | Send a message to the orchestrator | `200` |
| `POST` | `/api/v1/applications/{application_id}/chat/stream` | Stream orchestrator events as SSE | `200` |

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | User message text |
| `files` | file[] | no | Optional document attachments |

**Response** — `ChatResponse`

```json
{
  "message": "Please upload your Emirates ID to continue.",
  "phase": "intake",
  "uploaded_documents": [
    { "doc_type": "emirates_id", "file_path": "/data/...", "status": "uploaded" }
  ],
  "decision": null,
  "decision_card": null,
  "interrupt": {
    "question": "What is your monthly income?",
    "phase": "intake",
    "missing_fields": ["monthly_income"],
    "missing_documents": null,
    "discrepancies": null,
    "recommendations": null
  },
  "enablement_recommendations": null,
  "discrepancies": null,
  "validation_confidence": null
}
```

**Streaming response** — Server-Sent Events (`text/event-stream`)

Each event is a JSON object prefixed with `data: ` and terminated by `\n\n`. The stream ends with `data: [DONE]\n\n`.

```
data: {"type": "phase_transition", "from": "intake", "to": "document_collection"}

data: {"type": "extraction_complete", "document_type": "bank_statement"}

data: {"type": "decision_reached", "decision": "approved"}

data: [DONE]
```

---

### Documents

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/api/v1/documents/status` | Get document upload status for an application | `200` |

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `application_id` | string | yes | Application UUID |

**Response**

```json
{
  "application_id": "e5f6g7h8-...",
  "documents": [
    {
      "document_type": "bank_statement",
      "status": "processed",
      "confidence": 0.92,
      "uploaded_at": "2026-07-27T10:00:00Z"
    }
  ]
}
```

---

### Eligibility

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/api/v1/eligibility/{application_id}` | Get computed eligibility score | `200` |
| `POST` | `/api/v1/eligibility/{application_id}/compute` | Trigger eligibility computation | `200` |
| `GET` | `/api/v1/eligibility/{application_id}/explanation` | Get human-readable explanation | `200` |

**Eligibility response** — `EligibilityResponse`

```json
{
  "application_id": "e5f6g7h8-...",
  "eligibility_score": 0.72,
  "factors": {
    "income_factor": 0.8,
    "credit_factor": 0.9,
    "employment_factor": 0.5
  }
}
```

**Compute response** — `EligibilityComputeResponse`

```json
{
  "application_id": "e5f6g7h8-...",
  "eligibility_score": 0.72,
  "factors": { "income_factor": 0.8, "credit_factor": 0.9 },
  "features_used": ["monthly_salary", "credit_score", "employment_status"]
}
```

**Explanation response** — `EligibilityExplanationResponse`

```json
{
  "application_id": "e5f6g7h8-...",
  "explanation": "The applicant qualifies based on stable employment and good credit history.",
  "eligibility_score": 0.72
}
```

---

### Health

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/api/v1/health/langgraph` | Infrastructure health check | `200` |
| `GET` | `/api/v1/health/llm` | LLM connectivity check | `200` |

**LangGraph health response**

```json
{
  "status": "healthy",
  "components": {
    "postgres": { "status": "healthy" }
  },
  "timestamp": "2026-07-27T10:00:00Z"
}
```

**LLM health response**

```json
{
  "status": "healthy",
  "provider": "streamlake",
  "model": "gpt-4o",
  "latency_ms": 342.5,
  "tokens": 12
}
```

---

## 4. Error Handling

### Error Response Format

All errors use the FastAPI/Starlette standard format with a `detail` field:

```json
{
  "detail": "Application not found"
}
```

For validation errors (Pydantic), FastAPI returns a structured array:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "emirates_id"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### Status Code Usage

| Code | Meaning | When Used |
|---|---|---|
| `200 OK` | Success | GET, PATCH, and POST (chat, compute) operations |
| `201 Created` | Resource created | POST applications, POST documents |
| `400 Bad Request` | Client error | Invalid Emirates ID, malformed request body |
| `404 Not Found` | Resource missing | Unknown application_id, document_id, or eligibility record |
| `422 Unprocessable Entity` | Validation error | Pydantic schema violations |
| `500 Internal Server Error` | Server error | Unhandled exceptions, LLM failures |

### Error Logging

All errors are logged via `structlog` with the following context:

- `request_id` — correlation ID from the `x-correlation-id` header (auto-generated if absent)
- `application_id` — when available
- `duration_ms` — request processing time
- `error` — error message
- Full stack trace via `logger.exception()` in except blocks

The `RequestLoggingMiddleware` automatically attaches `x-correlation-id` to every response header, enabling end-to-end trace correlation across services.

### Client Guidance

- **400 errors** — Check request body schema. The `detail` field contains a human-readable message.
- **404 errors** — The referenced resource does not exist. Verify the UUID.
- **422 errors** — Inspect the `detail` array for field-level validation failures.
- **500 errors** — Retry with exponential backoff. If persistent, check the `x-correlation-id` against application logs.

---

## 5. Rate Limiting

### Current State

No rate limiting middleware is currently deployed. The API relies on the underlying infrastructure (reverse proxy, container orchestration) for basic traffic management.

### Recommended Strategy

When rate limiting is introduced, the following approach is recommended:

| Endpoint Category | Limit | Rationale |
|---|---|---|
| `POST /auth/login` | 10 requests/min per IP | Prevents Emirates ID enumeration |
| `POST /chat` | 30 requests/min per application_id | LLM calls are expensive; limits abuse |
| `POST /chat/stream` | 10 concurrent streams per application_id | Prevents graph spawning storms |
| `POST /documents/upload` | 5 requests/min per application_id | Document processing is CPU-intensive |
| All other endpoints | 60 requests/min per IP | Standard API protection |

### Implementation Notes

- Use a sliding-window counter stored in Redis for distributed rate limiting.
- Return `429 Too Many Requests` with `Retry-After` header when limits are exceeded.
- Include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers on all responses.
- Whitelist internal service-to-service communication (e.g., from the Streamlit frontend running on the same host).

---

## 6. Idempotency

### Current State

No explicit idempotency key mechanism is implemented. The following implicit behaviors exist:

- **Login** — Repeated logins with the same Emirates ID return the existing application (idempotent by identity lookup).
- **Document upload** — Each upload creates a new document record. Duplicate uploads of the same file are not deduplicated.
- **Eligibility compute** — Re-computing overwrites the previous result. The operation is idempotent for the same input data.

### Recommended Idempotency Strategy

For production, critical write operations should support an `Idempotency-Key` header:

| Endpoint | Idempotency Scope |
|---|---|
| `POST /applications` | Key scoped to `applicant_id` — prevents duplicate applications |
| `POST /applications/{id}/documents` | Key scoped to `application_id + file_hash` — deduplicates identical uploads |
| `POST /eligibility/{id}/compute` | Key scoped to `application_id` — prevents redundant computation |

**Response for duplicate key:**

```json
{
  "idempotency_key": "abc123",
  "status": "duplicate",
  "original_request_id": "req_789"
}
```

The server should store idempotency keys with a TTL of 24 hours in a fast key-value store (Redis).

---

## 7. Webhook Callbacks

### Current State

The API does not implement webhook callbacks. Instead, it provides **Server-Sent Events (SSE)** streaming via `POST /api/v1/applications/{application_id}/chat/stream` for real-time client updates during long-running agent operations.

### SSE Event Types

| Event Type | Description |
|---|---|
| `phase_transition` | Orchestrator moved from one workflow phase to another |
| `extraction_complete` | A document was successfully extracted |
| `validation_complete` | Validation agent finished processing |
| `eligibility_scored` | Eligibility score was computed |
| `decision_reached` | Final decision was made |
| `interrupt` | Graph paused for user input |
| `error` | An error occurred during processing |
| `[DONE]` | Stream completed |

### Future Webhook Design

For server-to-server integrations (e.g., notifying external case-management systems), a webhook system should be added:

1. **Registration** — `POST /api/v1/webhooks` with `url`, `events[]`, and `secret` fields.
2. **Payload** — Signed with HMAC-SHA256 using the registered secret. Delivered via `X-Webhook-Signature` header.
3. **Retry** — Exponential backoff with 3 retries. Dead-letter queue for permanent failures.
4. **Events** — `application.decision_reached`, `application.status_changed`, `document.processed`.

---

## 8. Pagination & Filtering

### Current State

No pagination is implemented on any endpoint. The `GET /applications/{id}/documents` endpoint returns all documents for an applicant in a single response. Given the domain constraint (maximum ~6 document types per applicant), this is acceptable for current scale.

### Recommended Pagination Strategy

When list endpoints grow (e.g., audit logs, chat history, admin application listings), implement **cursor-based pagination**:

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `cursor` | string | Opaque cursor from previous response's `next_cursor` |
| `limit` | int | Max items per page (default 20, max 100) |
| `sort` | string | Sort field (e.g., `created_at`, `updated_at`) |
| `order` | string | `asc` or `desc` (default `desc`) |

**Response envelope:**

```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wNy0yNyJ9",
    "has_more": true
  }
}
```

Cursor-based pagination is preferred over offset-based because:
- It is stable under concurrent inserts/deletes.
- It performs well on large datasets (no `OFFSET N` scans).
- Cursors can encode sort keys, avoiding ambiguous ordering.

### Filtering

For future admin/list endpoints, support filter parameters:

| Filter | Type | Example |
|---|---|---|
| `status` | enum | `?status=in_progress,pending_review` |
| `current_phase` | enum | `?current_phase=decision` |
| `decision` | enum | `?decision=approved,manual_review` |
| `from` / `to` | ISO 8601 date | `?from=2026-07-01&to=2026-07-31` |
| `eligibility_score_min` | float | `?eligibility_score_min=0.7` |

---

## 9. OpenAPI Documentation

### Accessing the Docs

FastAPI auto-generates interactive API documentation:

| Endpoint | Description |
|---|---|
| `GET /docs` | Swagger UI — interactive request/response testing |
| `GET /redoc` | ReDoc — clean, readable documentation |
| `GET /openapi.json` | Raw OpenAPI 3.0 schema (JSON) |

### Using Swagger UI

1. Start the application: `uvicorn src.main:app --reload --port 8000`
2. Navigate to `http://localhost:8000/docs`
3. Authorize by providing an `application_id` (for endpoints that require it)
4. Click any endpoint to expand its schema
5. Use "Try it out" to execute requests directly from the browser

### Schema Highlights

- All request/response bodies are defined as Pydantic models in `src/domain/schemas/`.
- Path parameters use `UUID` type — Swagger UI validates format before sending.
- File upload endpoints show a file picker in the Swagger UI.
- The streaming endpoint (`/chat/stream`) returns `text/event-stream` media type.

### Extending Documentation

Pydantic model docstrings and `Field(description=...)` annotations automatically populate the OpenAPI schema. To add descriptions to endpoints, use the `summary` and `description` parameters of the `@router` decorator.

Example:

```python
@router.post("/login", summary="Authenticate with Emirates ID", description="Creates or resumes an application session for the given Emirates ID number.")
```

---

## Appendix: Quick Reference

### Base URL

```
http://localhost:8000/api/v1
```

### Common Headers

| Header | Value | Required |
|---|---|---|
| `Content-Type` | `application/json` | For JSON body requests |
| `Content-Type` | `multipart/form-data` | For file uploads and chat |
| `Accept` | `application/json` | Recommended |
| `x-correlation-id` | UUID | Optional — auto-generated if absent |

### Workflow Summary

```
1. POST /auth/login → get application_id
2. POST /applications/{id}/chat → interact with orchestrator
3. POST /applications/{id}/documents → upload supporting documents
4. GET /applications/{id} → check status
5. GET /eligibility/{id} → view eligibility score
6. GET /eligibility/{id}/explanation → understand decision factors
```
