# LangGraph Implementation Patterns Design

**Date**: 2026-07-25  
**Status**: Draft  
**Python Version**: 3.11.12 (venv at `.venv/`)  
**Related Specs**: 
- `2026-07-25-agent-specification-design.md` (agent responsibilities and tools)
- `2026-07-25-applicant-user-flow-design.md` (7-phase flow)
- `2026-07-25-tech-stack-design.md` (LangGraph v1.2.9)

---

## Executive Summary

This specification defines the concrete LangGraph v1 implementation patterns for the five agents described in `2026-07-25-agent-specification-design.md`. The existing agent spec defines *what* each agent does (responsibilities, tools, reasoning frameworks). This spec defines *how* to implement them using LangGraph v1 patterns.

**Key decisions**:
1. **Subgraph decomposition**: Each agent is a compiled `StateGraph` subgraph. The parent orchestrator graph coordinates phase transitions.
2. **State isolation**: Each agent has its own `TypedDict` state. Private keys (agent-internal reasoning) never leak to the parent. Explicit state transformers at boundaries.
3. **`interrupt()` for chat interaction**: The graph pauses at phase boundaries (intake, document collection, review) using `interrupt()`. Streamlit resumes with `Command(resume=...)`.
4. **Reflexion as graph topology**: The validation agent's Reflexion loop is implemented as cyclic graph nodes with conditional routing and an iteration counter.
5. **`create_agent` replaces `create_react_agent`**: LangGraph v1 deprecates `create_react_agent`. Use `langchain.agents.create_agent` with middleware for Extraction, Eligibility, and Decision agents.

---

## 1. Subgraph Decomposition

### Architecture Decision

Each agent is a compiled `StateGraph` subgraph mounted as a node in the parent orchestrator graph. The parent sees each subgraph as an opaque node — it receives state, runs internal logic, returns updated state.

**Why subgraphs (not flat graph)**:
- The existing spec defines 5 agents with distinct responsibilities. A flat graph with all nodes would be 15+ nodes — too complex to debug or test.
- Subgraphs enable independent unit testing per agent.
- State isolation prevents key collisions between agents.
- Subgraphs are the 2026 LangGraph standard for multi-agent systems.

**Why not subagents (autonomous loops)**:
- Subagents filter context to prevent pollution — useful when agents need independent context windows.
- Our agents share state through the orchestrator (extracted data flows to validation, validation flows to eligibility). Subgraphs with shared state keys are simpler and more efficient.
- Subagents add overhead (separate context management) that isn't needed here.

### Parent Graph Structure

```python
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres import PostgresSaver

def build_orchestrator() -> CompiledStateGraph:
    builder = StateGraph(OrchestratorState)
    
    builder.add_node("auth", auth_node)
    builder.add_node("intake", intake_node)
    builder.add_node("doc_collection", doc_collection_node)
    builder.add_node("extraction", extraction_subgraph)
    builder.add_node("validation", validation_subgraph)
    builder.add_node("review", review_node)
    builder.add_node("eligibility", eligibility_subgraph)
    builder.add_node("decision", decision_subgraph)
    builder.add_node("enablement", enablement_node)
    
    builder.set_entry_point("auth")
    builder.add_edge("auth", "intake")
    builder.add_edge("intake", "doc_collection")
    builder.add_edge("doc_collection", "extraction")
    builder.add_edge("extraction", "validation")
    builder.add_edge("validation", "review")
    builder.add_edge("eligibility", "decision")
    builder.add_edge("decision", "enablement")
    builder.add_edge("enablement", END)
    
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"proceed": "eligibility", "reprocess": "processing"}
    )
    
    checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
    return builder.compile(checkpointer=checkpointer)
```

### State Mapping at Boundaries

Shared keys (e.g., `messages`, `applicant_id`) flow automatically when parent and subgraph schemas overlap. Isolated keys need explicit transformer functions.

```python
def parent_to_extraction(parent_state: OrchestratorState) -> ExtractionState:
    return {
        "messages": parent_state["messages"],
        "uploaded_documents": parent_state["uploaded_documents"],
        "applicant_id": parent_state["applicant_id"],
    }

def extraction_to_parent(extraction_state: ExtractionState) -> dict:
    return {
        "extracted_data": extraction_state["extracted_data"],
        "extraction_confidence": extraction_state["extraction_confidence"],
        "gate_status": extraction_state["gate_status"],
        "gate_errors": extraction_state["gate_errors"],
    }
```

### Rules

- Maximum 2 nesting levels (parent to subgraph). No deeper.
- Parent graph owns the checkpointer. Subgraphs inherit via `checkpointer=None` (default).
- State transformers are versioned and tested independently.
- Subgraph-internal state is ephemeral unless explicitly checkpointed.

---

## 2. State Isolation

### Per-Agent TypedDicts

Each agent gets its own `TypedDict` state. The parent orchestrator has a separate `OrchestratorState`. Private keys (agent-internal reasoning state) never leak to the parent.

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    current_phase: str
    applicant_id: str | None
    identity_number: str | None
    support_category: str | None
    basic_info: dict | None
    uploaded_documents: list[dict]
    extracted_data: dict[str, dict]
    validation_results: dict
    discrepancies: list[dict]
    eligibility_score: float | None
    decision: str | None
    decision_explanation: str | None

class ExtractionState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    applicant_id: str
    uploaded_documents: list[dict]
    extracted_data: dict[str, dict]
    extraction_confidence: dict[str, float]
    extraction_strategy: str
    gate_status: str
    gate_errors: list[str]
    retry_count: int

class ValidationState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    applicant_id: str
    extracted_data: dict[str, dict]
    validation_results: dict
    discrepancies: list[dict]
    critique_history: list[str]
    iteration_count: int
    overall_confidence: float

class EligibilityState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    applicant_id: str
    extracted_data: dict[str, dict]
    validation_results: dict
    eligibility_score: float | None
    eligibility_factors: dict | None
    adjusted_score: float | None
    explanation: str | None

class DecisionState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    applicant_id: str
    eligibility_score: float
    validation_results: dict
    discrepancies: list[dict]
    decision: str | None
    decision_explanation: str | None
    enablement_recommendations: list[dict] | None
```

### Rules

- Each agent's `TypedDict` is the single source of truth for that agent's state.
- Private keys (agent-internal reasoning state) never leak to the parent.
- Shared keys (`messages`, `applicant_id`) flow automatically through subgraph mounting.
- State transformers at the boundary are versioned and tested independently.

---

## 3. interrupt() Wiring for Chat Interaction

### Pattern

The 7-phase flow requires the graph to pause at phase boundaries and wait for user input through the Streamlit chat interface. Use `interrupt()` at phase boundaries where the graph needs user input. The graph pauses, state persists to the checkpointer, and the Streamlit UI renders the current state. When the user responds, `Command(resume=...)` resumes the graph.

```python
from langgraph.types import interrupt, Command

def intake_node(state: OrchestratorState) -> dict:
    missing_fields = get_missing_intake_fields(state)
    
    if not missing_fields:
        return {"current_phase": "document_collection"}
    
    field = missing_fields[0]
    user_response = interrupt({
        "question": f"What is your {field}?",
        "field": field,
        "phase": "intake"
    })
    
    return {"basic_info": {**state.get("basic_info", {}), field: user_response}}

def document_collection_node(state: OrchestratorState) -> dict:
    required = get_required_documents(state["support_category"])
    uploaded = [doc["doc_type"] for doc in state.get("uploaded_documents", [])]
    missing = [doc for doc in required if doc not in uploaded]
    
    if not missing:
        return {"current_phase": "processing"}
    
    uploaded_files = interrupt({
        "question": f"Please upload: {', '.join(missing)}",
        "missing_documents": missing,
        "phase": "document_collection"
    })
    
    return {"uploaded_documents": [*state.get("uploaded_documents", []), *uploaded_files]}

def review_node(state: OrchestratorState) -> dict:
    unresolved = [d for d in state["discrepancies"] 
                  if d["resolution_status"] == "unresolved"]
    
    if not unresolved:
        return {"current_phase": "decision"}
    
    discrepancy = unresolved[0]
    resolution = interrupt({
        "question": discrepancy["clarification_question"],
        "discrepancy": discrepancy,
        "phase": "review"
    })
    
    return {"discrepancy_resolutions": [resolution]}
```

### Streamlit Integration

```python
# In streamlit_app.py:
result = graph.invoke(input_state, config={"configurable": {"thread_id": applicant_id}})
if result.get("__interrupt__"):
    interrupt_data = result["__interrupt__"][0].value
    render_interrupt_to_chat(interrupt_data)
    # When user responds:
    result = graph.invoke(
        Command(resume=user_response),
        config={"configurable": {"thread_id": applicant_id}}
    )
```

### Phase Boundary Interrupts

| Phase | Interrupt Trigger | Resume Payload |
|-------|------------------|----------------|
| 1 (Intake) | Missing required field | Field value (string) |
| 2 (Doc Collection) | Missing required documents | List of uploaded file refs |
| 4 (Review) | Unresolved discrepancy | Resolution dict |
| 5 (Decision) | None (automated) | N/A |
| 6 (Enablement) | Follow-up question | User question text |

### Rules

- One `interrupt()` per node invocation. Never place multiple `interrupt()` calls in a loop within a single node. Resuming re-executes the node from the top, triggering earlier interrupts again.
- Use conditional edges to route back to the same node if re-prompting is needed.
- The `interrupt()` payload is a dict with enough context for the UI to render the question.
- `Command(resume=...)` payload becomes the return value of `interrupt()` inside the node.
- The checkpointer is mandatory. Without it, there is no state to resume from.

---

## 4. Reflexion Topology (Validation Agent)

### Graph Structure

The validation agent uses Reflexion (Attempt, Evaluate, Critique, Retry). This is implemented as a cyclic `StateGraph` with conditional routing and an iteration counter.

**Key insight**: Use distinct prompts for generation and critique to prevent the agent from rubber-stamping its own errors.

```python
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

def build_validation_subgraph() -> CompiledStateGraph:
    builder = StateGraph(ValidationState)
    
    builder.add_node("validate", validate_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("reflect", reflect_node)
    builder.add_node("gate", gate_check_node)
    builder.add_node("finalize", finalize_node)
    
    builder.set_entry_point("validate")
    builder.add_edge("validate", "evaluate")
    
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"high_confidence": "gate", "low_confidence": "reflect"}
    )
    
    builder.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {"retry": "validate", "max_iterations": "gate", "escalate": "finalize"}
    )
    
    builder.add_conditional_edges(
        "gate",
        route_after_gate,
        {"passed": "finalize", "failed": "reflect"}
    )
    
    builder.set_finish_point("finalize")
    
    return builder.compile()
```

### Routing Functions

```python
def route_after_evaluate(state: ValidationState) -> str:
    confidence = state.get("overall_confidence", 0)
    return "high_confidence" if confidence >= 0.85 else "low_confidence"

def route_after_reflect(state: ValidationState) -> str:
    iterations = state.get("iteration_count", 0)
    if iterations >= 3:
        return "max_iterations"
    unresolved_critical = [
        d for d in state.get("discrepancies", [])
        if d.get("classification") == "real_discrepancy"
        and d.get("resolution_status") == "unresolved"
    ]
    if len(unresolved_critical) > 3:
        return "escalate"
    return "retry"

def route_after_gate(state: ValidationState) -> str:
    return "passed" if state.get("gate_status") == "passed" else "failed"
```

### Node Implementations

```python
def validate_node(state: ValidationState) -> dict:
    extracted = state["extracted_data"]
    results = {}
    discrepancies = []
    
    for doc_id, doc_data in extracted.items():
        doc_results = run_per_document_validation(doc_data, doc_data["doc_type"])
        results[doc_id] = doc_results
    
    cross_results = run_cross_document_validation(extracted)
    discrepancies = cross_results.get("discrepancies", [])
    
    return {
        "validation_results": results,
        "discrepancies": discrepancies,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }

def evaluate_node(state: ValidationState) -> dict:
    classified = []
    for d in state.get("discrepancies", []):
        classification = classify_discrepancy(d, state["extracted_data"])
        classified.append({**d, **classification})
    
    confidence = compute_validation_confidence(classified)
    return {
        "discrepancies": classified,
        "overall_confidence": confidence,
    }

def reflect_node(state: ValidationState) -> dict:
    critique = generate_reflection_critique(
        discrepancies=state["discrepancies"],
        iteration=state.get("iteration_count", 0),
        previous_critiques=state.get("critique_history", []),
    )
    history = state.get("critique_history", []) + [critique]
    return {"critique_history": history}
```

### Rules

- Maximum 3 Reflexion iterations before forced exit to gate.
- `critique_history` is a private state key, never exposed to parent.
- Each iteration appends to `critique_history` so the reflector has full context.
- The gate node is deterministic (pure Python, no LLM).
- If gate fails after Reflexion retry, escalate to manual review (no infinite loop).

---

## 5. create_agent Migration and Middleware

### Deprecation Notice

LangGraph v1 deprecates `create_react_agent` from `langgraph.prebuilt`. Use `langchain.agents.create_agent` instead, which uses a middleware-based system.

**Migration**:

```python
# Old (deprecated)
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model, tools, prompt="...")

# New (LangGraph v1)
from langchain.agents import create_agent
agent = create_agent(model, tools, system_prompt="...")
```

### Agent-to-Pattern Assignment

| Agent | Pattern | Rationale |
|-------|---------|-----------|
| Master Orchestrator | Custom `StateGraph` | Deterministic routing, no LLM, `interrupt()` at boundaries |
| Data Extraction | `create_agent` + gate wrapper | Standard ReAct tool-calling loop |
| Data Validation | Custom `StateGraph` (Reflexion) | Cyclic graph with conditional routing |
| Eligibility Check | `create_agent` + gate wrapper | Standard ReAct tool-calling loop |
| Decision Recommendation | `create_agent` | Standard ReAct tool-calling loop |

### Middleware Composition

Middleware hooks into the agent loop at specific points: before model call, after tool execution, on errors. Each piece handles one concern and composes freely.

```python
from langchain.agents.middleware import retry_on_error, tool_timeout

extraction_agent = create_agent(
    model,
    tools=[
        ocr_extract_tool, pdf_parse_tool, table_extract_tool,
        resume_parse_tool, xlsx_extract_tool, confidence_score_tool,
    ],
    system_prompt=EXTRACTION_SYSTEM_PROMPT,
    middleware=[
        retry_on_error(max_retries=2, retryable_exceptions=[TimeoutError, ConnectionError]),
        tool_timeout(seconds=120),
    ],
)

eligibility_agent = create_agent(
    model,
    tools=[
        ml_model_predict_tool, feature_importance_tool,
        adjust_factor_weighting_tool, eligibility_explanation_tool,
    ],
    system_prompt=ELIGIBILITY_SYSTEM_PROMPT,
    middleware=[retry_on_error(max_retries=2)],
)

decision_agent = create_agent(
    model,
    tools=[
        decision_logic_tool, decision_explanation_tool,
        enablement_recommendation_tool, decision_formatting_tool,
    ],
    system_prompt=DECISION_SYSTEM_PROMPT,
    middleware=[retry_on_error(max_retries=2)],
)
```

### Observability

Langfuse tracing is injected at invocation time via callbacks, not as agent middleware.

```python
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

langfuse_handler = LangfuseCallbackHandler(
    trace_name=f"application-{applicant_id}",
    session_id=session_id,
    user_id=applicant_id,
    tags=[support_category, f"phase-{current_phase}"]
)

result = await extraction_agent.ainvoke(
    input_state,
    config={"callbacks": [langfuse_handler]}
)
```

### Rules

- Use `create_agent` for agents with standard ReAct tool-calling loops (Extraction, Eligibility, Decision).
- Use custom `StateGraph` for agents with non-standard control flow (Orchestrator with `interrupt()`, Validation with Reflexion cycles).
- Middleware handles cross-cutting concerns (retry, timeout). Langfuse handles observability via callbacks.
- Never mix `create_react_agent` (deprecated) with `create_agent` in the same codebase.

---

## 6. Agent-to-Pattern Mapping Summary

### Master Orchestrator

- **Pattern**: Custom `StateGraph` (no LLM). Parent graph.
- **State**: `OrchestratorState` (shared keys only, no private reasoning state).
- **Interrupts**: Phase 1 (intake fields), Phase 2 (document uploads), Phase 4 (discrepancy resolution).
- **Checkpointer**: Owns `PostgresSaver` (mandatory for resume capability).

### Data Extraction Agent

- **Pattern**: `create_agent` (ReAct tool-calling) wrapped as subgraph with gate.
- **State**: `ExtractionState`. Private keys: `extraction_strategy`, `retry_count`.
- **Gate**: Deterministic integrity checks (checksums, balance reconciliation, required fields).
- **Max retries**: 2 before escalation.
- **Checkpointer**: Inherits from parent.

### Data Validation Agent

- **Pattern**: Custom `StateGraph` with Reflexion cycle (Section 4).
- **State**: `ValidationState`. Private keys: `critique_history`, `iteration_count`.
- **Gate**: Deterministic completeness checks.
- **Max Reflexion iterations**: 3 before forced exit.
- **Checkpointer**: Inherits from parent.

### Eligibility Check Agent

- **Pattern**: `create_agent` (ReAct tool-calling) wrapped as subgraph with gate.
- **State**: `EligibilityState`. Private key: `adjusted_score`.
- **Gate**: Hard eligibility rules (Emirates ID validity, credit score range, identity consistency).
- **Checkpointer**: Inherits from parent.

### Decision Recommendation Agent

- **Pattern**: `create_agent` (ReAct tool-calling).
- **State**: `DecisionState`. No private keys (all outputs flow to parent).
- **Gate**: None (decision is final output, no hard constraints to validate).
- **Checkpointer**: Inherits from parent.

### Summary Table

| Agent | LangGraph Pattern | State TypedDict | Has Gate | Uses interrupt() | Checkpointer |
|-------|-------------------|-----------------|----------|-------------------|--------------|
| Orchestrator | Custom `StateGraph` | `OrchestratorState` | N/A | Yes (phases 1,2,4) | Owns (`PostgresSaver`) |
| Extraction | `create_agent` + gate wrapper | `ExtractionState` | Yes (integrity) | No | Inherits |
| Validation | Custom `StateGraph` (Reflexion) | `ValidationState` | Yes (completeness) | No | Inherits |
| Eligibility | `create_agent` + gate wrapper | `EligibilityState` | Yes (hard rules) | No | Inherits |
| Decision | `create_agent` | `DecisionState` | No | No | Inherits |

---

## Installation Commands

No additional packages beyond what is already in `2026-07-25-tech-stack-design.md`. The `create_agent` function is part of `langchain` (already included via `langgraph==1.2.9`). Middleware is part of `langchain.agents.middleware`.

```bash
# Already installed via tech stack spec
.\.venv\Scripts\pip.exe install langgraph==1.2.9
.\.venv\Scripts\pip.exe install langfuse==4.14.1
```

---

## Future Improvements

1. **Streaming**: Use LangGraph's streaming API (`astream_events`) to push real-time agent reasoning to the Streamlit chat interface.
2. **Time travel debugging**: Leverage PostgresSaver checkpoint history to replay any past state for debugging or audit.
3. **Dynamic model selection**: Use `create_agent`'s dynamic model callable to switch models per phase (e.g., smaller model for intake, larger for decision).
4. **Tool-level interrupt**: Use middleware `InterruptOnConfig` to require human approval before specific tool calls (e.g., database writes).
