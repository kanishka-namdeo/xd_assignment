# Application Source Code

## Purpose
Main application package implementing the UAE Social Support Application workflow automation system. Implements a 7-phase applicant flow using LangGraph agents, FastAPI REST endpoints, and PostgreSQL/Neo4j/Qdrant data storage.

## Ownership
- Primary: Development Team
- Review Required: Code changes require review

## Local Contracts

### Four-Layer Architecture
Strict dependency direction enforced:
- **Layer 1 - API Routes** (`api/`): Thin HTTP endpoints (5-12 lines). Parse input, call service, format output. No business logic.
- **Layer 2 - Services** (`services/`): Business logic orchestration. Own agent loop, session state, retry/fallback. Routes call services.
- **Layer 3 - Agents + Domain** (`agents/`, `domain/`): LangGraph agent definitions and pure domain logic. Services call agents.
- **Layer 4 - Infrastructure** (`infrastructure/`): External services (DB, LLM, vector DB, graph DB). Agents and services call infrastructure.

**Dependency rule**: Each layer imports only from layers below. No circular imports. Domain layer has no I/O.

### File Size and Decomposition Guardrails
These rules prevent the accumulation of oversized modules.

| Metric | Limit | Action |
|--------|-------|--------|
| Any `.py` file | 15 KB or 300 lines | Mandatory decomposition |
| Agent `nodes.py` | 150 lines or 4 node functions | Split nodes into `phases/<name>.py` or `helpers.py` |
| Agent `tools.py` | 30 lines per `@tool` | Extract business logic to `domain/` |
| Service class | 200 lines | Extract domain-specific logic to `domain/` |

### Orchestrator Decomposition
Multi-phase orchestrators MUST decompose per-phase logic:
- Each phase node lives in `agents/orchestrator/phases/<phase>.py`
- `agents/orchestrator/nodes.py` re-exports from `phases/` for backward compatibility
- Cross-cutting utilities (service injection, LLM helpers, document classification) go in `agents/orchestrator/di.py`
- Phase nodes MUST NOT import directly from Layer 4 (infrastructure). They call services; services call infrastructure.
- Phase nodes MUST NOT open DB sessions, create repositories, or persist data directly.

### Tool Thinness Rule
`@tool` decorated functions MUST be thin wrappers (<30 lines):
1. Validate inputs
2. Call a domain function
3. Format output with logging

All business logic (comparison algorithms, scoring, classification rules, question templates) lives in `domain/`.

### Domain Layer
Pure business logic with no I/O lives in `src/domain/`:

| Module | Purpose |
|--------|---------|
| `domain/parsers/<doc_type>.py` | Per-document-type parsing logic (one function per document type) |
| `domain/parsers/llm_extraction.py` | LLM-assisted extraction orchestration |
| `domain/parsers/text_extract.py` | Text extraction utilities |
| `domain/scoring/confidence.py` | Confidence score computation |
| `domain/scoring/validation_scorer.py` | Validation confidence aggregation |
| `domain/cross_document.py` | Identity, name, income, address comparison functions |
| `domain/discrepancy_classifier.py` | OCR error vs real discrepancy classification |
| `domain/document_classifier.py` | File path → document type classification |
| `domain/schemas/` | Pydantic models for agent output validation |
| `domain/templates/` | Clarification question templates |
| `domain/constants/` | Domain constants (document types, eligibility rules, validation rules) |
| `domain/exceptions/` | Domain-specific exception classes |

### Service Delegation Rule
Services MUST NOT implement document-type-specific logic inline. Instead:
- Call `domain/parsers/<type>.parse()` for per-document parsing
- Call `domain/scoring/` for confidence computation
- Call `domain/cross_document.py` for comparison algorithms
- Delegate persistence, embeddings, lineage to infrastructure via repositories

**Service inventory** (all class-based with `__init__(session: AsyncSession)`):
- `AuthService` (`auth_service.py`): Login/session management, applicant/application creation
- `ChatService` (`chat_service.py`): Orchestrator invocation, state persistence, interrupt handling, decision persistence
- `ApplicationService`, `DocumentService`, `EligibilityService`, `ValidationService`, `DecisionService`, `ExtractionService`

### ORM Model Directory at Scale
When a model module exceeds 5 models with wide schemas, use a subdirectory:
- `infrastructure/db/models/` for small modules (1-4 models)
- `infrastructure/db/models/<domain>/` with one file per model when >5 models

### Node Purity
Node functions in `nodes.py` contain only graph logic:
- State reads/writes
- Service invocations
- Phase transitions
- Conditional branching

The following do NOT belong in `nodes.py`:
- Output parsing logic → `<agent>/parsers.py`
- Pydantic model definitions → `domain/schemas/`
- Agent construction → `graph.py`
- LLM client creation → `infrastructure/llm/factory.py` or dependency injection
- Database sessions → service methods

### LangGraph Agent Structure
Each agent follows official LangGraph conventions:
- `graph.py`: StateGraph definition and compilation
- `nodes.py`: Node functions (pure logic)
- `routes.py`: Conditional edge routing (deterministic)
- `prompts.py`: System prompts (versionable, testable)
- `tools.py`: @tool decorators for agent capabilities
- `parsers.py`: Output parsing logic (optional, for extraction agent)
- `output.py`: Output formatting helpers (optional)
- `agent_runner.py`: Agent execution wrapper (optional, for extraction agent)

### Deterministic Gates
Validation gates are graph nodes in `agents/gates/`. Use `add_conditional_edges` for routing. Keep gates deterministic (no LLM calls) for <5ms latency.

| Gate | Purpose |
|------|---------|
| `completeness.py` | Document completeness validation |
| `document_integrity.py` | Tamper/forgery detection |
| `eligibility_rules.py` | Hard eligibility rule checks |
| `retry_logic.py` | Retry and fallback logic |

### Infrastructure Layer
External service integrations in `src/infrastructure/`:

| Module | Purpose |
|--------|---------|
| `db/models/` | SQLAlchemy ORM models |
| `db/repositories/` | Data access layer with base repository pattern |
| `db/session.py` | Database session management |
| `document_processing/` | Unified extraction API: PDF parsing, OCR, table extraction, resume parsing, XLSX extraction |
| `graph/` | Neo4j graph database (family relationships, document lineage) |
| `llm/` | LLM client and embedding client |
| `observability/` | Langfuse client, structured logging, tracing |
| `vector/` | Qdrant vector database (document embeddings) |
| `extraction_persistence.py` | Extraction result persistence helpers |

**Note**: `graph_db/` and `vector_db/` were legacy stubs and have been removed. Active modules are `graph/` and `vector/`.

### Utilities Layer
Shared utilities in `src/utils/`:

| Module | Purpose |
|--------|---------|
| `circuit_breaker.py` | Circuit breaker pattern for graceful degradation of subgraph invocations |
| `retry.py` | `@retry_transient` decorator with exponential backoff (1s, 2s, 4s) for transient failures |
| `state_size.py` | State size estimation and monitoring; warns when state exceeds `STATE_SIZE_WARNING_KB` threshold |
| `error_classifier.py` | Error classification (`ErrorType` enum: TRANSIENT, BUSINESS_RULE, LLM_ERROR, PROGRAMMING) |
| `tool_helpers.py` | Shared helper functions for agent tools |

**Circuit Breaker**: Opens after N failures, blocks calls until recovery timeout, then tests with single call. Used in `processing.py` and `decision.py` to prevent cascading failures when subgraphs consistently fail.

### Checkpointer Infrastructure
Shared checkpointer factory in `src/agents/checkpointer.py`:
- `get_checkpointer()` — async singleton factory returning `AsyncPostgresSaver` shared by all graphs
- `CheckpointerManager` — manages background TTL cleanup task with configurable interval
- `get_checkpointer_manager()` — returns singleton manager instance
- TTL cleanup runs periodically, deleting checkpoints older than `CHECKPOINT_TTL_DAYS` (default 30)
- Cleanup task started/stopped via FastAPI lifespan in `src/main.py`

### Streaming Support
`src/services/agent_runner.py` provides two execution modes:
- `run()` — blocking `ainvoke()` for standard request/response
- `run_streaming()` — async generator using `astream()` that yields phase transitions and key events (extraction_complete, validation_complete, decision_reached, eligibility_scored, interrupt)

### Health Check Endpoint
`/api/v1/health/langgraph` verifies PostgreSQL connection and all LangGraph graph compilation. Returns `healthy`, `degraded`, or `unhealthy` status with component details.

### Configuration
- Global config in `config.py` using pydantic-settings `BaseSettings`
- Environment variables via `.env` file
- LLM provider switching: `LLM_PROVIDER=ollama` or `LLM_PROVIDER=streamlake`
- Embeddings always local via Ollama

### Logging Conventions
Logging conventions are defined in `.cursor/rules/logging-practices.mdc`. All modules must follow structured logging with `structlog`, PII redaction, and `duration_ms` timing.

### Data Generation Module
Synthetic data generation for testing and development. All generators produce schema-compliant output with cross-document consistency.

**Core components**:
- `profile.py`: ApplicantProfile Pydantic model - single source of truth for applicant identity
- `applicant_generator.py`: Mimesis-based profile generation with Arabic locale support
- `emirates_id_generator.py`: Luhn-valid Emirates ID numbers and card images
- `bank_statement_generator.py`: PDF statements with UAE bank templates (Emirates NBD, FAB, ADCB, Mashreq)
- `credit_report_generator.py`: AECB-format credit reports with faker-credit-score
- `resume_generator.py`: DOCX/PDF resumes via ResumeCraft
- `assets_liabilities_generator.py`: XLSX financial statements
- `application_form_generator.py`: Handwritten form images via OCRSmith
- `consistency.py`: Cross-document validation (identity, income, address, employment)
- `templates/`: Bank layouts and form templates
- `utils.py`: Luhn algorithm, IBAN generation, UAE-specific helpers

**Consistency rules**: All generators accept an ApplicantProfile seed. identity_number, full_name, date_of_birth, monthly_salary, and employer_name are synchronized across all documents.

## Work Guidance

### Adding a New Agent
1. Create subfolder in `agents/` with 5 files (graph.py, nodes.py, routes.py, prompts.py, tools.py)
2. Define agent state in `agents/state.py` if needed
3. Implement node functions in `nodes.py` (keep <150 lines; split helpers to `parsers.py` or `helpers.py`)
4. Define routing logic in `routes.py`
5. Write system prompts in `prompts.py`
6. Create @tool wrappers in `tools.py` (keep <30 lines per tool; extract business logic to `domain/`)
7. Wire into orchestrator graph in `agents/orchestrator/graph.py`

### Adding a New API Endpoint
1. Create endpoint in `api/v1/` (applications.py, auth.py, chat.py, documents.py, eligibility.py)
2. Keep route thin: parse input, call service, return response
3. Implement business logic in corresponding `services/` file
4. Add Pydantic schemas in `domain/schemas/`
5. Register route in `api/router.py`
6. Add dependencies in `api/deps.py` if needed

### Adding Database Models
1. Create SQLAlchemy ORM model in `infrastructure/db/models/`
2. Create repository in `infrastructure/db/repositories/`
3. Run Alembic migration: `alembic revision --autogenerate -m "description"`

## Verification
- Unit tests in `tests/unit/` mock all dependencies
- Integration tests in `tests/integration/` use real DB, mocked LLM
- E2E tests in `tests/e2e/` and `tests/system/` validate full application flows
- Agent test suites cover orchestrator (51 tests), extraction (26), validation (29), eligibility (27), and decision (39) agents
- Gate tests cover completeness (9), document integrity (22), eligibility rules (15), and retry logic (12)
- Domain tests cover Emirates ID generation (9)
- Type checking: Pyright/mypy (required)
- Linting: Ruff (required)

## Child DOX Index
None - single-level structure. All subfolders are implementation details of the application.
