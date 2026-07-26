# DOX framework

- DOX is highly performant [AGENTS.md](http://AGENTS.md) hierarchy installed here
- Agent must follow DOX instructions across any edits

## Core Contract

- [AGENTS.md](http://AGENTS.md) files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable [AGENTS.md](http://AGENTS.md) plus every parent [AGENTS.md](http://AGENTS.md) above it

## Read Before Editing

1. Read the root [AGENTS.md](http://AGENTS.md)
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every [AGENTS.md](http://AGENTS.md) found along each route
5. If a parent [AGENTS.md](http://AGENTS.md) lists a child [AGENTS.md](http://AGENTS.md) whose scope contains the path, read that child and continue from there
6. Use the nearest [AGENTS.md](http://AGENTS.md) as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning [AGENTS.md](http://AGENTS.md) when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- [AGENTS.md](http://AGENTS.md) creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root [AGENTS.md](http://AGENTS.md) is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child [AGENTS.md](http://AGENTS.md) files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be



## Child Doc Shape

- Create a child [AGENTS.md](http://AGENTS.md) when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:

- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index



## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist



## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why



## User Preferences

When the user requests a durable behavior change, record it here or in the relevant child [AGENTS.md](http://AGENTS.md)

### Pre-Planning Requirements

Before writing any implementation plan, agents MUST complete two steps:

1. **Codebase scan**: Launch parallel `generalPurpose` subagents, each covering a distinct area relevant to the task (e.g., architecture, data models, API layer, UI, tests). Each subagent returns a summary of relevant files, patterns, contracts, and dependencies. Do not skip this step or do it sequentially — parallelism is required for speed.
2. **Web search**: Run web searches for current best practices, latest library versions, API changes, and relevant patterns before planning. This is mandatory regardless of topic — do not skip based on staleness heuristics. Plans must be informed by current external knowledge, not just training data.

### Superpowers Workflow Behavior

When using superpowers workflows, agents MUST follow these web search rules:

**Mandatory web search (before each workflow's core output):**
- **brainstorming**: Search for current library capabilities, architectural patterns, and best practices before proposing 2-3 approaches. Knowledge of what's currently available is required to make informed design recommendations.
- **writing-plans**: Search for current APIs, library versions, testing patterns, and implementation best practices. Already covered by Pre-Planning Requirements above.
- **test-driven-development**: Search for current testing patterns and library APIs before writing tests. Pytest fixtures, async testing strategies, mocking patterns, and assertion libraries evolve — use current best practices.

**Reactive web search (when relevant to the task):**
- **systematic-debugging**: Search when encountering unfamiliar errors, library-specific behaviors, or version-specific issues. Not required for every debug session — use when stuck or when the error domain is unfamiliar.
- **receiving-code-review**: Search when evaluating code against current best practices or library recommendations. Use to validate whether review feedback aligns with current standards.

**No web search needed:**
- **executing-plans**, **subagent-driven-development**: Execution workflows — follow the existing plan.
- **Git workflows** (using-git-worktrees, finishing-a-development-branch, verification-before-completion): Stable patterns with no external dependency.
- **dispatching-parallel-agents**: Orchestration pattern, not domain-specific.
- **requesting-code-review**: Review request is process, not content.

### Project Rules (`.cursor/rules/*.mdc`)

All rules use `alwaysApply: true` and apply to every Agent session:

- **Agent Personality**: All agents must communicate according to the personality defined in `.cursor/rules/agent-personality.mdc`. This Project Rule uses `alwaysApply: true` and complements technical practices with a direct, task-focused, accuracy-oriented communication style. Prioritizes clarity over conversational polish, uses active voice, avoids filler phrases and jargon, and expresses uncertainty explicitly. Personality never overrides task-specific requirements or technical standards.
- **Python Core Conventions**: Modern Python 3.11.12 syntax, PEP 585/604 type system, and Pydantic v2 patterns. See `.cursor/rules/python-core.mdc` for type hints, unions, and validation conventions.
- **Python Async Patterns**: Structured concurrency with `asyncio.TaskGroup` for Python 3.11+. See `.cursor/rules/python-async.mdc` for async best practices.
- **Python Virtual Environment**: Project uses Python 3.11.12 venv at `.venv/`. All Python work must use `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe` directly. System Python (`python`, `py`, `pip`) must not be used. See `.cursor/rules/python-venv.mdc` for full requirements.
- **LangGraph Agent Patterns**: Agent orchestration, state management, checkpointing, and reasoning frameworks (ReAct, Reflexion). Use `create_agent` from `langchain.agents`. See `.cursor/rules/langgraph.mdc` for patterns.
- **FastAPI Patterns**: REST API layer, async/sync separation, dependency injection, database integration. See `.cursor/rules/fastapi.mdc` for conventions.
- **Streamlit Patterns**: Frontend caching, performance with `@st.fragment`, and navigation with `st.Page` API. Use `app_pages/` directory (not legacy `pages/`). See `.cursor/rules/streamlit.mdc` for patterns.
- **Neo4j Patterns**: Graph database queries, connection management, AI integration. See `.cursor/rules/neo4j.mdc` for patterns.
- **Qdrant Patterns**: Vector database architecture, ingestion, querying. See `.cursor/rules/qdrant.mdc` for patterns.
- **Langfuse Patterns**: v4 observability, instrumentation, tracing. See `.cursor/rules/langfuse.mdc` for integration patterns.
- **pandas Patterns**: Performance optimization with PyArrow backend, Copy-on-Write, memory management. See `.cursor/rules/pandas.mdc` for best practices.
- **Document Processing**: PDF, OCR, table extraction, image processing patterns. See `.cursor/rules/document-processing.mdc` for pymupdf4llm, paddleocr, camelot-py, ReportLab, Pillow patterns.
- **Testing Patterns**: pytest configuration, async testing, mocking strategies. See `.cursor/rules/testing.mdc` for testing conventions.
- **Logging Practices**: Structured logging with `structlog`, PII redaction, timing. Use `structlog.get_logger(__name__)`, log events in snake_case, include `duration_ms` for timed operations. See `.cursor/rules/logging-practices.mdc` for full requirements.
- **Proactive Web Search Guidelines**: Research-based web search guidelines for library docs, best practices, and version-specific APIs. See `.cursor/rules/web-search-guidelines.mdc` for when to search.
- **PostgreSQL Patterns**: Async connection management with asyncpg/psycopg, query optimization, transaction patterns. See `.cursor/rules/postgres.mdc` for conventions.

### Cursor Terminology Reference

| Term | Definition |
|------|------------|
| **Agent** | Cursor's AI assistant that completes tasks autonomously in Agent Mode |
| **Agent Mode** | Primary mode for file edits, terminal commands, iterating until task done |
| **Project Rules** | `.mdc` files in `.cursor/rules/` with YAML frontmatter (`alwaysApply`, `globs`, `description`) |
| **alwaysApply: true** | Rule applies to every Agent session; ignores `globs` and `description` |
| **Context Window** | Token limit for conversation; Rules are injected at start |
| **@-mention** | Syntax to reference files (`@filename.ts`) or rules explicitly in chat |
| **MCP Server** | Model Context Protocol server providing external tools (e.g., context7 for docs) |
| **Subagents** | Specialized agents with isolated context for parallel or context-heavy work |
| **Skills** | Dynamic capabilities in `SKILL.md` files, invoked via `/` commands |



## Child DOX Index

### `src/` - Application Source Code

Main application package implementing the UAE Social Support Application system. Four-layer architecture: API routes (`api/`) → Services (`services/`) → Agents/Domain (`agents/`, `domain/`) → Infrastructure (`infrastructure/`). Contains 5 LangGraph agents (orchestrator, extraction, validation, eligibility, decision), 4 deterministic gates, FastAPI REST endpoints, PostgreSQL/Neo4j/Qdrant data layer, document processing pipeline, ML eligibility model, and synthetic data generation module. Also includes `ml/` (ML models, stubs) and `utils/` (shared utilities).

### `ui/` - Streamlit Frontend

Chat-based user interface for applicant interaction. Uses `st.navigation` with `app_pages/` directory (not `pages/` to avoid legacy conflicts). Implements 7-phase applicant flow: authentication (Phase 0), intake, document collection, processing, review, decision, enablement (Phases 1-6). Components: decision cards, document status, phase tracker, enablement section, chat input with file upload.

### `tests/` - Test Suite

Unit, integration, and end-to-end tests mirroring the `src/` structure. ~241+ unit tests covering agents (174), gates (58), and domain (9). Integration tests: 4 populated, 3 stubs. E2E and system tests for full application flow validation. Root-level ad-hoc test scripts also present.

### `evals/` - Agent Evaluation

Evaluation framework for agent accuracy and quality. Distinct from unit tests: measures extraction accuracy, validation rule effectiveness, and eligibility scoring performance against ground truth. Currently placeholder — 3 evaluation test files are stubs awaiting implementation.

### `alembic/` - Database Migrations

SQLAlchemy Alembic migrations for PostgreSQL schema evolution. 2 migrations: initial schema (16 tables) and state_snapshot column addition. Tracks changes to applicant, document, application, and extraction tables.

### `data/` - Test Data Storage

Runtime storage for synthetic test applicant data used in development and testing. Populated by running `scripts/generate_test_data.py`. Contains cross-document-consistent profiles for 3 applicant scenarios (approved, manual_review, soft_decline).

### `scripts/` - Utility Scripts

Development and operational scripts for data generation and maintenance tasks. Contains `generate_test_data.py` (279 lines) for generating 3 synthetic test applicant profiles with cross-document consistency.

### `docs/` - Documentation

Design specifications, architecture decisions, and durable project documentation. Contains 6 design specs (tech stack, document processing schema, fake data generation, applicant user flow, agent specification, LangGraph implementation patterns) and Langfuse v4 setup guide.

### `reference_docs/` - Reference Documentation

Assignment specifications and external reference materials. Contains the AI Case Study specification with problem statement, solution scope, technology stack recommendations, and evaluation criteria.