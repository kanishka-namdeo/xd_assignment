# ADR 0003: Four-Layer Architecture

## Status

Accepted

## Context

The UAE Social Support Application is a complex system with multiple concerns: HTTP request handling, business logic orchestration, LLM-driven agent execution, and infrastructure integration (databases, LLM providers, observability).

Without clear architectural boundaries, the codebase would become a tangled dependency graph where changes in one area ripple unpredictably through others.

## Decision

Enforce a strict four-layer architecture with unidirectional dependencies:

1. **API Layer** (`src/api/`) — Thin HTTP endpoints (5-12 lines). Parse input, call service, format output. No business logic.

2. **Services Layer** (`src/services/`) — Business logic orchestration. Own agent loop, session state, retry/fallback. Routes call services.

3. **Agents + Domain Layer** (`src/agents/`, `src/domain/`) — LangGraph agent definitions and pure domain logic. Services call agents.

4. **Infrastructure Layer** (`src/infrastructure/`) — External services (DB, LLM, vector DB, graph DB). Agents and services call infrastructure.

**Dependency rule:** Each layer imports only from layers below. No circular imports. Domain layer has no I/O.

## Alternatives Considered

### Feature-Based Layering

Organize by feature (auth, documents, eligibility) rather than technical layer. Works well for CRUD applications but conflicts with the agent-centric architecture where cross-cutting concerns (extraction, validation, decision) span multiple features.

### Hexagonal Architecture (Ports and Adapters)

More abstract. The four-layer approach is simpler to understand and enforce for a team that includes AI agents (via DOX framework).

### No Explicit Architecture

Let developers organize code as they see fit. Results in inconsistent patterns, tangled dependencies, and high onboarding cost.

## Consequences

### Positive

- Clear dependency direction prevents circular imports
- Each layer can be tested independently (mock layers below)
- New developers can understand the system by learning one layer at a time
- AI coding agents can be steered with layer-specific rules

### Negative

- Some boilerplate for simple operations (route → service → agent → repository)
- Requires discipline to keep routes thin

### Risks

- Over-engineering for simple CRUD operations (mitigated by allowing services to call infrastructure directly for non-agent operations)
