# LangGraph Configuration Audit & Fix Design

**Date**: 2026-07-27
**Status**: Draft
**Scope**: Identify and fix all LangGraph configuration issues (bugs, anti-patterns, missing features)

## Executive Summary

This spec documents a comprehensive audit of the LangGraph configuration across all 5 agents (orchestrator, extraction, validation, eligibility, decision). The audit identified 5 critical bugs, 7 anti-patterns, and 8 missing features. All issues will be fixed in a single implementation pass, categorized by severity.

**LangGraph Version**: 1.2.9 (latest, released 2026-07-10)
**Python Version**: 3.11.12

---

## Critical Bugs

Issues that can cause data loss, connection leaks, or state corruption in production.

### Bug 1: Validation Graph Connection Leak

**Location**: `src/agents/validation/graph.py:85`

**Problem**: Creates a new `AsyncPostgresSaver.from_conn_string()` on every `build_validation_graph()` call. Each call opens a new PostgreSQL connection. While `get_validation_graph()` caches the result, if the cache is cleared or the module reloads, connections leak.

**Fix**: Use the same singleton pattern as the orchestrator graph — share a module-level checkpointer instance via a common factory.

### Bug 2: Validation Graph Async/Sync Mismatch

**Location**: `src/agents/validation/graph.py:33-38`

**Problem**: `get_validation_graph()` is a sync function that builds the graph synchronously, but `AsyncPostgresSaver.from_conn_string()` is async. This blocks the event loop during checkpointer initialization.

**Fix**: Make `build_validation_graph()` async and use `await` for checkpointer initialization, matching the orchestrator pattern. Update all callers to `await` the graph build.

### Bug 3: Subgraph Error Propagation

**Location**: `src/agents/orchestrator/phases/processing.py:49,104`

**Problem**: Subgraphs are invoked with `await graph.ainvoke()` but errors are caught with broad `except Exception` that swallows the error and returns a fallback state. This masks real failures and makes debugging difficult.

**Fix**: Only catch specific expected exceptions (e.g., `ValueError`, `TimeoutError`). Let unexpected exceptions propagate. Add structured error logging with full context.

### Bug 4: State Mutation in Nodes

**Location**: Multiple nodes (e.g., `processing.py:70-81`)

**Problem**: Some nodes mutate the input state dict directly (e.g., `extracted_data[doc_type] = fields`) instead of returning a new dict. This can cause checkpoint corruption if LangGraph tries to serialize mutated state.

**Fix**: Always return new state updates from nodes, never mutate input state. Use dict unpacking or `copy()` to create new dicts.

### Bug 5: Missing State Reducers

**Location**: `src/agents/state.py:16-39`

**Problem**: Most state fields (e.g., `uploaded_documents`, `discrepancies`, `validation_errors`) are plain `list` types without reducers. When subgraphs return updates, LangGraph will replace the entire list instead of merging. This causes data loss.

**Fix**: Add appropriate reducers for list fields:
- `uploaded_documents`: `Annotated[list[dict[str, str]], operator.add]`
- `discrepancies`: `Annotated[list[dict[str, Any]], operator.add]`
- `validation_errors`: `Annotated[list[str], operator.add]`
- `extraction_results`: `Annotated[list[dict[str, Any]], operator.add]`
- `gate_errors`: `Annotated[list[str], operator.add]`
- `enablement_recommendations`: `Annotated[list[str], operator.add]`
- `_clarification_questions`: `Annotated[list[dict[str, Any]], operator.add]`

**Reducer strategy**: Use `operator.add` for all list fields to enable accumulation across subgraph invocations. This ensures that when extraction returns a list of documents and validation returns a list of discrepancies, both lists are preserved rather than one replacing the other. For dict fields like `extracted_data` and `validation_results`, use a custom merge reducer that performs deep merge rather than replacement.

---

## Anti-Patterns

Deprecated APIs, inconsistent patterns, and missing safety mechanisms.

### Anti-Pattern 1: Deprecated `set_conditional_entry_point`

**Location**: `src/agents/decision/graph.py:27`

**Problem**: `set_conditional_entry_point` is deprecated in LangGraph 1.x. The modern pattern is `add_conditional_edges(START, ...)`.

**Fix**: Replace with:
```python
workflow.add_conditional_edges(
    START,
    should_use_react,
    {"react": "decision_react", "deterministic": "decision_deterministic"},
)
```

### Anti-Pattern 2: Inconsistent Checkpointer Patterns

**Location**: All 5 graph files

**Problem**: Each graph uses a different checkpointer pattern:
- Orchestrator: async singleton with shared connection
- Validation: sync `from_conn_string()` per build
- Extraction: no checkpointer
- Decision: no checkpointer
- Eligibility: no checkpointer

**Fix**: Create a shared checkpointer factory in `src/agents/checkpointer.py` that all graphs use. Subgraphs that don't need persistence can explicitly pass `checkpointer=None`.

### Anti-Pattern 3: No `recursion_limit` Set

**Location**: All `graph.ainvoke()` calls

**Problem**: No `recursion_limit` is set on any graph invocation. LangGraph's default is 25, which may be too low for the validation Reflexion loop or too high for runaway loops.

**Fix**: Set explicit `recursion_limit` per graph:
- Orchestrator: 50 (7 phases + loops)
- Validation: 15 (Reflexion loop with bounded retries)
- Extraction: 10 (simple 2-node flow)
- Eligibility: 10 (3-node flow)
- Decision: 10 (2-node flow)

### Anti-Pattern 4: Extraction Subgraph Rebuilds Every Call

**Location**: `src/agents/extraction/graph.py:68-77`

**Problem**: `get_extraction_subgraph()` calls `build_extraction_subgraph()` on every invocation — no caching. This rebuilds and re-compiles the graph every time.

**Fix**: Add module-level caching like the validation graph pattern.

### Anti-Pattern 6: Eligibility Graph Same Issue

**Location**: `src/agents/eligibility/graph.py:47-50`

**Problem**: `get_eligibility_graph()` also rebuilds on every call — no caching.

**Fix**: Same caching pattern as extraction.

### Anti-Pattern 7: `create_agent` Import Path

**Location**: `src/agents/extraction/nodes.py`, `src/agents/eligibility/nodes.py`, `src/agents/decision/nodes.py`

**Problem**: The `.cursor/rules/langgraph.mdc` says to use `from langchain.agents import create_agent`, but the actual imports need verification.

**Fix**: Verify and align all ReAct agent creation to use the correct import path per the project's LangGraph rules.

---

## Missing Features

LangGraph capabilities that should be present for production readiness.

### Feature 1: No Streaming Support

**Location**: All `graph.ainvoke()` calls in `agent_runner.py`, `processing.py`, `decision.py`

**Problem**: All graph invocations use `ainvoke()` which blocks until completion. For a multi-phase workflow that can take minutes, the user gets no feedback.

**Fix**: Add `astream()` support for the orchestrator graph. Stream phase transitions and key events to the UI in real-time. Keep `ainvoke()` for subgraphs called within nodes.

### Feature 2: No Checkpoint TTL

**Location**: `src/agents/orchestrator/graph.py:38-53`

**Problem**: Checkpoints are persisted to PostgreSQL with no expiration. Over time, the `checkpoints` table grows unbounded.

**Fix**: Configure checkpoint TTL (e.g., 30 days) via `AsyncPostgresSaver` setup. Add cleanup job or document manual cleanup.

### Feature 3: No Error Classification

**Location**: All `except Exception` blocks in nodes

**Problem**: All exceptions are caught and handled identically. No distinction between transient errors (retry), business rule errors (escalate), LLM errors (bounded repair), and programming errors (fail fast).

**Fix**: Create an error classifier utility that categorizes exceptions and returns appropriate actions. Use it in all node error handlers.

### Feature 4: No State Size Management

**Location**: `src/agents/state.py`

**Problem**: The `ApplicantState` has 40 fields including large data structures. The LangGraph rule says "keep state under 50KB per checkpoint" but there's no enforcement.

**Fix**: Add state size validation before checkpointing. Move large data to external storage and store only references in state. Add logging for state size at each node transition.

### Feature 5: No Graceful Degradation

**Location**: `processing.py`, `decision.py`

**Problem**: When subgraphs fail, the code falls back to service-layer methods. But there's no circuit breaker — if a subgraph is consistently failing, every request waits for timeout.

**Fix**: Add a simple circuit breaker pattern: if a subgraph fails N times in M minutes, skip it and go directly to fallback. Log circuit breaker state transitions.

### Feature 6: No Health Check Endpoint

**Location**: API layer

**Problem**: No way to check if LangGraph graphs are healthy (checkpointer connected, graphs compile, dependencies available).

**Fix**: Add a `/health/langgraph` endpoint that verifies:
- PostgreSQL checkpointer connection is alive
- All 5 graphs compile without errors
- LLM client is reachable
- Returns graph compilation status and last successful invocation timestamp

### Feature 7: No Retry Logic for Transient Failures

**Location**: Subgraph invocations

**Problem**: When a subgraph invocation fails, the code immediately falls back. No retry for transient failures.

**Fix**: Add retry decorator with exponential backoff for transient errors (network timeouts, rate limits). Max 3 retries with 1s, 2s, 4s delays. Don't retry business rule errors.

### Feature 8: No Observability Metrics

**Location**: All graph invocations

**Problem**: Langfuse traces are present, but no metrics for:
- Graph invocation duration (p50, p95, p99)
- Node execution duration
- Error rates by node
- Checkpoint save/load latency
- State size over time

**Fix**: Add structured logging for these dimensions. Use the existing `duration_ms` pattern consistently across all nodes and subgraph invocations.

---

## Implementation Order

1. **Critical Bugs** (highest priority)
   - Fix state reducers (Bug 5)
   - Fix connection leak (Bug 1)
   - Fix async/sync mismatch (Bug 2)
   - Fix state mutation (Bug 4)
   - Fix error propagation (Bug 3)

2. **Anti-Patterns** (medium priority)
   - Create shared checkpointer factory (Anti-Pattern 2)
   - Add caching to extraction/eligibility graphs (Anti-Patterns 5, 6)
   - Fix decision graph double compilation (Anti-Pattern 4)
   - Replace deprecated API (Anti-Pattern 1)
   - Set recursion limits (Anti-Pattern 3)
   - Verify create_agent imports (Anti-Pattern 7)

3. **Missing Features** (lower priority but still required)
   - Add error classification (Feature 3)
   - Add retry logic (Feature 7)
   - Add streaming support (Feature 1)
   - Add checkpoint TTL (Feature 2)
   - Add state size management (Feature 4)
   - Add graceful degradation (Feature 5)
   - Add health check endpoint (Feature 6)
   - Add observability metrics (Feature 8)

---

## Testing Strategy

After each category of fixes:
1. Run existing unit tests: `.\.venv\Scripts\pytest.exe tests/unit/agents/`
2. Run integration tests: `.\.venv\Scripts\pytest.exe tests/integration/`
3. Manual E2E test: Login, upload documents, process, verify decision
4. Check Langfuse traces for correct phase transitions and timing
5. Verify PostgreSQL checkpoint table for correct state persistence

---

## Risk Notes

- **State reducer changes**: May break existing tests that expect list replacement behavior. Update test fixtures accordingly.
- **Checkpointer factory**: Requires careful migration to avoid breaking existing checkpoint data.
- **Streaming support**: May require UI changes to handle streamed events.
- **Error classification**: May change error handling behavior in edge cases. Test thoroughly.

---

## Gap Analysis

**Areas not covered**:
- LangGraph JS/TypeScript version (not applicable — this is Python-only)
- LangGraph Platform/Cloud (not using — self-hosted)
- Multi-tenant checkpoint isolation (not in scope for this audit)

**Assumptions**:
- PostgreSQL checkpointer is the only persistence backend (no SQLite, no in-memory)
- All agents use the same `ApplicantState` (no per-agent state types)
- Langfuse is the only observability backend
