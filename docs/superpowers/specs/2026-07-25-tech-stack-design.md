# Tech Stack Design: Social Support Application Workflow Automation

**Date**: 2026-07-25  
**Status**: Finalized  
**Python Version**: 3.11.12 (venv at `.venv/`)

---

## Technology Decisions

### 1. Agent Orchestration: LangGraph 1.2.9

**Decision**: Use LangGraph as the primary agent orchestration framework.

**Rationale**:
- **Durable checkpointed state**: Government social support applications involve long-running workflows with multiple review stages. LangGraph's checkpointing allows the system to resume from the last node after a failure rather than replaying the entire conversation. This is critical for production reliability.
- **Human-in-the-loop gates**: The workflow requires approval gates for edge cases flagged for manual review. LangGraph's `interrupt()` + `Command` resume pattern is purpose-built for regulated workflows.
- **Auditability**: Every node transition is a checkpoint. Combined with Langfuse tracing, this provides full replay capability for compliance and debugging.
- **Explicit graph control**: The workflow is a state machine (data extraction → validation → eligibility check → decision), not a loose collaboration. LangGraph's directed graph model maps cleanly to this structure.

**Version**: `langgraph==1.2.9` (released 2026-07-10, requires Python >=3.10)

---

### 2. Reasoning Framework: ReAct (Primary) + Reflexion (Validation)

**Decision**: Use ReAct as the primary reasoning framework for all agent nodes. Use Reflexion specifically for the data validation agent.

**Rationale**:
- **ReAct (Thought → Action → Observation)**: This is the standard for tool-using agents. Each LangGraph node implements ReAct for its specific task (extraction, validation, eligibility check, decision). This maps cleanly to the graph topology.
- **Reflexion for validation**: The data validation agent needs to critique its own output and identify inconsistencies (e.g., address mismatch between form and credit report, income discrepancies across documents). Reflexion's self-correction loop (attempt → evaluate → critique → retry) directly addresses the spec's pain points around "inconsistent information" and "semi-automated data validations."

**Implementation**:
- Each LangGraph node follows ReAct: the agent thinks about what to do, calls a tool (extraction, validation, scoring), observes the result, and decides next steps.
- The validation node uses Reflexion: after initial extraction, it critiques the output, identifies inconsistencies, and retries up to N times before escalating to human review.

---

### 3. Vector Database: Qdrant 1.18.0

**Decision**: Use Qdrant as the vector database for document embeddings and semantic search.

**Rationale**:
- **Disk-based architecture (Rust)**: Scales to millions of document embeddings without RAM cost explosion. This is critical for a production system processing thousands of applications with multiple documents each.
- **Payload filtering in indexing pipeline**: Qdrant's filtering is part of the indexing pipeline, not post-retrieval. This matters when filtering by document type (bank statement vs. Emirates ID vs. credit report) + applicant ID simultaneously. Performance doesn't degrade with complex filters.
- **Binary quantization (v1.17+)**: Reduces memory usage by up to 40x. Relevant for a prototype that might grow to production scale.
- **Apache 2.0 license**: No restrictions on use or deployment.
- **gRPC support**: Use `prefer_grpc=True` for throughput.

**Version**: `qdrant-client==1.18.0` (released May 2026, requires Python >=3.10)

---

### 4. Graph Database: Neo4j 6.2.0

**Decision**: Use Neo4j for relationship modeling (family/household structure) and document lineage (audit trail).

**Rationale**:
- **Family/household traversal**: Deep graph queries (who depends on whom, shared assets across multiple hops) are Neo4j's strength. Index-free adjacency provides consistent performance across high-hop queries.
- **Document lineage**: Provenance chains (which document supports which claim, validation history) need strong pattern matching. Cypher is ideal for expressing these relationships.
- **GenAI integrations (2026)**: Neo4j now supports vector search, LLM-powered knowledge graph construction, and GraphRAG. This enables combining structured eligibility data with LLM reasoning for explainable decisions.
- **MCP Server for agent memory**: Neo4j can serve as the agent's long-term memory for applicant context across sessions.
- **Production maturity**: Neo4j is the industry standard for fraud detection, recommendation engines, and knowledge graphs. Cypher is a mature, well-documented query language.

**Version**: `neo4j==6.2.0` (requires Python >=3.10, supports Neo4j server 4.4, 5.x, 2025.x, 2026.x)

---

### 5. Observability: Langfuse 4.14.1 (Self-Hosted)

**Decision**: Use Langfuse v4 (self-hosted) for end-to-end AI observability.

**Rationale**:
- **MIT-licensed core**: Free, no feature gates. Self-hosting requires ClickHouse + PostgreSQL + Redis + S3. Langfuse uses a dedicated PostgreSQL instance (separate from the app database) for cleaner isolation. Docker Compose deployment takes ~5 minutes.
- **End-to-end tracing**: LLM calls, tool invocations, retrieval steps, agent actions — with waterfall views and session replay. This is essential for debugging complex multi-agent workflows.
- **Native LangGraph integration**: Via OpenTelemetry. Traces flow automatically from LangGraph nodes to Langfuse.
- **Prompt management**: Version control for prompts without redeployment. Critical for iterating on agent prompts during development.
- **Evaluation workflows**: LLM-as-judge for hallucination and relevance scoring. Enables automated quality gates.
- **De facto standard**: Langfuse is the most widely adopted open-source LLM observability platform in 2026. Acquired by ClickHouse in January 2026, signaling long-term investment.

**Important**: Langfuse v4 (released March 2026) is a ground-up rewrite with an "observation-centric data model." The API changed significantly from v3. We start fresh with v4, so no migration needed, but all examples/tutorials must use v4 documentation.

**Architecture** (6 containers):
- `langfuse-web` (port 4000) — Web UI and API
- `langfuse-worker` (port 3030) — Background worker for async processing
- `langfuse-postgres` (port 5433) — Dedicated PostgreSQL 17 for metadata (separate from app DB on 5432)
- `langfuse-clickhouse` (ports 8123, 9000) — ClickHouse 25.12 for observation data (pinned to avoid 26.x breaking changes)
- `langfuse-redis` (port 6379) — Redis 7 for cache and queue
- `langfuse-minio` (ports 9090, 9091) — MinIO for S3-compatible event/media storage

**Version**: `langfuse==4.14.1` (released 2026-07-20, requires Python >=3.10, <4.0)

---

### 6. LLM Inference: Ollama (Local) + StreamLake (Cloud)

**Decision**: Use Ollama for local LLM hosting and embedding generation. Use StreamLake as an OpenAI-compatible cloud endpoint for LLM inference. Users can switch between Ollama and StreamLake for chat/reasoning via configuration. Embeddings always run on Ollama.

**Rationale**:
- **OpenAI-compatible APIs**: Both Ollama (`localhost:11434/v1`) and StreamLake (`https://vanchin.streamlake.ai/api/gateway/coding/v1`) expose OpenAI-compatible endpoints. A single `openai` Python SDK client works for both — just swap `base_url` and `api_key`.
- **No LiteLLM needed**: Since both providers speak the same protocol, adding LiteLLM would be unnecessary abstraction. The OpenAI SDK is sufficient.
- **Ollama for local**: Multimodal support (Gemma 3/4), zero cost, privacy, no network dependency. Required for embeddings (FastEmbed uses Ollama's local models).
- **StreamLake for cloud**: Higher-quality models when local VRAM is insufficient. Model: `kat-coder-pro-v2.5`. Pay-as-you-go or subscription billing.
- **Switching mechanism**: Configuration-driven via `pydantic-settings`. Set `LLM_PROVIDER=ollama` or `LLM_PROVIDER=streamlake` in `.env`. The application creates the appropriate OpenAI client at startup.

**Configuration**:
```python
# .env
LLM_PROVIDER=ollama              # or "streamlake"
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=ollama            # Ollama doesn't require a real key
OLLAMA_MODEL=qwen3.5:14b
STREAMLAKE_BASE_URL=https://vanchin.streamlake.ai/api/gateway/coding/v1
STREAMLAKE_API_KEY=<your-api-key>
STREAMLAKE_MODEL=kat-coder-pro-v2.5
EMBEDDING_PROVIDER=ollama        # Always local
EMBEDDING_MODEL=nomic-embed-text
```

**Recommended Local Models (Ollama)**:
- **Text reasoning**: `qwen3.5:14b` or `llama3.3:8b` (good instruction following, fits in 12-16 GB VRAM)
- **Vision/document processing**: `gemma3:12b` for OCR, chart analysis, image description (requires 12 GB VRAM)
- **Embeddings**: `nomic-embed-text` or `mxbai-embed-large` (always local)
- **Fallback for low VRAM**: `gemma3:4b` (4 GB VRAM) or `qwen3.5:7b`

**Cloud Model (StreamLake)**:
- **Model**: `kat-coder-pro-v2.5` — served via OpenAI-compatible endpoint
- **Base URL**: `https://vanchin.streamlake.ai/api/gateway/coding/v1` (Coding Plan) or `https://vanchin.streamlake.ai/api/gateway/v1/endpoints` (Pay-as-you-go)

**Versions**:
- Ollama: latest (v0.30.x as of July 2026)
- `openai` SDK: latest (compatible with both endpoints)

---

### 7. ML Classification: Scikit-learn 1.9.0

**Decision**: Use scikit-learn for eligibility scoring as the deterministic ML layer.

**Rationale**:
- **Required by spec**: The spec explicitly calls for scikit-learn algorithms for classification.
- **Eligibility scoring**: Gradient boosting (`HistGradientBoostingClassifier`) handles mixed feature types (income, family size, employment history, demographic profile) well. It's robust to non-linear relationships and feature interactions.
- **Pipeline pattern**: Use `Pipeline` with `ColumnTransformer` to prevent data leakage between preprocessing and modeling. This is a scikit-learn best practice.
- **Separation of concerns**: Scikit-learn produces an eligibility score that the LLM agents use as input to their recommendations. ML handles structured prediction, LLM handles reasoning and explanation. This is cleaner than having the LLM do all the work.

**Version**: `scikit-learn==1.9.0` (released 2026-06-02, requires Python >=3.11, supports 3.11-3.14)

---

### 8. API Serving: FastAPI 0.139.2

**Decision**: Use FastAPI for the REST API layer.

**Rationale**:
- **Required by spec**: The spec explicitly calls for FastAPI.
- **Async/sync separation**: Use `async def` for endpoints that call Ollama or Qdrant (I/O-bound). Use `def` for endpoints that call scikit-learn (CPU-bound, runs in thread pool). This follows FastAPI best practices.
- **Pydantic v2 integration**: Native request/response validation with `strict=True` for business-critical fields. FastAPI 0.139.2 requires pydantic >=2.9.0.
- **API versioning**: Use `/api/v1/applications/`, `/api/v1/eligibility/` for clean versioning.
- **Dependency injection**: Use `Depends` for database sessions, config, and auth. Design for `dependency_overrides` in tests.
- **Performance**: Connection pooling (`pool_size=10`, `max_overflow=20`), `pool_pre_ping=True` for cloud environments.

**Version**: `fastapi==0.139.2` (released 2026-07-16, requires Python >=3.10)

---

### 9. Frontend: Streamlit 1.60.0

**Decision**: Use Streamlit for the interactive chat UI and application intake form.

**Rationale**:
- **Required by spec**: The spec explicitly calls for Streamlit.
- **Caching**: Use `@st.cache_data` with `ttl` for API responses. Use `@st.cache_resource` for global objects (database connections, ML models).
- **Performance**: Use `@st.fragment` for partial reruns — chat interaction shouldn't rerun the entire page. This is up to 80% faster.
- **Form handling**: Use `st.form` for the application intake form to batch inputs and prevent excessive reruns.
- **Conditional rendering**: Use `st.toggle`, `st.segmented_control`, `@st.dialog` for interactive UI elements.

**Version**: `streamlit==1.60.0` (requires Python >=3.10, supports 3.10-3.14)

---

### 10. Data Validation: Pydantic 2.13.4

**Decision**: Use Pydantic v2 for all data validation and serialization.

**Rationale**:
- **Required by FastAPI**: FastAPI depends on Pydantic >=2.9.0.
- **Type safety**: Use `field_validator`, `model_validator` (not deprecated `@validator`, `@root_validator`). Use `model_config = ConfigDict(...)` (not inner `class Config:`).
- **Strict mode**: Apply `strict=True` for business-critical fields (income, applicant ID, eligibility scores).
- **Sensitive data**: Use `SecretStr` for sensitive config to prevent log leakage.
- **Langfuse v4 compatibility**: Langfuse v4 requires Pydantic v2. Starting with v2 throughout avoids compatibility issues.

**Version**: `pydantic==2.13.4` (released 2026-05-06, requires Python >=3.9)

---

### 11. Database: PostgreSQL (via SQLAlchemy 2.0 + asyncpg)

**Decision**: Use PostgreSQL as the primary relational database for application data, with SQLAlchemy 2.0 async sessions.

**Rationale**:
- **Required by spec**: The spec explicitly calls for PostgreSQL.
- **Async patterns**: Use `asyncpg` driver with SQLAlchemy 2.0: `postgresql+asyncpg://`. Set `expire_on_commit=False` in `async_sessionmaker` to prevent `MissingGreenlet` errors.
- **Connection pooling**: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=1800` (30 min).
- **Query optimization**: Use `selectinload` for relationships to prevent N+1 queries. Set `statement_timeout` via `SET LOCAL`.
- **Langfuse compatibility**: Langfuse self-hosted requires PostgreSQL for metadata and configuration. We already need it, so no additional overhead.

**Version**: `sqlalchemy>=2.0`, `asyncpg>=0.9.0`

---

### 12. Configuration: Pydantic Settings 2.x

**Decision**: Use `pydantic-settings` with `BaseSettings` for typed, validated configuration.

**Rationale**:
- **Type safety**: Define `SettingsConfigDict` with `env_file=".env"`, `secrets_dir` for containers. Priority: CLI args > init args > env vars > .env > secrets_dir > defaults.
- **Fail-fast**: Validate all config at startup. Missing required config should crash immediately, not fail at runtime.
- **Nested config**: Use `env_nested_delimiter="__"` for nested config (e.g., `DATABASE__HOST`, `OLLAMA__BASE_URL`).

**Version**: `pydantic-settings>=2.0.0`

---

### 13. Retry Logic: Tenacity

**Decision**: Use `tenacity` for exponential backoff with jitter on external service calls.

**Rationale**:
- **Resilience**: External services (Ollama, Qdrant, Neo4j) can fail transiently. Tenacity provides retry with exponential backoff and jitter to prevent thundering herd.
- **Selective retry**: Retry only 429 and 5xx errors. Never retry 4xx (client errors). Respect `retry-after` headers.
- **Jitter**: Add `random.uniform(0, 1)` to backoff to prevent synchronized retries across multiple clients.

**Version**: `tenacity>=8.1.0`

---

### 14. Logging: Structlog

**Decision**: Use `structlog` for structured logging with PII masking.

**Rationale**:
- **Structured logs**: JSON-formatted logs with context (applicant ID, session ID, agent node) are essential for debugging and audit.
- **PII masking**: Automatically mask sensitive data (applicant names, IDs, financial information) in logs. This is critical for government data.
- **Integration**: Structlog integrates with Langfuse for correlating logs with traces.

**Version**: `structlog>=23.0.0`

---

## Dependency Convergence

**No conflicts detected:**

- **Pydantic**: FastAPI needs >=2.9.0, LangGraph needs >=2.7.4, Langfuse v4 needs v2. All satisfied by 2.13.4.
- **Python 3.11.12**: Every package supports it. scikit-learn 1.9.0 has the tightest floor (>=3.11 exactly) — we meet it.

**Two things to be aware of:**

1. **Langfuse v4 is a ground-up rewrite** (March 2026). The API changed to an "observation-centric data model." We start fresh so no migration needed, but any examples/tutorials referencing v3 API won't work — use only v4 docs.
2. **scikit-learn 1.9.0 dropped Python 3.10 support** — minimum is now 3.11. Our 3.11.12 works, but this means we can never downgrade the venv Python. Not an issue since we have no reason to.

---

## Installation Commands

```bash
# Core dependencies
.\.venv\Scripts\pip.exe install langgraph==1.2.9
.\.venv\Scripts\pip.exe install qdrant-client==1.18.0
.\.venv\Scripts\pip.exe install neo4j==6.2.0
.\.venv\Scripts\pip.exe install langfuse==4.14.1
.\.venv\Scripts\pip.exe install scikit-learn==1.9.0
.\.venv\Scripts\pip.exe install "fastapi[standard]==0.139.2"
.\.venv\Scripts\pip.exe install streamlit==1.60.0
.\.venv\Scripts\pip.exe install pydantic==2.13.4
.\.venv\Scripts\pip.exe install pydantic-settings>=2.0.0
.\.venv\Scripts\pip.exe install sqlalchemy>=2.0.0
.\.venv\Scripts\pip.exe install asyncpg>=0.9.0
.\.venv\Scripts\pip.exe install tenacity>=8.1.0
.\.venv\Scripts\pip.exe install structlog>=23.0.0
.\.venv\Scripts\pip.exe install openai>=1.0.0  # OpenAI-compatible client for Ollama and StreamLake

# Synthetic data generation
.\.venv\Scripts\pip.exe install mimesis==19.1.0
.\.venv\Scripts\pip.exe install pandas>=2.0.0
.\.venv\Scripts\pip.exe install openpyxl>=3.1.0
.\.venv\Scripts\pip.exe install resumecraft==0.6.0
.\.venv\Scripts\pip.exe install "synthetic-statement[pdf] @ git+https://github.com/RohitSSolanki/synthetic-statement@main"
.\.venv\Scripts\pip.exe install faker-credit-score==1.0.0
.\.venv\Scripts\pip.exe install reportlab>=4.0.0
.\.venv\Scripts\pip.exe install Pillow>=10.0.0
.\.venv\Scripts\pip.exe install ocrsmith>=0.1.0

# Optional (good-to-have)
.\.venv\Scripts\pip.exe install fastembed>=0.8.0  # For Qdrant embeddings
.\.venv\Scripts\pip.exe install textbaker>=0.1.6  # Alternative OCR data generator with GUI
```

---

### 15. Synthetic Data Generation

**Decision**: Generate synthetic applicant data and documents using specialized libraries per document type.

**Rationale**: The spec allows synthetic/mockup data (line 17). We need realistic documents to test the full ingestion pipeline.

**Per-document libraries:**

| Document Type | Library | Version | Python Compatibility | Notes |
|---|---|---|---|---|
| **Tabular applicant data** | `Mimesis` + `pandas` | Mimesis 19.1.0 | ✓ 3.11 | 2-15x faster than Faker, better uniqueness (99.88% vs 93.63%). Generate names, addresses, income, employment, family size. Combine with custom logic for correlations. |
| **Emirates ID (image)** | Custom generator | N/A | ✓ 3.11 | Custom Luhn-based Emirates ID generator + `Pillow`/`reportlab` for card rendering. Implements `784-YYYY-NNNNNNN-C` format with proper checksum. |
| **Bank statement (PDF)** | `synthetic-statement[pdf]` | git main | ✓ 3.11 | Purpose-built for bank statements. Locale-aware, deterministic with seed. Uses `reportlab` for PDF. Extend with UAE bank templates (Emirates NBD, FAB, ADCB). |
| **Credit report (PDF)** | `faker-credit-score` + `reportlab` | 1.0.0 | ✓ 3.11 | `faker-credit-score` generates realistic FICO/VantageScore scores (300-900 range). Custom `reportlab` template for AECB credit report PDF with facilities, payment history. |
| **Resume (DOCX/PDF)** | `resumecraft` | 0.6.0 | ✓ 3.11 | Schema-driven resume generation from Pydantic-validated JSON. ATS-friendly DOCX/PDF output. Structured fields map directly to `resume_data` and `resume_work_experience` tables. |
| **Assets/liabilities (XLSX)** | `openpyxl` + `pandas` | openpyxl 3.1.x | ✓ 3.11 | Create structured financial data with formulas. Generate realistic asset categories, liabilities, and net worth calculations. |
| **Handwritten forms (image)** | ocrsmith | 0.1.0+ | ✓ 3.11 | Replaced TRDG (incompatible with Python 3.11, requires TF 1.x). OCRSmith provides native Arabic + Latin text rendering, modular augmentation pipeline (noise, blur, brightness, rotation), and active maintenance. |

**Version**: See table above. All compatible with Python 3.11.12.

**Design Note**: UAE-specific documents (Emirates ID, AECB credit reports) require custom generators because no mature free libraries exist for these formats. The custom generators ensure proper checksum validation and schema compliance.

---

### 16. Document Processing

**Decision**: Use mature, high-adoption libraries for document parsing, OCR, table extraction, and embeddings.

**Rationale**: The spec requires processing multiple document types (PDFs, images, Excel files). We need proven libraries with strong community adoption.

**Libraries (all with high adoption):**

| Component | Library | Version | GitHub Stars | PyPI Downloads | Python 3.11 |
|---|---|---|---|---|---|
| **PDF → Markdown/JSON** | `pymupdf4llm` | 1.28.0 | 1,951 | 116M total, 19.7M/month | ✓ |
| **OCR (scanned docs)** | `paddleocr` | 3.7.0 | 86K | 25.3M total, 2.8M/month | ✓ |
| **Table extraction** | `camelot-py` | 2.0.0 | 3,786 | ~840K/month | ✓ |
| **Embeddings** | `fastembed` | 0.8.0 | 3,085 | 13.3M total | ✓ |
| **Resume parsing** | `smartresume` | git main | 384 | N/A (git install) | ✓ |

**Version**: See table above. All compatible with Python 3.11.12.

---

## External Dependencies (Not Python Packages)

### Docker Infrastructure

All infrastructure services are managed via Docker Compose. The configuration file `docker-compose.yml` is located in the project root.

**Services included:**
- **PostgreSQL 17** - Primary relational database (port 5432)
- **Neo4j 2026.06.0** - Graph database for family relationships and document lineage (ports 7474, 7687)
- **Qdrant v1.18.3** - Vector database for document embeddings (ports 6333, 6334)
- **Langfuse v4 stack** (port 4000):
  - `langfuse-web` — Web UI (port 4000 → 3000)
  - `langfuse-worker` — Background worker (port 3030)
  - `langfuse-postgres` — Dedicated PostgreSQL 17 for Langfuse metadata (port 5433)
  - `langfuse-clickhouse` — ClickHouse 25.12 for observation data (ports 8123, 9000)
  - `langfuse-redis` — Redis 7 for cache and queue (port 6379)
  - `langfuse-minio` — MinIO for S3-compatible event/media storage (ports 9090, 9091)

**Host-Installed Services:**
- **Ollama** - Already installed on host system. Runs natively on port 11434. Docker containers connect via `host.docker.internal:11434`.

**Usage:**
```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop all services
docker compose down

# Stop and remove volumes (DESTRUCTIVE)
docker compose down -v
```

**Access Points:**
- Neo4j Browser: http://localhost:7474
- Qdrant Dashboard: http://localhost:6333/dashboard
- Langfuse Web UI: http://localhost:4000
- MinIO Console: http://localhost:9091

**Networking:**
- All containers communicate via `xd_backend` bridge network
- Application code (FastAPI, Streamlit) runs natively and connects to all services via `localhost`
- Langfuse uses a dedicated PostgreSQL instance (port 5433) to avoid conflicts with the main application database (port 5432)
- ClickHouse 25.12 is pinned to avoid breaking changes in ClickHouse 26.x
- All ports bind to 127.0.0.1 (localhost only) for security
