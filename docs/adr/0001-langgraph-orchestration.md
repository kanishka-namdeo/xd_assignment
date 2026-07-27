# ADR 0001: Use LangGraph for Agent Orchestration

## Status

Accepted

## Context

The UAE Social Support Application requires a 7-phase applicant flow (authentication, intake, document collection, processing, review, decision, enablement) with persistent state between phases, interrupt points for human input, and subgraph composition for extraction, validation, eligibility, and decision agents.

The system must support:
- Cyclic execution (reflexion loops in validation agent)
- Checkpointing for crash recovery and session persistence
- Human-in-the-loop interrupts for clarification questions
- Subgraph composition (extraction, validation, eligibility, decision as subgraphs of orchestrator)

## Decision

Use LangGraph as the agent orchestration framework.

LangGraph provides:
- Native support for cyclic graphs (required for Reflexion loops)
- `PostgresSaver` checkpointer for persistent state between phases
- `interrupt()` for human-in-the-loop clarification
- Subgraph composition (each agent is a subgraph of the orchestrator)
- Async execution compatible with FastAPI

## Alternatives Considered

### Plain Python State Machines

Would require implementing checkpointing, recovery, and interrupt logic from scratch. Duplicates infrastructure that LangGraph provides natively.

### CrewAI

Focused on multi-agent collaboration patterns, not state machine orchestration. Does not provide the cyclic graph support needed for Reflexion loops.

### Custom Async Framework

Building a custom orchestration layer would be a significant undertaking with no competitive advantage over LangGraph's battle-tested implementation.

## Consequences

### Positive
- Native checkpointing eliminates custom session management
- Cyclic graph support enables Reflexion loops naturally
- Subgraph composition keeps agents decoupled
- Active community and regular updates

### Negative
- LangGraph-specific abstractions (StateGraph, channels) create a learning curve
- Checkpointer adds a PostgreSQL dependency for all agent execution
- Debugging complex graph execution requires Langfuse integration

### Risks
- LangGraph API evolution may require migration (mitigated by wrapping graph construction in `graph.py` modules)
