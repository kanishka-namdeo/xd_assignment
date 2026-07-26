# UAE Social Support Application — Workflow Automation

<!-- TODO: Fill in project description (2–3 sentences). -->

---

## Prerequisites

<!-- TODO: List required software with versions and install links. -->

- Python 3.11.12
- Docker & Docker Compose
- 

---

## Quick Start

### 1. Clone and enter the project

```bash
git clone <repository-url>
cd xd_assignment
```

### 2. Create and activate the virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in required values
```

<!-- TODO: Document each required environment variable. -->

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `LLM_PROVIDER` | `ollama` or `streamlake` | Yes |
| `LANGFUSE_PUBLIC_KEY` | Langfuse observability key | No |
| `LANGFUSE_SECRET_KEY` | Langfuse observability secret | No |

### 5. Start infrastructure services

```bash
docker compose up -d
```

Services started:
- PostgreSQL
- Neo4j
- Qdrant
- Langfuse (optional)

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Generate test data (optional)

```bash
python scripts/generate_test_data.py
```

### 8. Start the application

```bash
# Terminal 1 — FastAPI backend
uvicorn src.main:app --reload
```

```bash
# Terminal 2 — Streamlit frontend
streamlit run ui/streamlit_app.py
```

Open `http://localhost:8501` in your browser.

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires Docker services running)
pytest tests/integration/

# All tests with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Architecture Overview

<!-- TODO: Insert a brief architecture summary or link to docs/solution-summary.md -->

See [Solution Summary](docs/solution-summary.md) for the full architecture diagram, tool justifications, and module breakdown.

---

## Project Structure

| Path | Purpose |
|------|---------|
| `src/api/` | FastAPI REST endpoints |
| `src/services/` | Business logic orchestration |
| `src/agents/` | LangGraph agent definitions |
| `src/domain/` | Pure business logic, parsers, scoring |
| `src/infrastructure/` | Database, LLM, vector DB, observability |
| `src/data_generation/` | Synthetic test data generators |
| `ui/` | Streamlit frontend |
| `tests/` | Unit, integration, and E2E tests |
| `evals/` | Agent evaluation framework |
| `alembic/` | Database migrations |
| `docs/` | Design specs and solution summary |
| `scripts/` | Utility scripts |
| `data/` | Generated test data (gitignored) |

---

## Configuration

<!-- TODO: Document key configuration options. -->

| Setting | Default | Description |
|---------|---------|-------------|
| `LOG_FORMAT` | `console` | `console` or `json` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `LLM_PROVIDER` | `ollama` | LLM backend to use |

---

## Troubleshooting

<!-- TODO: Add common issues and resolutions. -->

| Symptom | Cause | Resolution |
|---------|-------|-----------|
| | | |

---

*Last updated: YYYY-MM-DD*
