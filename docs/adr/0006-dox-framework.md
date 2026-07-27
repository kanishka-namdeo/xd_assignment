# ADR 0006: DOX Framework for AI Agent Steering

## Status

Accepted

## Context

This project is developed with significant AI coding agent assistance (Cursor, Claude Code). Without explicit steering, AI agents make inconsistent architectural decisions, introduce circular imports, and violate established patterns.

Traditional documentation (README, architecture docs) is read by humans but not consistently consulted by AI agents during coding sessions.

## Decision

Implement the DOX (Documentation-Oriented X) framework:

- `AGENTS.md` files at strategic boundaries (root, src/, ui/, tests/, etc.)
- Each file contains binding work contracts for its subtree
- Nearest file to code takes precedence for local work details
- Parent docs control repo-wide rules; no child doc may weaken DOX

The root `AGENTS.md` contains:

- Four-layer architecture contract
- File size and decomposition guardrails
- Tool thinness rules
- Service delegation rules
- LangGraph agent structure conventions
- User preferences (solution summary, README, pre-planning requirements)

## Alternatives Considered

### CLAUDE.md Only

Single file at root. Loses the hierarchical precedence model and local boundary contracts.

### No Agent Steering

AI agents make inconsistent decisions, introduce technical debt, and violate architecture.

### Pre-commit Hooks Only

Catches violations after the fact rather than preventing them.

## Consequences

### Positive

- AI agents consult rules before every edit
- Architecture violations prevented at the source
- Hierarchical model allows local customization
- Living documentation evolves with the codebase

### Negative

- Requires maintaining AGENTS.md files alongside code changes
- AI agents may over-constrain themselves

### Risks

- Conflicting rules between parent and child docs (mitigated by "closer doc controls, but no child may weaken DOX")
