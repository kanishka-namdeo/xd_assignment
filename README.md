# UAE Social Support Application — Workflow Automation

An AI-driven workflow automation system for UAE social support benefit applications. The system guides applicants through a 7-phase chat-based flow (authentication, intake, document collection, processing, review, decision, enablement) using LangGraph agents, validates documents with cross-document consistency checks, and produces eligibility decisions (approve / manual review / soft decline) backed by an ML model and deterministic rule gates.

---

## Prerequisites

- **Python 3.11.12** — [python.org](https://www.python.org/downloads/)
- **Docker & Docker Compose** — [docker.com](https://www.docker.com/products/docker-desktop/)
- **Ollama** (optional, for local LLM) — [ollama.com](https://ollama.com)

---

## Quick Start

### 1. Clone and enter the project

```bash
git clone <repository-url>
cd xd_assignment
```

### 2. Create and activate the virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Copy the example file and edit
copy .env.example .env     # Windows
cp .env.example .env       # Linux/macOS
```

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string for application data | Yes | `postgresql+asyncpg://postgres:change_me_to_strong_password@localhost:5432/social_support` |
| `POSTGRES_USER` | PostgreSQL admin user | Yes | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL admin password | Yes | `change_me_to_strong_password` |
| `POSTGRES_DB` | Application database name | Yes | `social_support` |
| `NEO4J_AUTH` | Neo4j credentials (`username/password`) | Yes | `neo4j/change_me_to_strong_password` |
| `LLM_PROVIDER` | LLM backend: `ollama` (local) or `streamlake` (cloud) | Yes | `streamlake` |
| `OLLAMA_BASE_URL` | Local Ollama endpoint | No (ollama only) | `http://localhost:11434/v1` |
| `OLLAMA_API_KEY` | Ollama API key (fixed value) | No (ollama only) | `ollama` |
| `OLLAMA_MODEL` | Ollama model name | No (ollama only) | `qwen3.5:14b` |
| `STREAMLAKE_BASE_URL` | StreamLake API gateway URL | No (streamlake only) | `https://vanchin.streamlake.ai/api/gateway/coding/v1` |
| `STREAMLAKE_API_KEY` | StreamLake API key from [streamlake.ai](https://streamlake.ai) | No (streamlake only) | — |
| `STREAMLAKE_MODEL` | StreamLake model name | No (streamlake only) | `kat-coder-pro-v2.5` |
| `EMBEDDING_PROVIDER` | Embedding backend (always `ollama`) | Yes | `ollama` |
| `EMBEDDING_MODEL` | Ollama embedding model | Yes | `nomic-embed-text:v1.5` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse SDK public key (from Langfuse UI) | No | — |
| `LANGFUSE_SECRET_KEY` | Langfuse SDK secret key | No | — |
| `LANGFUSE_HOST` | Langfuse UI URL | No | `http://localhost:4000` |
| `LOG_FORMAT` | Log output format: `console` or `json` | No | `console` |
| `LOG_LEVEL` | Logging verbosity | No | `INFO` |

### 5. Start infrastructure services

```bash
docker compose up -d
```

Services started:
- **PostgreSQL** (port 5432) — Application data
- **Neo4j** (ports 7474 HTTP, 7687 Bolt) — Document lineage and family graphs
- **Qdrant** (ports 6333 REST, 6334 gRPC) — Vector embeddings
- **Langfuse** (port 4000) — LLM observability UI (optional)

### 6. Run database migrations

```bash
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 7. Generate test data (optional)

```bash
.\.venv\Scripts\python.exe scripts/generate_test_data.py
```

### 8. Start the application

```powershell
# Terminal 1 — FastAPI backend
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend
.\.venv\Scripts\streamlit.exe run ui/streamlit_app.py --server.port 8501
```

Open `http://localhost:8501` in your browser.

---

## Running Tests

```bash
# Unit tests only (~241 tests)
.\.venv\Scripts\pytest.exe tests/unit/

# Integration tests (requires Docker services running)
.\.venv\Scripts\pytest.exe tests/integration/

# All tests with coverage report
.\.venv\Scripts\pytest.exe tests/ --cov=src --cov-report=html

# Evaluation suite — four layers:
#   Layer 1: Tool audit (coverage gaps)
#   Layer 2: Golden dataset (real documents vs ground truth)
#   Layer 3: Schema contracts + error handling
#   Layer 4: Live integration (requires infrastructure + LLM)
.\.venv\Scripts\pytest.exe evals/ -v --ignore=evals/integration/

# Live integration tests only (requires running infrastructure)
.\.venv\Scripts\pytest.exe tests/integration/test_live_integration.py -v -m live
```

---

## Architecture Overview

The application follows a strict four-layer architecture:

```
UI (Streamlit) → API (FastAPI) → Services → Agents + Domain → Infrastructure
```

| Layer | Responsibility | Key Technologies |
|-------|---------------|-----------------|
| Presentation | Chat-based applicant UI with file upload | Streamlit 1.60.0 |
| API | REST endpoints, request routing, dependency injection | FastAPI 0.140.0 |
| Services | Business logic orchestration, agent coordination, retry/fallback | Python, LangGraph 1.2.9 |
| Agents | LLM-driven extraction, validation, eligibility, decision | LangGraph, Ollama / StreamLake |
| Domain | Pure business logic: parsing, scoring, comparison, schemas | Python, Pydantic 2.13.4 |
| Infrastructure | Persistence, embeddings, graph, observability | PostgreSQL, Neo4j 6.2.0, Qdrant 1.18.0, Langfuse 4.14.1 |

**5 LangGraph agents** coordinate the workflow:
- **Orchestrator** — 7-phase state machine routing applicants through the pipeline
- **Extraction** — ReAct agent with Gate 1 (document integrity) for structured field extraction
- **Validation** — Reflexion loop with Gate 2 (completeness) for cross-document consistency
- **Eligibility** — ML scoring with Gate 3 (hard rules) for eligibility prediction
- **Decision** — Synthesis agent producing final outcome with explanation and enablement package

See [Solution Summary](docs/solution-summary.md) for the full architecture diagram, tool justifications, and module breakdown.

---

## Project Structure

| Path | Purpose |
|------|---------|
| `src/api/` | FastAPI REST endpoints (auth, applications, documents, eligibility, chat) |
| `src/services/` | Business logic orchestration (chat, application, document, extraction, validation, eligibility, decision services) |
| `src/agents/` | LangGraph agent definitions (orchestrator, extraction, validation, eligibility, decision) and deterministic gates |
| `src/domain/` | Pure business logic: document parsers, scoring, cross-document comparison, schemas, templates, constants |
| `src/infrastructure/` | Database (PostgreSQL, Neo4j, Qdrant), LLM, document processing, observability, vector storage |
| `src/data_generation/` | Synthetic test data generators with cross-document consistency |
| `src/ml/` | ML eligibility model and feature engineering |
| `ui/` | Streamlit frontend (chat UI, decision cards, phase tracker, document status) |
| `tests/` | Unit, integration, and E2E tests (~241+ unit tests) |
| `evals/` | Four-layer agent evaluation framework (audit, golden dataset, schema contracts, live integration) — 50+ tests validating 19 agent tools |
| `alembic/` | SQLAlchemy Alembic migrations (16-table schema) |
| `docs/` | Design specs, solution summary, Langfuse setup guide, E2E testing trackers |
| `scripts/` | Utility scripts (test data generation) |
| `data/` | Generated test data (gitignored) |
| `reference_docs/` | Assignment specification and evaluation criteria |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `LOG_FORMAT` | `console` | `console` for development (colored), `json` for production |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LLM_PROVIDER` | `ollama` | LLM backend: `ollama` (local, no API key) or `streamlake` (cloud) |
| `EMBEDDING_PROVIDER` | `ollama` | Embeddings always run locally via Ollama |

---

## Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|-----------|
| `DATABASE_URL` connection refused | PostgreSQL container not running | `docker compose up -d postgres` and verify with `docker compose ps` |
| `Ollama model not found` | Model not pulled locally | `ollama pull qwen3.5:14b` and `ollama pull nomic-embed-text` |
| Langfuse UI not loading | Langfuse containers not started or keys missing | Run `docker compose up -d` and obtain keys from `http://localhost:4000` after first login |
| `Port 8000 already in use` | Another process holding the backend port | Kill the process: `$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess; if ($pid) { Stop-Process -Id $pid -Force }` |
| `Port 8501 already in use` | Another Streamlit instance running | Kill the process: `$pid = (Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue).OwningProcess; if ($pid) { Stop-Process -Id $pid -Force }` |
| Migration `Target database is not up to date` | Alembic version mismatch | Run `.\.venv\Scripts\python.exe -m alembic upgrade head` |
| `ModuleNotFoundError` | Virtual environment not activated | Activate `.venv` and reinstall: `pip install -r requirements.txt` |
| Documents fail Gate 1 (integrity) | File format unsupported or corrupted | Ensure uploads are valid PDF, PNG, JPG, DOCX, or XLSX; check file hash |
| Agent returns empty extraction | LLM provider unreachable or model not loaded | Verify `LLM_PROVIDER` setting and that Ollama is serving (`curl http://localhost:11434/api/tags`) |

---

*Last updated: 2026-07-27*
