# Agent Specification Design: Social Support Application Workflow Automation

**Date**: 2026-07-25  
**Status**: Draft  
**Python Version**: 3.11.12 (venv at `.venv/`)  
**Related Specs**: 
- `2026-07-25-tech-stack-design.md`
- `2026-07-25-applicant-user-flow-design.md`
- `2026-07-25-document-processing-schema-design.md`
- `2026-07-25-fake-data-generation-design.md`

---

## Executive Summary

This specification defines the architecture, responsibilities, and implementation patterns for the five AI agents in the UAE Social Support Application system. The agents use a **Hybrid ReAct + Deterministic Gates** architecture: LLM-autonomous agents with ReAct/Reflexion reasoning loops, constrained by deterministic validation gates that enforce hard constraints (math, checksums, completeness).

**Architecture decision**: Approach B — Hybrid ReAct + Deterministic Gates. LLM autonomy for strategy (how to extract, validate, interpret), deterministic gates for correctness (what must be true regardless of LLM judgment). This balances flexibility with auditability, prevents token waste on obviously invalid paths, and ensures regulatory compliance.

---

## Architecture Overview

### Hybrid ReAct + Deterministic Gates Pattern

**Core principle**: LLM decides *how* to extract/validate/interpret. Gates enforce *what must be true* regardless of LLM judgment.

**Pattern**: Agent → Gate → (Pass | Retry | Escalate)

1. **LLM agent** executes ReAct/Reflexion loop with full tool autonomy
2. **Deterministic gate** validates output against hard constraints (pure Python, no LLM)
3. **Routing logic**:
   - **Pass**: Gate validates, continue to next agent
   - **Fail + Retry**: Gate fails, error message fed back to LLM, LLM tries different strategy (max 2 retries)
   - **Fail + Escalate**: After retries exhausted, escalate to manual review

**Why this pattern**:
- **Prevents catastrophic errors**: LLM can't hallucinate a valid checksum. Math is math.
- **Reduces token waste**: If balance doesn't reconcile, don't let LLM interpret it — force re-extraction.
- **Faster processing**: Deterministic gates are instant (microseconds vs seconds for LLM calls).
- **Auditability**: Gates produce clear pass/fail logs. Regulators see "balance reconciliation failed" without parsing LLM reasoning.

### Agent Topology

```
┌─────────────────────────────────────────────────────────────┐
│ Master Orchestrator (LangGraph State Machine)               │
│ ├─ Phase 0: Authentication (deterministic)                  │
│ ├─ Phase 1: Intake (LLM-assisted, deterministic validation)│
│ ├─ Phase 2: Document Collection (deterministic tracking)    │
│ ├─ Phase 3: Processing                                     │
│ │   ├─ Data Extraction Agent (ReAct)                       │
│ │   │   └─ GATE 1: Document Integrity Checks               │
│ │   └─ Data Validation Agent (Reflexion)                   │
│ │       └─ GATE 2: Completeness Checks                     │
│ ├─ Phase 4: Review (LLM-assisted discrepancy resolution)   │
│ ├─ Phase 5: Decision                                       │
│ │   ├─ Eligibility Check Agent (ReAct)                     │
│ │   │   └─ GATE 3: Hard Eligibility Rules                  │
│ │   └─ Decision Recommendation Agent (ReAct)               │
│ └─ Phase 6: Enablement (LLM-assisted recommendations)      │
└─────────────────────────────────────────────────────────────┘
```

### Reasoning Framework Assignment

| Agent | Reasoning Framework | Rationale |
|---|---|---|
| Master Orchestrator | Graph-native routing (deterministic) | Workflow is well-defined by 7-phase flow. No LLM needed for routing. |
| Data Extraction Agent | ReAct | Must adapt extraction strategy per document type/format. LLM decides OCR vs PDF parsing vs table extraction. |
| Data Validation Agent | Reflexion | Must self-critique: "Is this discrepancy an OCR error or real?" Attempt → Evaluate → Critique → Retry. |
| Eligibility Check Agent | ReAct | Calls ML model, interprets results, adjusts factor weighting based on context. |
| Decision Recommendation Agent | ReAct | Synthesizes all inputs (eligibility, validation, context) and generates human-readable explanation. |

### Safeguards Against Runaway Costs

- **Recursion limit**: `recursion_limit=10` per agent (prevents infinite loops)
- **Reflexion iterations**: `max_iterations=3` for validation agent
- **Gate retries**: Max 2 retries per gate before escalation
- **Token monitoring**: Langfuse tracks token usage per agent per application
- **Confidence thresholds**: If LLM confidence < 0.70 after 2 retries, escalate to manual review

---

## LangGraph State Model

### Agent State Definition

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """State shared across all agents in the workflow."""
    
    # Messages (accumulated via add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Applicant identity (populated in Phase 0-1)
    applicant_id: str | None
    identity_number: str | None
    support_category: str | None
    
    # Documents (populated in Phase 2)
    uploaded_documents: list[dict]  # [{doc_type, file_path, document_id}]
    
    # Extraction results (populated in Phase 3)
    extracted_data: dict[str, dict]  # keyed by document_id
    extraction_confidence: dict[str, float]
    
    # Validation results (populated in Phase 3-4)
    validation_results: dict  # per-doc + cross-doc validation
    discrepancies: list[dict]
    
    # Eligibility (populated in Phase 5)
    eligibility_score: float | None
    eligibility_factors: dict | None
    
    # Decision (populated in Phase 5)
    decision: str | None  # "approved" | "soft_decline" | "manual_review"
    decision_explanation: str | None
    
    # Gate status (used for routing)
    gate_status: str  # "passed" | "failed"
    gate_errors: list[str]
    retry_count: int
    escalation_reason: str | None
```

---

## Agent 1: Master Orchestrator

**Status**: Approved

**Role**: The "conductor" that manages the entire workflow. Implemented as the LangGraph state machine itself.

**Active in**: All phases (runs continuously)

**Reasoning framework**: Graph-native routing (deterministic). No LLM needed for phase transitions — the graph topology handles routing based on state.

**Responsibilities**:
- Tracks current phase and transitions between phases
- Decides which agent to invoke at each phase
- Manages state (applicant data, documents, results)
- Handles exceptions (e.g., applicant wants to go back, missing documents)
- Coordinates the chatbot interface with backend agents
- Implements the "99% automated" logic — decides when human review is needed

**Implementation pattern**:
- LangGraph `StateGraph` with conditional edges
- Each phase is a node (or subgraph)
- Conditional edges route based on state (e.g., "if all docs uploaded → processing")
- No LLM calls in orchestrator — pure graph routing

**Phase transitions** (from user flow spec):
- Auth → Intake: Emirates ID validated
- Intake → Document Collection: All required basic_info fields populated
- Document Collection → Processing: All required documents uploaded
- Processing → Review: All documents extracted and validated (gates passed)
- Review → Decision: All discrepancies resolved or flagged
- Decision → Enablement: Decision delivered

**Error handling**:
- If gate fails after retries → escalate to manual review
- If LLM agent hits recursion limit → escalate to manual review
- If applicant uploads corrected docs during review → loop back to Processing

---

---

## Agent 2: Data Extraction Agent

**Status**: Approved

**Role**: Extracts structured data from uploaded documents (PDF, images, XLSX, DOCX). Uses ReAct reasoning to decide which extraction tools to call based on document type and content.

**Active in**: Phase 3 (Processing)

**Reasoning framework**: ReAct (Thought → Action → Observation loop)

**Input**: Uploaded documents (file paths, document types)

**Output**: Extracted data conforming to PostgreSQL schemas (emirates_id_data, bank_statement_data, credit_report_data, resume_data, assets_liabilities_data, application_form_data)

### Tools Available to Agent

The agent has 6 tools. It decides which to call based on document type and content.

```python
from langchain_core.tools import tool

@tool
def ocr_extract_tool(
    file_path: str,
    language: str = "en+ar",
    use_gpu: bool = False
) -> dict:
    """
    Extract text from images using PaddleOCR.
    
    Use for: Scanned documents, images (Emirates ID, application forms).
    Returns: Extracted text with bounding boxes and confidence scores.
    """
    pass

@tool
def pdf_parse_tool(
    file_path: str,
    pages: list[int] | None = None,
    extract_tables: bool = True
) -> dict:
    """
    Parse digital PDF using PyMuPDF4LLm.
    
    Use for: Digital PDFs with text layer (credit reports, bank statements).
    Returns: Markdown or JSON with extracted text, tables, and metadata.
    """
    pass

@tool
def table_extract_tool(
    file_path: str,
    flavor: str = "auto",
    pages: list[int] | None = None
) -> dict:
    """
    Extract tables from PDF using Camelot.
    
    Use for: Tabular data in PDFs (bank statements, assets/liabilities).
    Returns: Extracted tables as DataFrames.
    """
    pass

@tool
def resume_parse_tool(file_path: str) -> dict:
    """
    Parse resume/CV using SmartResume.
    
    Use for: Resumes in DOCX or PDF format.
    Returns: Structured resume data (contact, experience, education, skills).
    """
    pass

@tool
def xlsx_extract_tool(
    file_path: str,
    sheet_name: str | None = None
) -> dict:
    """
    Extract data from Excel file using openpyxl + pandas.
    
    Use for: Assets/liabilities statements in XLSX format.
    Returns: Extracted data as DataFrame.
    """
    pass

@tool
def confidence_score_tool(
    extracted_data: dict,
    document_type: str
) -> dict:
    """
    Compute field-level confidence scores for extracted data.
    
    Use for: Assessing extraction quality after extraction.
    Returns: Confidence scores per field and overall document.
    """
    pass
```

### ReAct Loop: How Agent Decides

The agent follows this reasoning pattern:

```
Thought: I need to extract data from this document. Let me check the document type.
Action: Infer document type from file metadata
Observation: Document is a bank statement (PDF)

Thought: This is a PDF bank statement. I should use table_extract_tool for tabular data, 
         and pdf_parse_tool for text sections.
Action: Call table_extract_tool(file_path="bank_statement.pdf", flavor="auto")
Observation: Extracted 3 tables with 95% accuracy

Thought: Tables extracted successfully. Now I need to extract header information 
         (account holder name, account number, statement period).
Action: Call pdf_parse_tool(file_path="bank_statement.pdf", pages=[1])
Observation: Extracted markdown with header information

Thought: I have tables and header. Now I need to compute confidence scores 
         to assess extraction quality.
Action: Call confidence_score_tool(extracted_data=..., document_type="bank_statement")
Observation: Overall confidence 0.92, no low-confidence fields

Thought: Extraction complete with high confidence. I'll return the extracted data.
Action: Return extracted_data dict
```

### Gate 1: Document Integrity Checks (Deterministic)

After the agent produces extracted data, the gate validates hard constraints:

```python
def validate_document_integrity(
    extracted_data: dict,
    document_type: str
) -> tuple[bool, list[str]]:
    """
    Deterministic validation of extracted data.
    Returns (is_valid, errors).
    """
    errors = []
    
    if document_type == "emirates_id":
        # Emirates ID checksum validation
        identity_number = extracted_data.get("identity_number", "")
        if not validate_emirates_id_checksum(identity_number):
            errors.append(f"Emirates ID checksum invalid: {identity_number}")
        
        # Expiry date must be in the future
        expiry_date = extracted_data.get("expiry_date")
        if expiry_date and expiry_date < date.today():
            errors.append(f"Emirates ID expired: {expiry_date}")
    
    elif document_type == "bank_statement":
        # Balance reconciliation
        opening = extracted_data.get("opening_balance", Decimal(0))
        credits = extracted_data.get("total_credits", Decimal(0))
        debits = extracted_data.get("total_debits", Decimal(0))
        closing = extracted_data.get("closing_balance", Decimal(0))
        
        expected_closing = opening + credits - debits
        if abs(expected_closing - closing) > Decimal("0.01"):
            errors.append(
                f"Bank statement balance does not reconcile: "
                f"opening({opening}) + credits({credits}) - debits({debits}) "
                f"= {expected_closing}, but closing is {closing}"
            )
        
        # Statement period validation
        period_start = extracted_data.get("statement_period_start")
        period_end = extracted_data.get("statement_period_end")
        if period_start and period_end and period_start >= period_end:
            errors.append(f"Invalid statement period: {period_start} >= {period_end}")
    
    elif document_type == "credit_report":
        # Credit score range
        credit_score = extracted_data.get("credit_score", 0)
        if not (300 <= credit_score <= 900):
            errors.append(f"Credit score outside valid range (300-900): {credit_score}")
        
        # Total outstanding must equal sum of facility balances
        total_outstanding = extracted_data.get("total_outstanding_balance", Decimal(0))
        facility_sum = sum(
            Decimal(f.get("current_balance", 0))
            for f in extracted_data.get("active_facilities", [])
        )
        if abs(total_outstanding - facility_sum) > Decimal("0.01"):
            errors.append(
                f"Total outstanding ({total_outstanding}) does not match "
                f"sum of facility balances ({facility_sum})"
            )
    
    elif document_type == "assets_liabilities":
        # Net worth calculation
        total_assets = extracted_data.get("total_assets", Decimal(0))
        total_liabilities = extracted_data.get("total_liabilities", Decimal(0))
        net_worth = extracted_data.get("net_worth", Decimal(0))
        
        expected_net_worth = total_assets - total_liabilities
        if abs(expected_net_worth - net_worth) > Decimal("0.01"):
            errors.append(
                f"Net worth calculation incorrect: "
                f"assets({total_assets}) - liabilities({total_liabilities}) "
                f"= {expected_net_worth}, but net_worth is {net_worth}"
            )
    
    # Common validation: required fields
    required_fields = get_required_fields(document_type)
    for field in required_fields:
        if field not in extracted_data or extracted_data[field] is None:
            errors.append(f"Required field missing: {field}")
    
    return (len(errors) == 0, errors)
```

### Gate Retry Logic

If the gate fails, the error is fed back to the agent:

```python
async def extraction_with_gate(
    state: AgentState,
    document: dict
) -> AgentState:
    """Extraction agent with deterministic gate."""
    
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        # 1. LLM agent extracts data (ReAct loop)
        extraction_result = await extraction_agent.ainvoke({
            "messages": [
                SystemMessage(content=f"Extract data from {document['doc_type']} document."),
                HumanMessage(content=f"File path: {document['file_path']}")
            ]
        })
        
        extracted_data = extraction_result["messages"][-1].content
        
        # 2. Deterministic gate checks result
        gate_passed, gate_errors = validate_document_integrity(
            extracted_data,
            document["doc_type"]
        )
        
        if gate_passed:
            # Gate passed — continue
            state["extracted_data"][document["document_id"]] = extracted_data
            state["gate_status"] = "passed"
            return state
        
        # 3. Gate failed — feed error back to agent
        retry_count += 1
        error_message = (
            f"Validation gate failed: {gate_errors}. "
            f"Retry {retry_count}/{max_retries}. "
            f"Try a different extraction strategy."
        )
        
        # Add error to messages so agent can see it and adapt
        extraction_result["messages"].append(
            SystemMessage(content=error_message)
        )
        
        # Agent will retry with different strategy
        state["messages"] = extraction_result["messages"]
    
    # 4. All retries exhausted — escalate
    state["gate_status"] = "failed"
    state["gate_errors"] = gate_errors
    state["escalation_reason"] = (
        f"Extraction failed validation after {max_retries} retries: {gate_errors}"
    )
    return state
```

### Error Handling

| Scenario | Handling |
|---|---|
| OCR fails (confidence < 0.80) | Agent retries with different OCR settings (e.g., enable GPU, adjust language). If still fails after 2 retries, escalate to manual review. |
| Document is corrupted | Agent detects error, chatbot asks applicant to re-upload. |
| Partial extraction (some fields missing) | Gate detects missing required fields, feeds error back to agent. Agent tries different extraction method. |
| Gate fails after 2 retries | Escalate to manual review with error details. |
| Agent hits recursion limit | Escalate to manual review. |

---

---

## Agent 3: Data Validation Agent

**Status**: Approved

**Role**: Validates extracted data for consistency and correctness. Uses Reflexion reasoning to self-critique and identify whether discrepancies are OCR errors or real inconsistencies.

**Active in**: Phase 3 (Processing) and Phase 4 (Review)

**Reasoning framework**: Reflexion (Attempt → Evaluate → Critique → Retry)

**Input**: Extracted data from all documents (from Agent 2)

**Output**: Validation results, discrepancies list, confidence scores, clarification questions

### Why Reflexion (not ReAct)?

The validation agent needs to **judge its own output** and **self-correct**. ReAct is linear (think → act → observe), but validation requires:
- **Attempt**: Initial validation pass
- **Evaluate**: Check if discrepancies are real or extraction errors
- **Critique**: Identify root cause (OCR error vs. actual discrepancy)
- **Retry**: If confidence is low, request re-extraction or ask applicant for clarification

This self-correction loop is Reflexion's strength.

### Tools Available to Agent

The agent has 5 tools for validation and discrepancy resolution.

```python
from langchain_core.tools import tool

@tool
def per_document_validation_tool(
    extracted_data: dict,
    document_type: str
) -> dict:
    """
    Validate extracted data within a single document.
    
    Use for: Checking internal consistency (e.g., do transactions sum to totals?).
    Returns: Validation results with pass/fail per rule.
    """
    pass

@tool
def cross_document_compare_tool(
    extracted_data: dict[str, dict],
    comparison_type: str
) -> dict:
    """
    Compare fields across multiple documents.
    
    Use for: Checking consistency between documents (e.g., does Emirates ID match credit report?).
    Returns: Comparison results with match/mismatch per field.
    """
    pass

@tool
def discrepancy_classify_tool(
    discrepancy: dict,
    extraction_confidence: dict
) -> dict:
    """
    Classify whether a discrepancy is an OCR error or a real inconsistency.
    
    Use for: Judging if a mismatch is due to extraction error or actual data inconsistency.
    Returns: Classification with confidence and recommended action.
    """
    pass

@tool
def applicant_clarify_tool(
    discrepancy: dict,
    applicant_context: dict
) -> dict:
    """
    Generate a clarification question for the applicant.
    
    Use for: Asking applicant to resolve ambiguous discrepancies.
    Returns: Formulated question and context.
    """
    pass

@tool
def validation_confidence_tool(
    validation_results: dict,
    discrepancies: list[dict]
) -> dict:
    """
    Compute overall validation confidence score.
    
    Use for: Assessing whether validation is complete or needs more work.
    Returns: Confidence score and recommendation.
    """
    pass
```

### Reflexion Loop: How Agent Self-Corrects

The agent follows this reasoning pattern:

```
Attempt 1:
Thought: I need to validate the extracted data. Let me start with per-document validation.
Action: Call per_document_validation_tool(extracted_data=bank_statement_data, document_type="bank_statement")
Observation: Validation passed. Balance reconciles, dates are consistent.

Thought: Now I need to validate across documents. Let me check identity consistency.
Action: Call cross_document_compare_tool(extracted_data=all_docs, comparison_type="identity_match")
Observation: Mismatch found. Emirates ID name is "Ahmed Hassan Mohammed", credit report name is "Ahmed H. Mohammed".

Evaluate:
Thought: I found a name discrepancy. Is this an OCR error or a real inconsistency?
Action: Call discrepancy_classify_tool(discrepancy={...}, extraction_confidence={...})
Observation: Classification: "ocr_error", confidence 0.85. Reasoning: "Name variation is minor (middle initial vs full name) and extraction confidence is high."

Critique:
Thought: The discrepancy classifier says it's an OCR error with 85% confidence. But I should check other fields to be sure.
Action: Call cross_document_compare_tool(extracted_data=all_docs, comparison_type="income_consistency")
Observation: Mismatch found. Bank statement salary is 15,000 AED, application form salary is 12,000 AED.

Thought: This is a larger discrepancy (3,000 AED difference). Let me classify it.
Action: Call discrepancy_classify_tool(discrepancy={...}, extraction_confidence={...})
Observation: Classification: "real_discrepancy", confidence 0.90. Reasoning: "Income difference is significant and extraction confidence is high. Likely real discrepancy."

Retry:
Thought: I have a real discrepancy. I need to ask the applicant to clarify.
Action: Call applicant_clarify_tool(discrepancy={...}, applicant_context={...})
Observation: Generated question: "Your bank statement shows a salary of 15,000 AED, but your application form states 12,000 AED. Can you clarify?"

Thought: I've identified the discrepancy and generated a clarification question. Let me compute overall validation confidence.
Action: Call validation_confidence_tool(validation_results={...}, discrepancies=[...])
Observation: Overall confidence 0.88, 1 unresolved discrepancy. Recommendation: "proceed_to_review".

Thought: Validation complete. I'll return the results and the clarification question for the applicant.
Action: Return validation_results, discrepancies, clarification_questions
```

### Gate 2: Completeness Checks (Deterministic)

After the agent produces validation results, the gate validates completeness:

```python
def validate_completeness(
    validation_results: dict,
    extracted_data: dict[str, dict],
    required_documents: list[str]
) -> tuple[bool, list[str]]:
    """
    Deterministic validation of completeness.
    Returns (is_complete, missing_items).
    """
    missing_items = []
    
    # Check all required documents were processed
    processed_doc_types = [doc["doc_type"] for doc in extracted_data.values()]
    for required_doc in required_documents:
        if required_doc not in processed_doc_types:
            missing_items.append(f"Required document not processed: {required_doc}")
    
    # Check all required fields are present in extracted data
    for doc_id, doc_data in extracted_data.items():
        doc_type = doc_data["doc_type"]
        required_fields = get_required_fields(doc_type)
        for field in required_fields:
            if field not in doc_data or doc_data[field] is None:
                missing_items.append(f"Required field missing in {doc_type}: {field}")
    
    # Check identity consistency (hard requirement)
    identity_numbers = [
        doc.get("identity_number")
        for doc in extracted_data.values()
        if doc.get("identity_number")
    ]
    if len(set(identity_numbers)) > 1:
        missing_items.append("Identity number inconsistent across documents")
    
    return (len(missing_items) == 0, missing_items)
```

### Output: Validation Results Schema

The agent produces validation results conforming to PostgreSQL schema:

```python
{
    "per_document_validation": {
        "document_id_1": {
            "validation_results": [
                {"rule": "balance_reconciliation", "status": "passed", "message": "..."},
                {"rule": "date_consistency", "status": "passed", "message": "..."}
            ],
            "overall_status": "valid",
            "confidence": 0.95
        }
    },
    "cross_document_validation": {
        "identity_match": {
            "results": [...],
            "overall_match": True,
            "confidence": 1.0
        },
        "income_consistency": {
            "results": [...],
            "overall_match": False,
            "discrepancies": ["salary_mismatch"],
            "confidence": 0.90
        }
    },
    "discrepancies": [
        {
            "discrepancy_type": "income_consistency",
            "field": "monthly_salary",
            "values": {
                "bank_statement": "15,000 AED",
                "application_form": "12,000 AED"
            },
            "classification": "real_discrepancy",
            "confidence": 0.90,
            "resolution_status": "unresolved",
            "clarification_question": "Your bank statement shows..."
        }
    ],
    "overall_confidence": 0.88,
    "recommendation": "proceed_to_review"
}
```

### Error Handling

| Scenario | Handling |
|---|---|
| Discrepancy classification confidence < 0.70 | Agent retries classification with more context. If still low, escalate to manual review. |
| Applicant doesn't respond to clarification | After timeout, mark discrepancy as "unresolved" and proceed to decision (will be "manual_review"). |
| Validation agent hits recursion limit | Escalate to manual review with partial validation results. |
| Gate fails (missing required documents) | Chatbot asks applicant to upload missing documents. |
| Multiple discrepancies (>5) | Agent prioritizes by severity (identity > income > address). Focus on critical discrepancies first. |

---

---

## Agent 4: Eligibility Check Agent

**Status**: Approved

**Role**: Computes eligibility score using the ML model and interprets results in context. Uses ReAct reasoning to decide how to weight factors based on applicant's specific situation.

**Active in**: Phase 5 (Decision)

**Reasoning framework**: ReAct (Thought → Action → Observation loop)

**Input**: Extracted and validated data from all documents, validation results, applicant context

**Output**: Eligibility score (0-1), feature importance breakdown, human-readable explanation, recommended support level

### Why ReAct (not just ML model call)?

The ML model produces a numeric score, but the agent needs to:
- **Interpret** the score in context (e.g., "score is 0.65, but applicant has 5 children — that's actually good")
- **Adjust** factor weighting based on support category (e.g., "for divorced applicants, employment stability matters less")
- **Explain** the result in human-readable terms (e.g., "you qualify because your income is low and you have dependents")

This requires LLM reasoning on top of the ML model output.

### Tools Available to Agent

The agent has 4 tools for eligibility assessment.

```python
from langchain_core.tools import tool

@tool
def ml_model_predict_tool(
    applicant_features: dict
) -> dict:
    """
    Call scikit-learn HistGradientBoostingClassifier to predict eligibility.
    
    Use for: Computing eligibility score based on applicant features.
    Returns: Probability score (0-1) and predicted class.
    
    Args:
        applicant_features: Feature dict with keys:
            - monthly_income: float
            - family_size: int
            - employment_stability_months: int
            - credit_score: int
            - debt_to_income_ratio: float
            - net_worth: float
            - housing_cost_ratio: float
            - support_category: str
            - has_dependents: bool
            - employment_status: str
    """
    pass

@tool
def feature_importance_tool(
    applicant_features: dict,
    n_top_features: int = 5
) -> dict:
    """
    Compute feature importance using SHAP values or permutation importance.
    
    Use for: Understanding which factors drove the eligibility score.
    Returns: Top features and their contribution to the score.
    """
    pass

@tool
def adjust_factor_weighting_tool(
    eligibility_score: float,
    feature_importance: list[dict],
    applicant_context: dict
) -> dict:
    """
    Adjust eligibility score based on applicant context and support category.
    
    Use for: Contextual interpretation of the ML model output.
    Returns: Adjusted score and reasoning.
    """
    pass

@tool
def eligibility_explanation_tool(
    eligibility_score: float,
    feature_importance: list[dict],
    applicant_context: dict,
    validation_results: dict
) -> dict:
    """
    Generate human-readable explanation of eligibility decision.
    
    Use for: Explaining the decision to the applicant in plain language.
    Returns: Explanation text and key factors.
    """
    pass
```

### ReAct Loop: How Agent Decides

The agent follows this reasoning pattern:

```
Thought: I need to assess eligibility. Let me start by calling the ML model with the applicant's features.
Action: Call ml_model_predict_tool(applicant_features={...})
Observation: Eligibility score 0.72, predicted class 1 (eligible), confidence 0.85

Thought: The score is 0.72, which is above the threshold (0.60). Now I need to understand which factors drove this score.
Action: Call feature_importance_tool(applicant_features={...}, n_top_features=5)
Observation: Top features: monthly_income (-0.25), family_size (+0.18), credit_score (+0.15)

Thought: The model says low income is the strongest positive factor. But this applicant is divorced with 3 children. For the "divorced" support category, family size and dependents should weigh more heavily. Let me adjust the score.
Action: Call adjust_factor_weighting_tool(eligibility_score=0.72, feature_importance=[...], applicant_context={...})
Observation: Adjusted score 0.78 (+0.06). Reason: "Applicant is divorced with 3 dependents."

Thought: The adjusted score is 0.78, which is good. Now I need to generate a human-readable explanation.
Action: Call eligibility_explanation_tool(eligibility_score=0.78, ...)
Observation: Explanation: "Based on your application, you are eligible for social support..."

Thought: I have the eligibility score, feature importance, and explanation. I'll return the results.
Action: Return eligibility_score, feature_importance, explanation
```

### Gate 3: Hard Eligibility Rules (Deterministic)

After the agent produces eligibility results, the gate validates hard rules:

```python
def check_hard_eligibility_rules(
    extracted_data: dict[str, dict],
    validation_results: dict
) -> tuple[bool, str | None]:
    """
    Deterministic validation of hard eligibility rules.
    Returns (passes, failure_reason).
    """
    # Check Emirates ID validity and expiry
    emirates_id_data = next(
        (doc for doc in extracted_data.values() if doc["doc_type"] == "emirates_id"),
        None
    )
    if not emirates_id_data:
        return (False, "Emirates ID not provided")
    
    if not validate_emirates_id_checksum(emirates_id_data.get("identity_number", "")):
        return (False, "Emirates ID checksum invalid")
    
    expiry_date = emirates_id_data.get("expiry_date")
    if expiry_date and expiry_date < date.today():
        return (False, "Emirates ID expired")
    
    # Check credit score range (300-900)
    credit_report_data = next(
        (doc for doc in extracted_data.values() if doc["doc_type"] == "credit_report"),
        None
    )
    if credit_report_data:
        credit_score = credit_report_data.get("credit_score", 0)
        if not (300 <= credit_score <= 900):
            return (False, f"Credit score outside valid range: {credit_score}")
    
    # Check identity consistency across documents
    identity_numbers = [
        doc.get("identity_number")
        for doc in extracted_data.values()
        if doc.get("identity_number")
    ]
    if len(set(identity_numbers)) > 1:
        return (False, "Identity number inconsistent across documents")
    
    # Check bank statement reconciliation
    bank_statement_data = next(
        (doc for doc in extracted_data.values() if doc["doc_type"] == "bank_statement"),
        None
    )
    if bank_statement_data:
        opening = bank_statement_data.get("opening_balance", Decimal(0))
        credits = bank_statement_data.get("total_credits", Decimal(0))
        debits = bank_statement_data.get("total_debits", Decimal(0))
        closing = bank_statement_data.get("closing_balance", Decimal(0))
        
        expected_closing = opening + credits - debits
        if abs(expected_closing - closing) > Decimal("0.01"):
            return (False, "Bank statement balance does not reconcile")
    
    # Check all required documents present
    support_category = extracted_data.get("support_category")
    required_docs = get_required_documents(support_category)
    processed_docs = [doc["doc_type"] for doc in extracted_data.values()]
    missing_docs = [doc for doc in required_docs if doc not in processed_docs]
    if missing_docs:
        return (False, f"Missing required documents: {missing_docs}")
    
    # Check validation confidence >= 0.70
    if validation_results.get("overall_confidence", 0) < 0.70:
        return (False, "Validation confidence too low")
    
    return (True, None)
```

### Error Handling

| Scenario | Handling |
|---|---|
| ML model fails to load | Escalate to manual review with error message. |
| Feature preprocessing fails (missing values) | Agent identifies missing features, asks chatbot to request from applicant. |
| Eligibility score is borderline (0.55-0.65) | Agent flags for manual review with explanation. |
| Gate fails (hard rule violation) | Auto-decline with reason (no LLM needed). Chatbot informs applicant. |
| Agent hits recursion limit | Escalate to manual review with partial results. |

---

---

## Agent 5: Decision Recommendation Agent

**Status**: Approved

**Role**: Synthesizes all inputs (eligibility score, validation results, applicant context) and generates the final recommendation (approve/soft_decline/manual_review) with a human-readable explanation. Uses ReAct reasoning to structure the decision logic.

**Active in**: Phase 5 (Decision)

**Reasoning framework**: ReAct (Thought → Action → Observation loop)

**Input**: Eligibility results (from Agent 4), validation results (from Agent 3), applicant context, support category requirements

**Output**: Final decision (approve/soft_decline/manual_review), decision explanation, next steps, enablement recommendations (if applicable)

### Why ReAct?

The decision agent needs to:
- **Synthesize** multiple inputs (eligibility score, validation confidence, discrepancies)
- **Apply** decision rules (thresholds, confidence routing)
- **Generate** context-aware explanations (why approved/declined, what could improve)
- **Recommend** next steps (enablement programs, document corrections)

This requires LLM reasoning to balance quantitative scores with qualitative context.

### Tools Available to Agent

The agent has 4 tools for decision synthesis and explanation.

```python
from langchain_core.tools import tool

@tool
def decision_logic_tool(
    eligibility_score: float,
    validation_confidence: float,
    discrepancies: list[dict],
    support_category: str
) -> dict:
    """
    Apply decision rules to determine final recommendation.
    
    Decision rules:
    - eligibility_score > 0.60 AND validation_confidence > 0.80 AND no critical discrepancies → Approve
    - eligibility_score < 0.40 OR validation_confidence < 0.70 OR critical discrepancies unresolved → Soft Decline
    - Otherwise → Manual Review
    """
    pass

@tool
def decision_explanation_tool(
    decision: str,
    eligibility_results: dict,
    validation_results: dict,
    applicant_context: dict
) -> dict:
    """
    Generate human-readable explanation of the decision.
    Returns: Explanation text tailored to the decision.
    """
    pass

@tool
def enablement_recommendation_tool(
    applicant_context: dict,
    eligibility_results: dict,
    decision: str
) -> dict:
    """
    Generate personalized enablement recommendations (upskilling, job matching, etc.).
    Returns: List of recommendations tailored to applicant's profile.
    """
    pass

@tool
def decision_formatting_tool(
    decision: str,
    explanation: dict,
    enablement_recommendations: dict | None,
    applicant_context: dict
) -> dict:
    """
    Format the final decision for display in the chat interface.
    Returns: Formatted decision card with styling information.
    """
    pass
```

### ReAct Loop: How Agent Decides

```
Thought: I need to make the final decision. Let me apply the decision rules.
Action: Call decision_logic_tool(eligibility_score=0.78, validation_confidence=0.88, discrepancies=[], support_category="divorced")
Observation: Decision: "approved". Reasoning: "Score 0.78 > 0.60, confidence 0.88 > 0.80, no critical discrepancies."

Thought: The decision is "approved". Now I need to generate a human-readable explanation.
Action: Call decision_explanation_tool(decision="approved", ...)
Observation: Explanation: "Your application has been approved. You qualify for 2,000 AED/month for 12 months."

Thought: The decision is approved, so I should also provide enablement recommendations.
Action: Call enablement_recommendation_tool(applicant_context={...}, ...)
Observation: Recommendations: upskilling, job_matching, financial_literacy.

Thought: I have everything. Now format for display.
Action: Call decision_formatting_tool(decision="approved", ...)
Observation: Formatted decision card with green color, support details, next steps.

Thought: Decision complete. Return formatted results.
Action: Return decision_card, explanation_text, next_steps, enablement_section
```

### Decision Rules

```python
def apply_decision_rules(
    eligibility_score: float,
    overall_confidence: float,
    discrepancies: list[dict],
    support_category: str
) -> tuple[str, str]:
    """Apply decision rules. Returns (decision, reasoning)."""
    
    critical_discrepancies = [
        d for d in discrepancies
        if d["discrepancy_type"] in ["identity_match", "income_consistency"]
        and d["resolution_status"] == "unresolved"
    ]
    
    # Align with user flow spec: overall confidence < 0.80 OR unresolved discrepancies → Manual Review
    if overall_confidence < 0.80 or len(critical_discrepancies) > 0:
        return (
            "manual_review",
            f"Overall confidence {overall_confidence:.2f} < 0.80 or {len(critical_discrepancies)} unresolved critical discrepancies."
        )
    
    # High confidence, no critical discrepancies
    if eligibility_score > 0.60:
        return ("approved", f"Eligibility score {eligibility_score:.2f} > 0.60, confidence {overall_confidence:.2f} >= 0.80, no critical discrepancies.")
    
    elif eligibility_score < 0.40:
        return ("soft_decline", f"Eligibility score {eligibility_score:.2f} < 0.40.")
    
    else:
        return ("manual_review", f"Borderline eligibility score {eligibility_score:.2f} (0.40-0.60).")
```

### Error Handling

| Scenario | Handling |
|---|---|
| Decision logic tool fails | Escalate to manual review with error message. |
| Explanation generation fails | Use fallback template: "Your application has been [decision]. Please contact support for details." |
| Enablement recommendations fail | Skip enablement section, proceed with decision only. |
| Agent hits recursion limit | Escalate to manual review with partial results. |
| Applicant context is incomplete | Agent uses available context, notes missing information in explanation. |

---

## Observability Integration (Langfuse v4)

All agents are traced via Langfuse v4 using the LangChain CallbackHandler.

### Integration Pattern

```python
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

# Create handler per invocation with trace context
langfuse_handler = LangfuseCallbackHandler(
    trace_name=f"application-{applicant_id}",
    session_id=session_id,
    user_id=applicant_id,
    tags=[support_category, f"phase-{current_phase}"]
)

# Pass to graph invocation
result = await app.ainvoke(
    state,
    config={"callbacks": [langfuse_handler]}
)
```

### What Gets Traced

- Every LLM call (model, prompt, response, tokens, latency)
- Every tool invocation (tool name, arguments, result, duration)
- Every gate check (pass/fail, errors, retry count)
- Every phase transition (from → to, state changes)
- End-to-end trace per application (from Emirates ID login to decision)

### Monitoring Dashboards

- **Per-agent token usage**: Track cost per agent per application
- **Gate failure rates**: Monitor which gates fail most often
- **Latency percentiles**: p50/p95/p99 per phase
- **Confidence distributions**: Track extraction and validation confidence over time
- **Escalation rates**: Percentage of applications requiring manual review

---

## Integration Patterns

### Agent-to-Agent Communication

Agents don't call each other directly. They communicate through the shared `AgentState`:

```
Extraction Agent → writes to state["extracted_data"]
Validation Agent → reads state["extracted_data"], writes to state["validation_results"]
Eligibility Agent → reads state["extracted_data"] + state["validation_results"], writes to state["eligibility_score"]
Decision Agent → reads all state fields, writes to state["decision"]
```

### Database Integration

Each agent writes to PostgreSQL after completing its work:

| Agent | Tables Written |
|---|---|
| Extraction Agent | `documents` (update extraction_status), `emirates_id_data`, `bank_statement_data`, `credit_report_data`, `resume_data`, `assets_liabilities_data`, `application_form_data`, `document_extraction_fields` |
| Validation Agent | `cross_document_validations`, `documents` (update validation_status) |
| Eligibility Agent | `applications` (update eligibility_score) |
| Decision Agent | `applications` (update decision, decision_explanation) |

### Neo4j Integration

After extraction, the Extraction Agent creates graph relationships:

```cypher
// Applicant → Document relationships
MATCH (a:Applicant {id: $applicant_id})
MATCH (d:Document {id: $document_id})
CREATE (a)-[:SUBMITTED {submitted_at: $timestamp}]->(d)

// Family relationships (from extracted dependents)
MATCH (a:Applicant {id: $applicant_id})
CREATE (a)-[:HAS_DEPENDENT {relationship: $rel}]->(dep:Person {name: $name, dob: $dob})
```

### Qdrant Integration

After extraction, the Extraction Agent creates document embeddings:

```python
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333, prefer_grpc=True)

# Embed extracted text and store
embedding = embedding_model.encode(extracted_text)
client.upsert(
    collection_name="documents",
    points=[{
        "id": document_id,
        "vector": embedding,
        "payload": {
            "applicant_id": applicant_id,
            "document_type": doc_type,
            "extracted_text": extracted_text[:1000]  # first 1000 chars
        }
    }]
)
```

---

## Confidence Routing Summary

| Confidence Level | Action |
|---|---|
| > 0.95 | Auto-process, no human review needed |
| 0.80 - 0.95 | Auto-process with spot-check flag |
| 0.70 - 0.80 | Flag for manual review |
| < 0.70 | Escalate to manual review, chatbot explains to applicant |

If the **overall application confidence** (weighted average of all document confidences) is < 0.80, the decision is "Manual Review" regardless of eligibility score.

---

## Future Improvements

1. **Multi-language support**: Agents handle Arabic-language documents natively (PaddleOCR already supports Arabic)
2. **Incremental model retraining**: As decisions are made and outcomes tracked, retrain the scikit-learn eligibility model quarterly
3. **Anomaly detection**: Add a dedicated agent to flag unusual patterns (e.g., sudden income drop, multiple applications from same address)
4. **Caseworker dashboard**: UI for reviewing manual_review cases with full agent reasoning trace
5. **Appeals workflow**: Applicant can appeal decision with additional evidence, triggering re-validation
6. **Government API integration**: Verify Emirates ID, query employment records via government APIs
7. **Voice input**: Applicant can speak responses instead of typing (requires speech-to-text integration)

---

## Installation Commands

No additional packages beyond what's already in `2026-07-25-tech-stack-design.md`. All agent dependencies are covered:

```bash
# Already installed via tech stack spec
.\.venv\Scripts\pip.exe install langgraph==1.2.9
.\.venv\Scripts\pip.exe install langfuse==4.14.1
.\.venv\Scripts\pip.exe install scikit-learn==1.9.0
.\.venv\Scripts\pip.exe install openai>=1.0.0
.\.venv\Scripts\pip.exe install qdrant-client==1.18.0
.\.venv\Scripts\pip.exe install neo4j==6.2.0

# Additional for SHAP (feature importance)
.\.venv\Scripts\pip.exe install shap>=0.46.0
```
