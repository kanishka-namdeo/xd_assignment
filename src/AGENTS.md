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

### LangGraph Agent Structure
Each agent follows official LangGraph conventions:
- `graph.py`: StateGraph definition and compilation
- `nodes.py`: Node functions (pure logic)
- `routes.py`: Conditional edge routing (deterministic)
- `prompts.py`: System prompts (versionable, testable)
- `tools.py`: @tool decorators for agent capabilities

### Deterministic Gates
Validation gates are graph nodes, not separate modules. Use `add_conditional_edges` for routing. Keep gates deterministic (no LLM calls) for <5ms latency.

### Configuration
- Global config in `config.py` using pydantic-settings `BaseSettings`
- Environment variables via `.env` file
- LLM provider switching: `LLM_PROVIDER=ollama` or `LLM_PROVIDER=streamlake`
- Embeddings always local via Ollama

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
3. Implement node functions in `nodes.py`
4. Define routing logic in `routes.py`
5. Write system prompts in `prompts.py`
6. Create @tool wrappers in `tools.py`
7. Wire into orchestrator graph in `agents/orchestrator/graph.py`

### Adding a New API Endpoint
1. Create endpoint in `api/v1/` (applications.py, documents.py, eligibility.py, or chat.py)
2. Keep route thin: parse input, call service, return response
3. Implement business logic in corresponding `services/` file
4. Add Pydantic schemas in `domain/schemas/`

### Adding Database Models
1. Create SQLAlchemy ORM model in `infrastructure/db/models/`
2. Create repository in `infrastructure/db/repositories/`
3. Run Alembic migration: `alembic revision --autogenerate -m "description"`

## Verification
- Unit tests in `tests/unit/` mock all dependencies
- Integration tests in `tests/integration/` use real DB, mocked LLM
- Type checking: Pyright/mypy (required)
- Linting: Ruff (required)

## Child DOX Index
None - single-level structure. All subfolders are implementation details of the application.
