# ADR 0005: Structured Logging with PII Redaction

## Status

Accepted

## Context

The UAE Social Support Application processes sensitive citizen data. Logs must not contain PII values (identity numbers, names, account numbers) but must provide sufficient observability for debugging and audit purposes.

Standard `logging` module produces unstructured text that is difficult to query and may accidentally include PII.

## Decision

Use `structlog` with a custom PII redaction processor:

1. **Structured output:** JSON format in production, colored console in development
2. **PII redaction:** Custom processor automatically masks sensitive keys (identity_number, full_name, account_number, phone, email)
3. **Event-based:** Log events in snake_case (`"document_extracted"`, `"node_enter"`, `"request_complete"`)
4. **Mandatory timing:** All timed operations log `duration_ms`
5. **Named loggers:** `structlog.get_logger(__name__)` for traceability

## Alternatives Considered

### Standard Logging

Produces unstructured text, no built-in PII redaction, harder to integrate with observability platforms.

### Loguru

Good developer experience but less mature structured output and no built-in PII redaction.

### No PII Redaction

Unacceptable for government data. Would fail security review.

## Consequences

### Positive

- PII automatically redacted before writing
- JSON output integrates with Langfuse and log aggregation
- Event-based logging is queryable and analyzable

### Negative

- Requires discipline to log only IDs, counts, statuses (not PII values)
- Custom processor adds complexity to logging setup

### Risks

- New PII fields must be added to redaction list (mitigated by code review checklist)
