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
- **Python AI Agent Coding Practices**: All agents must follow the scalable Python coding practices documented in `.cursor/rules/python-ai-practices.mdc`. This Project Rule (`alwaysApply: true`) covers modern Python 3.11+, async patterns, LangGraph, FastAPI, Streamlit, Neo4j, PostgreSQL, Qdrant, Langfuse, Scikit-learn, pandas, openpyxl, mimesis, document processing (pymupdf4llm, paddleocr, camelot-py), Pillow, fastembed, ReportLab, reasoning frameworks (ReAct, Reflexion), testing strategies, de-slop code practices (YAGNI, function quality, proper DRY, code smells, readability-first, comment hygiene, Python-specific clean code), and anti-patterns. Based on 2025-2026 latest package versions and best practices.
- **Proactive Web Search Guidelines**: All agents must follow research-based web search guidelines documented in `.cursor/rules/web-search-guidelines.mdc`. This Project Rule (`alwaysApply: true`) covers when to search proactively based on temporal signals, domain staleness rates, confidence estimation, library/framework queries, and efficiency heuristics. Balances under-search and over-search failure modes. Mentions MCP servers (context7, browser tools) for specialized retrieval.
- **Python Virtual Environment**: Project uses Python 3.11.12 venv at `.venv/`. All Python work must use `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe` directly. System Python (`python`, `py`, `pip`) must not be used. See `.cursor/rules/python-venv.mdc` for full requirements.
- **Logging Practices**: All code must follow structured logging conventions using `structlog`. Use `structlog.get_logger(__name__)`, log events in snake_case, include `duration_ms` for timed operations, use `logger.exception()` in except blocks, and never log PII directly. See `.cursor/rules/logging-practices.mdc` for full requirements.

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

Main application package implementing the UAE Social Support Application system. Four-layer architecture: API routes → Services → Agents/Domain → Infrastructure. Contains LangGraph agents, FastAPI endpoints, database layer, ML models, document processing, and synthetic data generation module.

### `ui/` - Streamlit Frontend

Chat-based user interface for applicant interaction. Uses `st.navigation` with `app_pages/` directory (not `pages/` to avoid legacy conflicts). Implements 7-phase applicant flow: authentication, intake, document collection, processing, review, decision, enablement.

### `tests/` - Test Suite

Unit, integration, and end-to-end tests mirroring the `src/` structure. Unit tests mock dependencies, integration tests use real databases with mocked LLMs, e2e tests validate full application flow.

### `evals/` - Agent Evaluation

Evaluation framework for agent accuracy and quality. Distinct from unit tests: measures extraction accuracy, validation rule effectiveness, and eligibility scoring performance against ground truth.

### `alembic/` - Database Migrations

SQLAlchemy Alembic migrations for PostgreSQL schema evolution. Tracks changes to applicant, document, application, and extraction tables.

### `data/` - Test Data Storage

Runtime storage for synthetic test applicant data used in development and testing. Contains cross-document-consistent profiles for validating the application workflow.

### `scripts/` - Utility Scripts

Development and operational scripts for data generation and maintenance tasks. Not part of the main application.

### `docs/` - Documentation

Design specifications, architecture decisions, and durable project documentation. Contains brainstorming workflow outputs and technical design specs.

### `reference_docs/` - Reference Documentation

Assignment specifications and external reference materials.