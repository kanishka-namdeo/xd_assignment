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

|| File | Topic |
||------|-------|
|| `2026-07-25-tech-stack-design.md` | Technology stack decisions (LangGraph, Qdrant, Neo4j, Langfuse, Ollama, FastAPI, Streamlit, synthetic data generation) |
|| `2026-07-25-document-processing-schema-design.md` | PostgreSQL schemas for six document types, cross-document validation, audit trail |
|| `2026-07-25-fake-data-generation-design.md` | Synthetic data generation spec: per-document generators, cross-document consistency, schema compliance |
|| `2026-07-25-applicant-user-flow-design.md` | Applicant user flow design: chat-only interaction, 7-phase hybrid flow (Phase 0-6), LangGraph state model, agent roles, Streamlit UI, error handling |
|| `2026-07-25-agent-specification-design.md` | Agent architecture spec: 5 agents (orchestrator, extraction, validation, eligibility, decision), ReAct/Reflexion reasoning, deterministic gates, LangGraph state model |
|| `2026-07-25-langgraph-implementation-patterns-design.md` | LangGraph v1 implementation patterns: subgraph decomposition, state isolation, interrupt() wiring, Reflexion topology, create_agent migration, middleware strategy |
|| `2026-07-27-agent-tools-evaluation-design.md` | Agent tools evaluation framework: four-layer pytest suite (audit, golden dataset, schema contracts, live integration) for validating 19 agent tools |
|| `2026-07-27-langgraph-configuration-audit-design.md` | LangGraph configuration audit: 15 issues (state reducers, checkpointer factory, state mutation, error classification, graph caching, deprecated API, recursion limits, create_agent imports, retry logic, streaming, checkpoint TTL, state size management, graceful degradation, health check, observability) |
|| `2026-07-27-ui-ux-polish-design.md` | UI/UX polish improvements: high contrast mode, text size accessibility, help panel, phase guidance, document status cards |
|| `2026-07-27-demo-readiness-fixes-design.md` | Demo readiness bug fixes: 8 bugs/architecture violations fixes + verification plan for full 7-phase flow |
|| `2026-07-28-api-only-agent-skill-design.md` | API-only agent skill: Cursor Agent Skill for full FastAPI backend interaction without Streamlit UI, automated testing, demo/smoke testing, data generation |
|| `2026-07-27-architecture-documentation-suite-design.md` | Architecture documentation suite: 10-section architecture doc, security-privacy doc, API design catalog, data dictionary |
|| `2026-07-28-repo-presentation-enhancement-design.md` | Repository presentation enhancement: README, SOLUTION_SUMMARY, project structure cleanup |

13 design specs total.

### `superpowers/plans/` - Implementation Plans
Active implementation plans tracking ongoing work items.

|| File | Topic |
||------|-------|
|| `2026-07-27-agent-tools-evaluation.md` | Agent tools evaluation implementation plan |
|| `2026-07-27-architecture-documentation-suite.md` | Architecture documentation suite implementation |
|| `2026-07-27-demo-readiness-fixes.md` | Demo readiness bug fixes and improvements |
|| `2026-07-27-langgraph-configuration-audit.md` | LangGraph configuration audit implementation |
|| `2026-07-28-api-only-agent-skill.md` | API-only agent skill implementation: Cursor Agent Skill and CLI script for full FastAPI backend interaction |
|| `2026-07-27-ui-ux-polish.md` | UI/UX polish implementation: high contrast mode, text size accessibility, help panel, phase guidance |
|| `2026-07-28-repo-presentation-enhancement.md` | Repository presentation enhancement: README, SOLUTION_SUMMARY, project structure |

7 active plans.

### Solution Summary
Living design artifact maintained by agents throughout the project. Moved to repo root as `SOLUTION_SUMMARY.md` per case study submission requirements.

|| File | Topic |
||------|-------|
|| `SOLUTION_SUMMARY.md` (at repo root) | High-level architecture diagram, tool choice justification, data-type tool justification, scikit-learn algorithm justification, modular workflow breakdown, future improvements and integration considerations. Capped at 10 pages. Moved to root per case study submission requirements. |

### Architecture Documentation
Comprehensive documentation suite for the project.

|| File | Topic |
||------|-------|
|| `architecture.md` | 10-section architecture document covering all layers and components |
|| `security-privacy.md` | Security and privacy practices |
|| `api-design.md` | API design principles and endpoint catalog |
|| `data-dictionary.md` | PostgreSQL schema documentation |

### Setup Guides
Operational guides for infrastructure setup and configuration.

|| File | Topic |
||------|-------|
|| `LANGFUSE_SETUP.md` | Langfuse v4 self-hosted setup: architecture, secrets generation, initial configuration, integration, troubleshooting |

### Testing Trackers
E2E testing artifacts produced during live testing sessions.

|| File | Topic |
||------|-------|
|| `live-testing-tracker.md` | Comprehensive E2E testing tracker: 9/9 tests passing, 6 bugs fixed, all phases validated with real LLM requests |
|| `e2e-testing-tracker.md` | Detailed E2E test results with bug analysis, logging enhancements, and remaining issues |

### Architecture Decision Records
Architecture decision records (ADRs) documenting key technical decisions.

|| File | Topic |
||------|-------|
|| `README.md` | ADR index and methodology |
|| `0001-langgraph-orchestration.md` | Use LangGraph for agent orchestration |
|| `0002-polyglot-persistence.md` | Polyglot persistence with PostgreSQL, Neo4j, Qdrant |
|| `0003-four-layer-architecture.md` | Four-layer architecture (API, Services, Agents/Domain, Infrastructure) |
|| `0004-local-llm-fallback.md` | Local LLM fallback with Ollama |
|| `0005-structured-logging-pii.md` | Structured logging with PII redaction |
|| `0006-dox-framework.md` | DOX framework for project documentation |

### Images
UI screenshots and architecture diagrams used in documentation. Contains ~20 PNG files capturing phase-by-phase UI states, error states, and the high-level architecture diagram.
