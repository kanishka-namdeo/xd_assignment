# Documentation Domain

## Purpose
Design specifications, architecture decisions, and durable project documentation.

## Ownership
- Primary: Project Owner
- Review Required: Updates require acknowledgment

## Local Contracts
- Design specs are immutable once approved — create new versions rather than editing
- Each spec follows the format: `YYYY-MM-DD-<topic>-design.md`

## Work Guidance
This folder contains:
- `superpowers/specs/` — Design specifications produced by the brainstorming workflow
- Each spec includes: executive summary, per-decision rationale, dependency analysis, installation commands, and future improvements

## Verification
None — documentation only.

## Child DOX Index
### `superpowers/specs/` - Design Specifications
Design specs produced by the brainstorming workflow. Each spec is a durable artifact.

| File | Topic |
|------|-------|
| `2026-07-25-tech-stack-design.md` | Technology stack decisions (LangGraph, Qdrant, Neo4j, Langfuse, Ollama, FastAPI, Streamlit, synthetic data generation) |
| `2026-07-25-document-processing-schema-design.md` | PostgreSQL schemas for six document types, cross-document validation, audit trail |
| `2026-07-25-fake-data-generation-design.md` | Synthetic data generation spec: per-document generators, cross-document consistency, schema compliance |
| `2026-07-25-applicant-user-flow-design.md` | Applicant user flow design: chat-only interaction, 7-phase hybrid flow (Phase 0-6), LangGraph state model, agent roles, Streamlit UI, error handling |
| `2026-07-25-agent-specification-design.md` | Agent architecture spec: 5 agents (orchestrator, extraction, validation, eligibility, decision), ReAct/Reflexion reasoning, deterministic gates, LangGraph state model |

### Setup Guides
Operational guides for infrastructure setup and configuration.

| File | Topic |
|------|-------|
| `LANGFUSE_SETUP.md` | Langfuse v4 self-hosted setup: architecture, secrets generation, initial configuration, integration, troubleshooting |
