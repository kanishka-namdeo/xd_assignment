# UAE Social Support Application — Workflow Automation

An AI-driven workflow automation system for UAE social support benefit applications. The system guides applicants through a 7-phase chat-based flow (authentication, intake, document collection, processing, review, decision, enablement) using LangGraph agents, validates documents with cross-document consistency checks, and produces eligibility decisions (approve / manual review / soft decline) backed by an ML model and deterministic rule gates.

---

## Evaluation Criterion Mapping

This project addresses the AI Case Study requirements for Social Support Application Workflow Automation. Below is where to find evidence for each evaluation criterion:

| # | Evaluation Criterion | Where to Find Evidence |
|---|----------------------|------------------------|
| 1 | **Functionality** — addresses all core requirements | [SOLUTION_SUMMARY.md](SOLUTION_SUMMARY.md) (architecture diagram, data flow), `src/agents/` (5 agents), `src/infrastructure/document_processing/` (multimodal processing), `src/ml/` (ML eligibility) |
| 2 | **Code Quality** — clean, modular, documented | `src/` (four-layer architecture), `tests/` (241+ unit tests), `docs/adr/` (6 architecture decision records), [AGENTS.md](AGENTS.md) (DOX framework), `docs/architecture.md` (10-section architecture doc) |
| 3 | **Solution Design** — scalable architecture, AI/ML principles | [SOLUTION_SUMMARY.md](SOLUTION_SUMMARY.md) (tool justification, modular breakdown), `docs/architecture.md` (data flow, state persistence), `docs/adr/` (design decisions), `src/ml/feature_engineering.py` (ML pipeline) |
| 4 | **Integration** — effective component integration, APIs, data pipelines | `src/api/v1/` (FastAPI endpoints), `src/infrastructure/db/` (PostgreSQL), `src/infrastructure/graph/` (Neo4j), `src/infrastructure/vector/` (Qdrant), `src/infrastructure/observability/` (Langfuse tracing) |
| 5 | **Demo UI** — user-friendly | `ui/` (Streamlit chat UI), `docs/images/ui-*.png` (screenshots), [Demo Walkthrough](#demo-walkthrough) section below |
| 6 | **Problem-Solving** — challenges addressed | [Challenges & Solutions](#challenges--solutions) section below |
| 7 | **Communication** — clear, thorough documentation | [README.md](README.md), [SOLUTION_SUMMARY.md](SOLUTION_SUMMARY.md), `docs/architecture.md`, `docs/adr/` (6 ADRs), `docs/superpowers/specs/` (12 design specs), [AGENTS.md](AGENTS.md) (DOX framework) |

---

## Architecture Overview

![Architecture Diagram](docs/images/architecture.png)

The system follows a strict four-layer architecture with unidirectional dependencies:

```
UI (Streamlit) → API (FastAPI) → Services → Agents + Domain → Infrastructure
```

### Key Highlights

**5 LangGraph agents** coordinate the workflow:
- **Orchestrator** — 7-phase StateGraph routing applicants through the pipeline
- **Extraction** — ReAct agent with Gate 1 (document integrity) for structured field extraction
- **Validation** — Reflexion loop with Gate 2 (completeness) for cross-document consistency
- **Eligibility** — ML scoring with Gate 3 (hard rules) for eligibility prediction
- **Decision** — Synthesis agent producing final outcome with explanation and enablement package

**4 deterministic gates** for <5ms validation:
- Gate 1: Document integrity / tamper detection
- Gate 2: Document completeness per support category
- Gate 3: Hard eligibility rules (residency, income, identity)
- Retry: Configurable retry with exponential backoff

**Multimodal processing** for 6 document types:
- PDF (pymupdf4llm), Images (PaddleOCR), Tables (camelot-py), DOCX (python-docx), XLSX (openpyxl)

**ML eligibility pipeline**: Scikit-learn with demographic + financial feature engineering

**Observability**: Langfuse v4 traces every LLM call and agent transition; structlog with PII redaction

---

## Demo Walkthrough

Follow these steps to reproduce the full 7-phase flow in <5 minutes:

### Prerequisites

- Docker & Docker Compose
- Python 3.11.12
- Ollama (optional, for local LLM)

### Steps

1. **Start infrastructure services:**
   ```bash
   docker compose up -d
   ```
   Services: PostgreSQL (5432), Neo4j (7474, 7687), Qdrant (6333), Langfuse (4000)

2. **Run database migrations:**
   ```bash
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

3. **Generate test data:**
   ```bash
   .\.venv\Scripts\python.exe scripts/generate_test_data.py
   ```

4. **Start the FastAPI backend:**
   ```bash
   .\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000
   ```

5. **Start the Streamlit frontend:**
   ```bash
   .\.venv\Scripts\streamlit.exe run ui/streamlit_app.py --server.port 8501
   ```

6. **Open the application:**
   Navigate to `http://localhost:8501` in your browser.

7. **Login with a test Emirates ID:**
   Enter a test Emirates ID number (e.g., `784-1990-1234567-8`).

8. **Complete the intake phase:**
   The orchestrator agent will collect 13 applicant fields (name, DOB, marital status, children, residency, employment, salary, etc.) via chat.

9. **Upload documents:**
   Upload documents from the generated test data:
   ```
   data/test_applicants/divorced_employed_good_credit/
   ```
   Files: `emirates_id_front.png`, `emirates_id_back.png`, `bank_statement.pdf`, `credit_report.pdf`, `application_form.png`

10. **Review the decision:**
    After processing, review the decision card with approval outcome, explanation, and enablement recommendations.

### Expected Outcome

For the `divorced_employed_good_credit` profile: **Approved** with enablement recommendations.

---

## Challenges & Solutions

During development, several significant challenges were addressed:

### Challenge 1: State Management Across 7 Asynchronous Phases

**Problem:** The applicant flow spans 7 phases with asynchronous document uploads, LLM calls, and human-in-the-loop clarification. State must persist between phases and survive server restarts.

**Solution:** LangGraph `PostgresSaver` checkpointer with `state_snapshot` JSONB column. The checkpointer persists LangGraph's internal checkpoint binary, while `state_snapshot` stores the deserialized, application-level state for inspection and recovery. This dual approach enables both LangGraph's native checkpointing and human-readable state recovery.

### Challenge 2: PII Egress to Third-Party LLM APIs

**Problem:** Government social support data contains sensitive PII (Emirates ID numbers, names, account numbers) that cannot be sent to external APIs.

**Solution:** Local-first Ollama with StreamLake fallback. The `LLM_PROVIDER` environment variable switches between local Ollama (no PII egress) and cloud StreamLake (Azure OpenAI-compatible). Additionally, structlog's PII redaction processor automatically masks identity numbers, names, and account numbers before log write.

### Challenge 3: Cross-Document Consistency Validation

**Problem:** Applicants submit 6 document types with overlapping information (identity, income, address). Discrepancies may be OCR errors or real fraud indicators.

**Solution:** Domain comparison functions (`domain/cross_document.py`) with discrepancy classification (`domain/discrepancy_classifier.py`). The validation agent runs a Reflexion loop: attempt extraction → evaluate consistency → critique discrepancies → clarify with applicant (if low confidence) → finalize. Gate 2 (completeness) runs after finalization.

### Challenge 4: Agent Coordination Without Tight Coupling

**Problem:** 5 agents must coordinate through the orchestrator without direct imports or circular dependencies.

**Solution:** Four-layer architecture with strict dependency direction (API → Services → Agents → Infrastructure). Agents obtain services via dependency injection (`Depends` in FastAPI, constructor injection in services), not direct imports. The orchestrator invokes subgraphs through service methods, maintaining loose coupling.

### Challenge 5: Debugging ReAct/Reflexion Loops

**Problem:** ReAct and Reflexion agents iterate 3–5 times per invocation. Debugging requires visibility into each LLM call, tool invocation, and node transition.

**Solution:** Langfuse v4 self-hosted tracing with trace-level visibility. Every LLM call is traced with inputs, outputs, token counts, and latency. Agent node transitions are logged as spans. This enables post-hoc analysis of agent reasoning and identification of failure points in the loop.

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
.\.venv\Scripts\pytest.exe evals/ -v

# Live integration tests only (requires running infrastructure)
.\.venv\Scripts\pytest.exe tests/integration/test_live_integration.py -v -m live
```

---

## Project Structure

| Path | Purpose |
|------|---------|
| `src/api/` | FastAPI REST endpoints (auth, applications, documents, eligibility, chat) |
| `src/services/` | Business logic orchestration (chat, application, document, extraction, validation, eligibility, decision, extraction_pipeline, agent_runner services) |
| `src/agents/` | LangGraph agent definitions (orchestrator, extraction, validation, eligibility, decision) and deterministic gates |
| `src/domain/` | Pure business logic: document parsers, scoring, cross-document comparison, schemas, templates, constants |
| `src/infrastructure/` | Database (PostgreSQL, Neo4j, Qdrant), LLM, document processing, observability, vector storage |
| `src/data_generation/` | Synthetic test data generators with cross-document consistency (includes CLI entry point) |
| `src/ml/` | ML eligibility model and feature engineering |
| `ui/` | Streamlit frontend (chat UI, decision cards, phase tracker, document status, phase guidance, accessibility controls, Help panel) |
| `tests/` | Unit, integration, and E2E tests (~241+ unit tests, plus service and utils tests) |
| `evals/` | Four-layer agent evaluation framework (audit, golden dataset, schema contracts, live integration) — 50+ tests validating 19 agent tools |
| `alembic/` | SQLAlchemy Alembic migrations (16-table schema) |
| `docs/` | Design specs (12), solution summary, architecture decision records (6 ADRs), Langfuse setup guide, E2E testing trackers |
| `scripts/` | Utility scripts (28 scripts: data generation, E2E testing, database maintenance, demo/smoke, API testing, streaming, enablement debugging, MCP/credential management) |
| `data/` | Generated test data (gitignored) — 7 profiles (3 canonical golden + 4 additional accounts) |
| `reference_docs/` | Assignment specification and evaluation criteria |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `LOG_FORMAT` | `console` | `console` for development (colored), `json` for production |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LLM_PROVIDER` | `streamlake` | LLM backend: `ollama` (local, no API key) or `streamlake` (cloud) |
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
