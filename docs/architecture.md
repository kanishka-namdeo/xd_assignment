# Architecture — UAE Social Support Application

> Living architecture document. Update when architecture, tool choices, component boundaries, or integration points change.

---

## 1. Tech Stack

| Component | Version | Purpose | Rationale |
|-----------|---------|---------|-----------|
| Python | 3.11.12 | Runtime | PEP 695 type parameters, `asyncio.TaskGroup`, `match/case` |
| FastAPI | 0.140.0 | REST API layer | Async-native, Pydantic v2 integrated, automatic OpenAPI docs |
| Streamlit | 1.60.0 | Frontend UI | Chat-only interaction with file upload; `@st.fragment` for partial reruns |
| LangGraph | 1.2.9 | Agent orchestration | Cyclic graphs (Reflexion loops), checkpointing, subgraph composition, `interrupt()` |
| PostgreSQL | 16 | Relational data store | 16-table schema, ACID compliance, JSONB for state snapshots, native LangGraph checkpoint integration |
| Neo4j | 6.2.0 | Graph database | Document lineage and family relationships; Cypher for transitive queries |
| Qdrant | 1.18.0 | Vector database | HNSW indexing for document embeddings; self-hosted deployment parity |
| Ollama | — | Local LLM inference | Llama 3.2 / Mistral / Qwen models; keeps PII local |
| StreamLake | — | Cloud LLM fallback | Azure OpenAI-compatible API when GPU unavailable |
| Pydantic | 2.13.4 | Data validation | 9 domain schema files; `field_validator`, `SecretStr`, FastAPI integration |
| SQLAlchemy | 2.0.51 | ORM | Async support via `asyncpg`, autogenerate migrations |
| Alembic | 1.18.5 | Database migrations | Autogenerate from ORM models |
| structlog | 26.1.0 | Structured logging | JSON output with PII redaction processor |
| Langfuse | 4.14.1 | Observability | Self-hosted tracing for every LLM call and agent transition |
| pandas | 2.3.3 | Data processing | Document parsing, tabular data manipulation |
| scikit-learn | 1.9.0 | ML eligibility model | Feature engineering and prediction pipeline |

**Decision references:** [ADR 0001](adr/0001-langgraph-orchestration.md) (LangGraph), [ADR 0002](adr/0002-polyglot-persistence.md) (databases), [ADR 0003](adr/0003-four-layer-architecture.md) (layering), [ADR 0004](adr/0004-local-llm-fallback.md) (LLM providers), [ADR 0005](adr/0005-structured-logging-pii.md) (logging).

---

## 2. Module Map

```
D:\test_misc\xd_assignment
├── src/                          # Application source (Layer 2–4)
│   ├── api/                      # Layer 1 — HTTP endpoints
│   │   ├── v1/                   # Versioned routes
│   │   │   ├── auth.py           # POST /api/v1/auth/login
│   │   │   ├── chat.py           # POST /api/v1/chat
│   │   │   ├── applications.py   # CRUD /api/v1/applications
│   │   │   ├── documents.py      # POST /api/v1/documents/upload
│   │   │   ├── eligibility.py    # GET /api/v1/eligibility/{id}
│   │   │   └── health.py         # GET /api/v1/health/langgraph
│   │   ├── deps.py               # Dependency injection (DB session)
│   │   ├── middleware.py         # CORS, request logging
│   │   └── router.py             # Route aggregation (prefix=/api/v1)
│   │
│   ├── services/                 # Layer 2 — Business logic orchestration
│   │   ├── auth_service.py       # Login, session management
│   │   ├── chat_service.py       # Orchestrator invocation, state persistence
│   │   ├── application_service.py# Application lifecycle
│   │   ├── document_service.py   # Document classification, storage
│   │   ├── extraction_service.py # Extraction pipeline coordination
│   │   ├── validation_service.py # Cross-document validation
│   │   ├── eligibility_service.py# ML eligibility scoring
│   │   ├── decision_service.py   # Final decision synthesis
│   │   └── extraction_pipeline.py# Document processing pipeline
│   │
│   ├── agents/                   # Layer 3 — LangGraph agents
│   │   ├── state.py              # ApplicantState TypedDict (25+ fields)
│   │   ├── checkpointer.py       # Shared PostgresSaver factory + TTL cleanup
│   │   ├── orchestrator/         # 7-phase StateGraph
│   │   │   ├── graph.py          # StateGraph definition, compilation
│   │   │   ├── nodes.py          # Re-exports from phases/
│   │   │   ├── phases/           # One file per phase (0–6)
│   │   │   ├── routes.py         # Conditional edge routing
│   │   │   └── di.py             # LLM and service injection
│   │   ├── extraction/           # ReAct agent + Gate 1
│   │   ├── validation/           # Reflexion loop + Gate 2
│   │   ├── eligibility/          # ML prediction + Gate 3
│   │   ├── decision/             # Synthesis + explanation
│   │   └── gates/                # Deterministic validation gates
│   │       ├── completeness.py   # Gate 2 — document completeness (validation phase)
│   │       ├── document_integrity.py  # Gate 1 — tamper detection (extraction phase)
│   │       ├── eligibility_rules.py   # Gate 3 — hard rules (eligibility phase)
│   │       └── retry_logic.py    # Retry/fallback behavior
│   │
│   ├── domain/                   # Layer 3 — Pure business logic (no I/O)
│   │   ├── constants/            # document_types, eligibility_rules, validation_rules
│   │   ├── schemas/              # 9 Pydantic models for agent I/O
│   │   ├── parsers/              # 8 document-type parsers + LLM extraction
│   │   ├── scoring/              # Confidence computation, validation scoring
│   │   ├── cross_document.py     # Identity, name, income, address comparison
│   │   ├── discrepancy_classifier.py  # OCR error vs real discrepancy
│   │   ├── document_classifier.py # File path → document type
│   │   └── exceptions/           # Domain-specific exceptions
│   │
│   ├── infrastructure/           # Layer 4 — External services
│   │   ├── db/                   # PostgreSQL
│   │   │   ├── models/           # 6 ORM models (applicant, application, document, extraction, validation, audit)
│   │   │   ├── repositories/     # Data access layer (base + 6 repos)
│   │   │   └── session.py        # AsyncSession factory
│   │   ├── document_processing/  # PDF parsing, OCR, table extraction
│   │   ├── graph/                # Neo4j client (document lineage)
│   │   ├── vector/               # Qdrant client (embeddings)
│   │   ├── llm/                  # LLM factory (Ollama / StreamLake)
│   │   └── observability/        # Langfuse client, structlog configuration
│   │
│   ├── utils/                    # Cross-cutting utilities
│   │   ├── circuit_breaker.py    # Graceful degradation for subgraphs
│   │   ├── retry.py              # @retry_transient decorator (1s, 2s, 4s backoff)
│   │   ├── error_classifier.py   # ErrorType enum (TRANSIENT, BUSINESS_RULE, LLM_ERROR, PROGRAMMING)
│   │   ├── state_size.py         # State size monitoring (warns at 50 KB)
│   │   ├── emirates_id.py        # Luhn algorithm, ID generation/validation
│   │   └── tool_helpers.py       # Shared helper functions for agent tools
│   │
│   ├── ml/                       # ML models and feature engineering
│   │   ├── eligibility_model.py  # Stub ML model
│   │   └── feature_engineering.py # Demographic/financial features
│   │
│   ├── data_generation/          # Synthetic test data generation
│   │   └── (profile, applicant, document generators)
│   │
│   ├── config.py                 # Global settings (pydantic-settings BaseSettings)
│   └── main.py                   # FastAPI app, lifespan context manager
│
├── ui/                           # Streamlit frontend
│   ├── streamlit_app.py          # Entrypoint with st.navigation
│   ├── app_pages/                # Page definitions (landing, chat)
│   ├── components/               # Reusable UI elements (11 components)
│   ├── fragments/                # @st.fragment wrapped sections
│   └── styles/                   # Global CSS
│
├── tests/                        # Test suite (~241+ unit tests)
│   ├── unit/                     # Mocked dependencies
│   ├── integration/              # Real databases, mocked LLM
│   ├── e2e/                      # Full stack
│   └── system/                   # System-level tests
│
├── evals/                        # Four-layer evaluation framework
│   ├── audit/                    # Tool inventory and coverage
│   ├── golden/                   # Ground-truth dataset validation
│   └── contracts/                # Pydantic contract conformance
│
├── alembic/                      # Database migrations
│   └── versions/                 # 4 migrations (initial schema, state_snapshot, validation_confidence, checkpoint_created_at)
│
├── docs/                         # Documentation
│   ├── adr/                      # Architecture Decision Records (0001–0006)
│   ├── superpowers/              # Design specs and plans
│   └── solution-summary.md       # Living 10-page architecture summary
│
├── scripts/                      # Utility scripts
│   └── generate_test_data.py     # 3 synthetic test profiles
│
└── data/                         # Runtime test data storage
    └── test_applicants/          # 3 cross-document-consistent profiles
```

---

## 3. Data Flow

### Request Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Streamlit  │ ──▶ │   FastAPI   │ ──▶ │  Services   │ ──▶ │   Agents    │
│     UI      │ ◀── │  (Layer 1)  │ ◀── │  (Layer 2)  │ ◀── │  (Layer 3)  │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                     ┌─────────────┐     ┌─────────────┐          │
                     │  PostgreSQL │ ◀──▶│  Neo4j/Qdr  │ ◀────────┘
                     │  (Layer 4)  │     │  (Layer 4)  │
                     └─────────────┘     └─────────────┘
```

### Phase-by-Phase Flow

| Phase | Name | Entry | Processing | Exit |
|-------|------|-------|------------|------|
| 0 | Authentication | Applicant enters Emirates ID | Luhn validation (`domain/utils/emirates_id.py`) | `identity_number` set in state |
| 1 | Intake | Chat messages | LLM extracts 13 fields from conversation | `applicant_info` populated |
| 2 | Document Collection | File upload | Document service classifies into 6 types | `uploaded_documents` dict |
| 3 | Processing | Auto-triggered | Extraction subgraph (ReAct + Gate 1) → Validation subgraph (Reflexion + Gate 2) | `extracted_data`, `validation_results` |
| 4 | Review | Auto-triggered | Discrepancy cards generated; clarification questions from templates | Applicant responds to clarifications |
| 5 | Decision | Auto-triggered | Eligibility agent (ML + Gate 3) → Decision agent (synthesis) | `decision`, `explanation`, `enablement` |
| 6 | Enablement | Auto-triggered | Post-decision recommendations packaged | Response rendered in UI |

### State Persistence

- All agent state flows through `ApplicantState` (TypedDict, 25+ fields)
- LangGraph `PostgresSaver` checkpoints state between phases
- `applications.state_snapshot` JSONB column stores full state (distinct from `langgraph_checkpoint`, which stores the raw LangGraph-internal checkpoint binary; `state_snapshot` is the deserialized, application-level state for inspection and recovery)
- Checkpoint TTL: 30 days (configurable via `CHECKPOINT_TTL_DAYS`)

### Observability

- Every LLM call traced via Langfuse v4
- Every timed operation logs `duration_ms` via structlog
- PII automatically redacted by custom processor

---

## 4. API Structure

### Endpoint Catalog

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/v1/auth/login` | `auth.py` | Login with Emirates ID |
| POST | `/api/v1/applications/{application_id}/chat` | `chat.py` | Send chat message, receive streaming response |
| GET | `/api/v1/applications` | `applications.py` | List applications |
| GET | `/api/v1/applications/{id}` | `applications.py` | Get application details |
| POST | `/api/v1/applications` | `applications.py` | Create new application |
| POST | `/api/v1/applications/{application_id}/documents` | `documents.py` | Upload document files |
| GET | `/api/v1/eligibility/{application_id}` | `eligibility.py` | Get eligibility score |
| GET | `/api/v1/health/langgraph` | `health.py` | Infrastructure health check |

### Authentication

- Stateless session via Emirates ID number
- `AuthService.login()` validates ID format (Luhn) and creates/returns applicant record
- No JWT or OAuth — government internal tool with network-level access control

### Error Handling

- Standard FastAPI `HTTPException` with status codes
- `ValueError` from services mapped to 400 BAD REQUEST
- Global exception handler in `middleware.py`
- All errors logged with `logger.exception()`

### Dependency Injection

- `get_db()` — yields `AsyncSession` from connection pool
- Service instances created per-request via `Depends()`
- DB session statement timeout: 30s (`STATEMENT_TIMEOUT`)

---

## 5. Data Model

### Entity Overview

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    applicants   │──1:N──│   applications  │──1:N──│    documents    │
│                 │       │                 │       │                 │
│ id (UUIDv7)     │       │ id (UUIDv7)     │       │ id (UUIDv7)     │
│ identity_number │       │ applicant_id    │       │ application_id  │
│ full_name       │       │ status          │       │ doc_type        │
│ date_of_birth   │       │ current_phase   │       │ file_path       │
│ created_at      │       │ state_snapshot  │       │ uploaded_at     │
└─────────────────┘       │ validation_conf │       │ extraction_data │
                          └─────────────────┘       └─────────────────┘
                                                         │
                                                         │ 1:1
                                                         ▼
                                               ┌─────────────────┐
                                               │   extractions   │
                                               │                 │
                                               │ id (UUIDv7)     │
                                               │ document_id     │
                                               │ extracted_fields│
                                               │ confidence      │
                                               └─────────────────┘
```

### Key Tables (16 total)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `applicants` | Applicant identity | `identity_number` (unique), `full_name`, `date_of_birth` |
| `applications` | Application lifecycle | `applicant_id`, `status`, `current_phase`, `state_snapshot` (JSONB), `validation_confidence` |
| `documents` | Uploaded documents | `application_id`, `doc_type`, `file_path`, `file_hash` |
| `document_extraction_fields` | Extracted structured data | `document_id`, `field_name`, `field_value`, `confidence_score` |
| `document_validation_results` | Cross-document validation | `application_id`, `field_name`, `is_consistent`, `discrepancy_type` |
| `document_audit_log` | Immutability trail | `entity_type`, `entity_id`, `action`, `old_value`, `new_value` |
| `checkpoints` | LangGraph state | `thread_id`, `checkpoint`, `created_at` |
| `document_processing_queue` | Background processing | `document_id`, `status`, `retry_count` |

### Migration History

| Migration | Changes |
|-----------|---------|
| `20260725001` | Initial schema — 16 tables |
| `20260726001` | Added `state_snapshot` JSONB to `applications` |
| `20260727001` | Added `validation_confidence` FLOAT to `applications` |
| `20260727002` | Added `created_at` TIMESTAMPTZ to `checkpoints` (TTL cleanup) |

---

## 6. Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `console` | Output format (`console` or `json`) |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres123@localhost:5432/social_support` | PostgreSQL connection string |
| `STATEMENT_TIMEOUT` | `30000` | Query timeout in milliseconds |
| `LLM_PROVIDER` | `streamlake` | LLM provider (`ollama` or `streamlake`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen3.5:14b` | Ollama model name |
| `STREAMLAKE_BASE_URL` | `https://vanchin.streamlake.ai/api/gateway/coding/v1` | StreamLake API endpoint |
| `STREAMLAKE_MODEL` | `kat-coder-pro-v2.5` | StreamLake model name |
| `LANGFUSE_ENABLED` | `True` | Enable Langfuse tracing |
| `LANGFUSE_HOST` | `http://localhost:4000` | Langfuse server URL |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB URL |
| `CHECKPOINT_TTL_DAYS` | `30` | Checkpoint retention period |
| `STATE_SIZE_WARNING_KB` | `50` | State size warning threshold |

### Feature Flags

| Flag | Location | Description |
|------|----------|-------------|
| `LANGFUSE_ENABLED` | `config.py` | Toggle observability tracing |
| `LLM_PROVIDER` | `config.py` | Switch between local/cloud LLM |

### Deployment Profiles

| Profile | LLM | Databases | Observability | Use Case |
|---------|-----|-----------|---------------|----------|
| Local dev | Ollama | Docker Compose | Langfuse local | Development |
| Production | StreamLake | Managed PostgreSQL/Neo4j/Qdrant | Langfuse cloud | Government deployment |

---

## 7. Security

### PII Handling

- **Redaction at rest:** Custom structlog processor masks `identity_number`, `full_name`, `account_number`, `phone`, `email` before log write
- **No PII in URLs:** All endpoints use UUIDs, not identity numbers
- **Local-first LLM:** Ollama keeps PII on-premises; StreamLake fallback only when GPU unavailable ([ADR 0004](adr/0004-local-llm-fallback.md))
- **Secret management:** `SecretStr` for API keys; never logged

### Access Control

- Network-level access control (government internal network)
- Emirates ID validation on login (Luhn algorithm)
- No role-based access control in current implementation

### Encryption

- PostgreSQL: TLS in transit (connection string dependent)
- Neo4j: Bolt protocol with optional encryption
- Qdrant: REST/gRPC with optional TLS
- File uploads: Stored on local filesystem; no encryption at rest in prototype

### Audit Trail

- `document_audit_log` table provides immutability for all entity changes
- Langfuse traces every LLM call and agent transition
- Structured logs with `duration_ms` timing on all operations

---

## 8. Constraints

### Known Limitations

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| Local Ollama requires GPU | Deployment environments without GPU must use StreamLake fallback | Single env var switch; documented minimum requirements |
| No rate limiting on chat/upload | Potential LLM pipeline abuse | FastAPI middleware can be added |
| File uploads stored locally | No S3-compatible storage in prototype | MinIO available in Langfuse stack; can be repurposed |
| Binary LLM provider switch | No tiered fallback chain | Can add health-check-based selection |
| No pagination on list endpoints | Does not scale beyond hundreds of records | Cursor-based pagination can be added |
| English-only agent prompts | Arabic-speaking applicants not supported | Mimesis Arabic locale already in data generation |

### Assumptions

- Government internal network provides perimeter security
- Applicants have digital document uploads (PDF, PNG, DOCX, XLSX)
- Emirates ID numbers follow Luhn-valid format
- Cross-document consistency is the primary fraud indicator

### Boundaries

- **In scope:** Automated extraction, validation, eligibility scoring, decision synthesis
- **Out of scope:** Real-time government API integration (ICA, AECB, banks), benefit disbursement, case management

---

## 9. Tech Debt

### Documented Shortcuts

| Area | Shortcut | Reason | Tracking |
|------|----------|--------|----------|
| ML model | `ml/eligibility_model.py` is a stub | Prototype phase; real model requires training data | Deferred to production |
| Document processing queue | `document_processing_queue` table exists but not wired to worker | Synchronous processing sufficient for prototype | Background worker deferred |
| Accuracy evals | 3 eval stubs need ground-truth datasets | Four-layer correctness framework complete; metrics pending | `evals/test_extraction_accuracy.py` etc. |
| Graph/vector updates | Post-commit hooks, not transactional | Cross-database transactions not possible | Eventual consistency accepted |

### Deferred Work

- Production LLM failover chain (local → Azure → AWS)
- Real-time government API integrations (ICA identity verification, AECB credit pull, open banking)
- Multi-language prompt localization (Arabic)
- Idempotency keys on application creation
- Webhook callbacks for long-running operations
- Case management system export (batch CSV/SFTP or REST push)
- Audit trail compliance with UAE government record-keeping standards

---

## 10. Code Hotspots

### Files Most Likely to Change

| File | Reason | Coupling |
|------|--------|----------|
| `src/agents/orchestrator/graph.py` | Phase transitions, subgraph wiring | High — all agents depend on orchestrator structure |
| `src/agents/orchestrator/phases/` | Per-phase logic evolves with requirements | Medium — 7 files, one per phase |
| `src/domain/schemas/` | Agent I/O contracts change with extraction needs | Medium — 9 files, all agents consume |
| `src/services/chat_service.py` | Streaming, interrupt handling, state persistence | High — central coordination point |
| `src/config.py` | New environment variables, feature flags | Low — additive changes only |
| `src/infrastructure/db/models/` | Schema evolution via Alembic | Medium — repositories depend on models |
| `src/agents/validation/graph.py` | Reflexion loop topology | Medium — tools and prompts depend on structure |

### Coupling Points

1. **`ApplicantState`** (`src/agents/state.py`) — Every agent reads/writes this TypedDict. Adding fields requires updating all consumers.
2. **`get_checkpointer()`** (`src/agents/checkpointer.py`) — Shared singleton across all graphs. TTL cleanup affects all checkpoint retention.
3. **`settings`** (`src/config.py`) — Global singleton; all modules import from here.
4. **`domain/cross_document.py`** — Called by validation agent and gates. Comparison algorithm changes affect Gate 2.
5. **`src/api/router.py`** — Single aggregation point for all v1 routes.

### Stable Areas

- `src/domain/constants/` — Domain rules change infrequently
- `src/infrastructure/db/session.py` — Standard asyncpg factory pattern
- `src/utils/retry.py` — Generic decorator, unlikely to change
- `ui/components/` — Component interface contracts are stable
