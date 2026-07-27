# Security & Privacy Practices

> This document describes the security and privacy posture of the UAE Social Support Application. It is intended for security reviewers, auditors, and operations staff.

---

## 1. Data Classification

The application processes the following categories of citizen data for social support eligibility assessment:

| Category | Examples | Sensitivity |
|----------|----------|-------------|
| **National ID** | Emirates ID number (15 digits, Luhn-validated) | Critical |
| **Personal Identity** | Full name (Arabic/English), mother name, sponsor name | High |
| **Contact Information** | Email, phone number | High |
| **Financial Data** | Bank statements, IBAN, monthly salary, assets and liabilities | Critical |
| **Credit History** | AECB-format credit reports | High |
| **Family Relationships** | Marital status, dependents, family linkage (Neo4j graph) | High |
| **Employment** | Employer name, self-employment status | Medium |
| **Application Artifacts** | Uploaded documents (PDF, PNG, DOCX, XLSX), extracted text, agent reasoning traces | High |

**Data stores:**

- **PostgreSQL** — applicant records, application state, extracted structured data, audit logs (16 tables)
- **Neo4j** — family relationship graphs and document lineage
- **Qdrant** — document embeddings for semantic search (768-dimensional vectors)
- **Langfuse** — LLM observability traces (optional, self-hosted)

---

## 2. PII Handling

### 2.1 Logging Redaction

All application logs pass through a central PII redaction processor (`src/infrastructure/observability/logging.py`). The processor operates at two levels:

**Key-based redaction** — the following keys are always masked before log output:

```
identity_number, full_name, full_name_en, full_name_ar,
email, phone, contact_phone, contact_email,
account_number, iban, password, token, secret_key, api_key,
mother_name, sponsor_name
```

**Pattern-based redaction** — regex patterns catch PII in free-text fields:

- 15-digit numbers (Emirates ID pattern)
- Email addresses
- IBAN numbers (AE-prefixed)

Matched values are replaced with `[REDACTED]`.

**Rationale:** See [ADR 0005 — Structured Logging with PII Redaction](adr/0005-structured-logging-pii.md).

### 2.2 Authentication

The application uses Emirates ID number as the sole authentication factor. The Emirates ID is validated using:

1. **Format check** — regex pattern `^(784|866|978)-\d{4}-\d{6,7}-\d$`
2. **Luhn checksum validation** — ensures the ID is mathematically valid

No passwords, tokens, or session cookies are issued. Each request is stateless; the applicant's Emirates ID is submitted per interaction.

### 2.3 Storage

PII is stored in PostgreSQL with the following mitigations:

- Database ports are bound to `127.0.0.1` only (not exposed to external networks)
- Docker containers run with `no-new-privileges:true` security option
- Secrets are loaded from `.env` (gitignored) — never committed to version control
- Pydantic `SecretStr` is used for API keys and database passwords in configuration

**Note:** Application-level encryption at rest (e.g., column-level encryption for Emirates ID) is not currently implemented. This should be addressed before production deployment in a government environment.

---

## 3. Data Retention

### 3.1 Checkpoint TTL

LangGraph state checkpoints (which contain application state snapshots) are automatically cleaned up by a background task:

- **Retention period:** 30 days (`CHECKPOINT_TTL_DAYS`)
- **Cleanup interval:** Every 60 minutes
- Managed by `CheckpointerManager` in `src/agents/checkpointer.py`

### 3.2 Audit Logs

Document audit logs (`document_audit_log` table) are retained indefinitely to support compliance investigations. The audit log uses hash chaining (SHA-256) to detect tampering.

### 3.3 Applicant Data

There is currently no automated deletion policy for applicant records. Applicants persist in PostgreSQL until manually removed. A data retention and right-to-erasure policy should be defined before production deployment to comply with UAE data protection regulations.

### 3.4 Langfuse Traces

Langfuse observability data is self-hosted and governed by its own retention settings. Telemetry to Langfuse's cloud is disabled (`LANGFUSE_TELEMETRY_ENABLED=false`).

---

## 4. Access Control

### 4.1 API Access

- All API endpoints are under `/api/v1/` and are currently unauthenticated beyond Emirates ID validation
- No role-based access control (RBAC) is implemented
- No rate limiting or throttling is configured

### 4.2 Infrastructure Access

- PostgreSQL: `127.0.0.1:5432` (localhost only)
- Neo4j: `127.0.0.1:7474` (browser), `127.0.0.1:7687` (Bolt)
- Qdrant: `127.0.0.1:6333` (REST), `127.0.0.1:6334` (gRPC)
- Langfuse: `127.0.0.1:4000` (web UI)

All infrastructure ports are bound to localhost. External access requires explicit reverse proxy configuration.

### 4.3 Container Security

All Docker Compose services include:

- `security_opt: no-new-privileges:true` — prevents privilege escalation
- Resource limits (memory and CPU) to prevent denial-of-service
- Health checks for automatic recovery
- JSON log drivers with rotation (max 10 MB per file, 3 files)

---

## 5. Encryption

### 5.1 In-Transit

- **Internal (development):** Services communicate over a Docker bridge network (`xd_backend`) without TLS. This is acceptable for local development where all containers run on the same host.
- **Production requirement:** TLS must be terminated at a reverse proxy (e.g., nginx, Traefik) for all external-facing endpoints. Inter-service communication should use mutual TLS or service mesh encryption.

### 5.2 At-Rest

| Data Store | Encryption Status |
|------------|-------------------|
| PostgreSQL | Relies on volume-level encryption; TDE not configured |
| Neo4j | Relies on volume-level encryption; native encryption not configured |
| Qdrant | Relies on volume-level encryption |
| Langfuse | Uses `ENCRYPTION_KEY` for sensitive metadata; S3 data via MinIO |
| MinIO | S3-compatible; server-side encryption available |

**Recommendation:** Enable PostgreSQL TDE or use encrypted volumes (e.g., LUKS, AWS EBS encryption) before production deployment.

### 5.3 Secrets Management

- Secrets are loaded from environment variables via `.env` file
- Pydantic `SecretStr` prevents accidental logging of sensitive values
- No integration with external secrets managers (HashiCorp Vault, AWS Secrets Manager) is currently configured

---

## 6. Audit Trail

### 6.1 Document Audit Log

Every document action is recorded in the `document_audit_log` table with:

- `action` — what operation was performed
- `performed_by` — identity of the actor (user, system, or agent)
- `performed_by_type` — constrained to `user`, `system`, or `agent`
- `timestamp` — UTC timestamp
- `changes`, `previous_values`, `new_values` — JSONB diff of what changed
- `ip_address` — source IP (INET type)
- `user_agent` — client user agent string
- `session_id` — correlation to application session

### 6.2 Hash Chain Integrity

Each audit log entry includes a SHA-256 hash computed over:

```
{
  "id": <uuid>,
  "document_id": <uuid>,
  "action": <string>,
  "performed_by": <string>,
  "timestamp": <iso8601>,
  "changes": <json>,
  "previous_hash": <hex_digest>
}
```

The `previous_hash` links to the prior entry's hash, forming an immutable chain. The `AuditLogRepository.verify_chain()` method can detect any tampering by recomputing and comparing hashes.

### 6.3 Request Logging

All HTTP requests pass through `RequestLoggingMiddleware`, which logs:

- Request ID (correlation ID, propagated via `x-correlation-id` header)
- HTTP method and path
- Query parameters
- Response status code
- Duration in milliseconds

PII is redacted before logging per Section 2.1.

### 6.4 LLM Observability

When Langfuse is enabled, all LLM calls are traced with:

- Trace name and session ID
- Input/output tokens
- Model and provider metadata
- Latency and error information

Langfuse traces may contain PII in LLM inputs/outputs. Ensure Langfuse is self-hosted and access-controlled.

---

## 7. Third-Party Risk

### 7.1 LLM Provider Strategy

The application supports two LLM providers, controlled by the `LLM_PROVIDER` environment variable:

| Provider | Type | PII Egress | Default |
|----------|------|------------|---------|
| **Ollama** | Local (on-premises) | None — runs on host | Development |
| **StreamLake** | Cloud (Azure OpenAI-compatible) | PII sent to cloud API | Production (when GPU unavailable) |

**Rationale:** See [ADR 0004 — Local LLM via Ollama with Cloud Fallback](adr/0004-local-llm-fallback.md).

### 7.2 Embeddings

Embeddings always run locally via Ollama (`nomic-embed-text:v1.5`) regardless of LLM provider. No document content is sent to external services for embedding generation.

### 7.3 Langfuse

Langfuse is self-hosted via Docker Compose. No data is sent to Langfuse's cloud service. Telemetry is explicitly disabled.

### 7.4 No Other Third-Party Services

The application does not integrate with:
- External analytics platforms (Google Analytics, etc.)
- Cloud storage providers (AWS S3, Azure Blob) — MinIO provides S3-compatible local storage
- External identity providers or SSO
- Payment processors

---

## 8. Incident Response

### 8.1 Current Capabilities

The application provides the following incident response primitives:

- **Hash chain verification** — `AuditLogRepository.verify_chain()` can detect tampered audit logs
- **Health check endpoint** — `/api/v1/health/langgraph` reports component health status
- **Structured error logging** — all exceptions are logged with full traceback via `logger.exception()`
- **Request correlation** — every request has a unique ID for traceability

### 8.2 Recommended Procedures

Before production deployment, the following procedures should be established:

1. **Breach notification** — Define notification timelines per UAE data protection law (typically 72 hours for regulatory bodies)
2. **Data subject access requests** — Implement mechanisms to export and delete applicant data on request
3. **Log retention policy** — Define how long audit logs and application logs are retained
4. **Key rotation** — Establish a schedule for rotating database passwords, API keys, and encryption keys
5. **Penetration testing** — Conduct regular security assessments, particularly on the authentication flow
6. **Vulnerability scanning** — Scan Docker images and Python dependencies (e.g., `pip-audit`, `trivy`)

### 8.3 Contact

For security issues related to this application, contact the development team. No dedicated security contact is currently designated.

---

## Appendix A — Security Checklist

| Control | Status | Notes |
|---------|--------|-------|
| PII redaction in logs | Implemented | `src/infrastructure/observability/logging.py` |
| Emirates ID validation | Implemented | Luhn checksum + format check |
| Audit trail with hash chaining | Implemented | `src/infrastructure/db/models/audit.py` |
| Localhost-only database ports | Implemented | Docker Compose configuration |
| Secrets in environment (not code) | Implemented | `.env` file, gitignored |
| Container security options | Implemented | `no-new-privileges:true` |
| Local LLM (no PII egress) | Implemented | Ollama default |
| Checkpoint TTL cleanup | Implemented | 30-day retention |
| Database encryption at rest | Not implemented | Rely on volume-level encryption |
| TLS for inter-service communication | Not implemented | Required for production |
| Rate limiting | Not implemented | Required for production |
| Role-based access control | Not implemented | Required for production |
| Automated data deletion | Not implemented | Required for compliance |
| External secrets manager | Not implemented | Recommended for production |
| Dedicated security contact | Not designated | Required for production |
