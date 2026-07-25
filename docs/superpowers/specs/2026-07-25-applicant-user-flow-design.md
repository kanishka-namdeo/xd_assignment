# Applicant User Flow Design: Social Support Application Workflow Automation

**Date**: 2026-07-25  
**Status**: Finalized  
**Python Version**: 3.11.12 (venv at `.venv/`)  
**Related Specs**: `2026-07-25-tech-stack-design.md`, `2026-07-25-document-processing-schema-design.md`, `2026-07-25-fake-data-generation-design.md`

---

## Executive Summary

This specification defines the end-user (applicant) flow for the UAE Social Support Application system. The applicant interacts with a GenAI chatbot through a single conversational session that guides them through application intake, document upload, processing, review, decision delivery, and enablement recommendations.

The flow uses a **hybrid structured + conversational** approach: six phases with clear boundaries, where structured phases ensure completeness and conversational phases allow natural interaction. The chatbot is the sole user interface — no separate forms or dashboards.

**Scope**: Applicant-facing flow only. Caseworker review dashboard is out of scope.

---

## Design Decisions

### Interaction Model: Chat-Only

**Decision**: Single chat interface using Streamlit's `st.chat_message` + `st.chat_input` with native file upload.

**Rationale**:
- The case study explicitly requires a "GenAI Chatbot" for "live interactions"
- Streamlit 1.60 supports `st.chat_input(accept_file="multiple", file_type=["pdf", "xlsx", "docx", "png", "jpg"])` — native multi-file upload in chat
- `st.chat_message` containers can hold any Streamlit element (buttons, charts, status indicators)
- `@st.fragment` enables partial reruns so chat interaction doesn't rerun the entire page
- `submit_mode="disable"` prevents users from interrupting LLM responses
- Simplest to implement and demo, aligns with "99% automated in minutes" goal

### Flow Structure: Hybrid Structured + Conversational

**Decision**: Six phases with clear boundaries. Structured phases ensure all required information is collected. Conversational phases allow natural interaction where it matters.

**Rationale**:
- Pure linear flow is too rigid — applicant may not have all documents ready
- Pure adaptive flow is hard to control — risk of missing required steps
- Hybrid balances completeness (structured phases) with naturalness (conversational phases)
- Maps cleanly to LangGraph's graph structure — each phase is a subgraph with defined entry/exit conditions
- Demo-friendly — can show both automation and intelligent conversation

### Session Structure: Single Session

**Decision**: Applicant completes entire application in one conversation. Optional "Check Application Status" feature in sidebar for returning users.

**Rationale**:
- Aligns with "99% automated decision-making within minutes" goal
- LangGraph checkpoint persists state if applicant returns (same browser session)
- Status check is a lightweight addition (Emirates ID → PostgreSQL query → display result)
- Multi-session with authentication adds complexity without prototype value

---

## High-Level Flow Overview

The applicant journey consists of six phases, each implemented as a LangGraph subgraph.

### Phase 1: Intake (Structured)

**Purpose**: Collect required basic information from the applicant.

**Flow**:
1. Chatbot greets applicant and explains the process
2. Collects required fields through conversation:
   - Full name (English + Arabic)
   - Emirates ID number (validated with Luhn checksum)
   - Date of birth
   - Nationality
   - Contact phone and email
   - Address (emirate, city, street, PO box)
   - Marital status
   - Family size
   - Employment status (employed, self_employed, unemployed, retired)
   - Employer name and occupation (if employed)
   - Housing status (owned, rented, family_provided)
   - Support category (divorced, abandoned, unknown_parentage, health_disability)
3. Creates applicant record in PostgreSQL
4. Determines which documents are required based on support category

**Exit condition**: All required fields collected and validated.

**Agent**: Master Orchestrator collects info directly (no specialized agent needed).

### Phase 2: Document Collection (Semi-structured)

**Purpose**: Collect all required supporting documents.

**Flow**:
1. Chatbot requests documents in logical groups:
   - **Identity documents**: Emirates ID (image)
   - **Financial documents**: Bank statements (PDF), credit report (PDF), assets/liabilities (XLSX)
   - **Employment documents**: Resume (DOCX/PDF)
   - **Supporting documents**: Based on support category (e.g., divorce certificate, medical reports)
2. Applicant uploads documents via `st.chat_input(accept_file="multiple")`
3. Applicant can upload in any order
4. Chatbot confirms receipt with real-time feedback ("I've received your Emirates ID — processing...")
5. File upload preview shows in chat (file name, size, type)

**Required documents by support category**:

| Support Category | Required Documents |
|---|---|
| Divorced | Emirates ID, bank statement, credit report, application form |
| Abandoned | Emirates ID, bank statement, credit report, application form, assets/liabilities |
| Unknown parentage | Emirates ID, bank statement, application form |
| Health/disability | Emirates ID, bank statement, credit report, application form, resume |

**Conditional requirements**:
- **Resume**: Required if employment_status is "employed" or "self_employed", OR if support_category is "health_disability"
- **Assets/liabilities**: Required if support_category is "abandoned", OR if applicant reports significant assets (>50,000 AED) or liabilities (>30,000 AED) in conversation

**Exit condition**: All required documents uploaded (minimum viable set for eligibility assessment).

**Agent**: Master Orchestrator manages uploads. Classification agent (part of extraction pipeline) identifies document types.

### Phase 3: Processing (Automated)

**Purpose**: Extract data from documents, validate, and compute confidence scores.

**Flow**:
1. **Data Extraction Agent** processes each document:
   - OCR (PaddleOCR) for scanned documents and images
   - Table extraction (Camelot) for bank statements, assets/liabilities
   - PDF parsing (PyMuPDF4LLM) for credit reports
   - Resume parsing (SmartResume) for resumes
   - Extracts data into PostgreSQL schemas (emirates_id_data, bank_statement_data, etc.)
   - Computes field-level confidence scores
   - Uses ReAct reasoning to decide which extraction tools to call
2. **Data Validation Agent** validates extracted data:
   - Per-document validation (Emirates ID checksum, balance reconciliation, credit score range)
   - Cross-document validation (identity match, income consistency, address match, employment match, debt consistency)
   - Uses Reflexion reasoning (attempt → evaluate → critique → retry) for self-correction
   - Stores results in `cross_document_validations` table
3. System stores extraction results in PostgreSQL
4. Creates document embeddings in Qdrant
5. Models family relationships in Neo4j

**Exit condition**: All documents processed, validation complete, confidence scores computed.

**Agents**: Data Extraction Agent, Data Validation Agent.

### Phase 4: Review (Conversational)

**Purpose**: Resolve discrepancies and clarify findings with the applicant.

**Flow**:
1. Chatbot presents processing summary to applicant
2. If discrepancies found, chatbot asks clarifying questions:
   - "Your bank statement shows a salary of 15,000 AED, but your application form states 12,000 AED. Can you clarify?"
   - "Your credit report shows an outstanding loan not mentioned in your assets/liabilities statement. Is this correct?"
3. Applicant can provide explanations or upload corrected documents
4. If applicant uploads new documents, system loops back to Phase 3 for re-processing
5. Data Validation Agent helps chatbot formulate clarification questions

**Exit condition**: All discrepancies resolved or flagged for manual review.

**Agent**: Data Validation Agent (assists chatbot with discrepancy details).

### Phase 5: Decision (Structured)

**Purpose**: Compute eligibility and deliver decision.

**Flow**:
1. **Eligibility Check Agent** computes eligibility score:
   - Calls scikit-learn `HistGradientBoostingClassifier`
   - Input features: income level, family size, employment history stability, asset/liability ratio, credit score, payment history, demographic profile
   - Output: eligibility score (0-1) + feature importance
   - Identifies key factors driving the score
2. **Decision Recommendation Agent** makes recommendation:
   - Input: eligibility score, validation results, applicant context, support category requirements
   - Output: Approve, Soft Decline, or Manual Review
   - Generates human-readable explanation (why, what factors, what could improve eligibility, next steps)
   - Uses ReAct reasoning to structure explanation
3. Chatbot presents decision as styled card in chat:
   - Green card for "Approved" with support details (amount, duration, next steps)
   - Yellow card for "Manual Review" with what additional information is needed
   - Red card for "Soft Decline" with reasons and what could improve eligibility

**Decision rules**:
- If eligibility score > threshold AND all validations passed → Approve
- If eligibility score < threshold OR critical validation failures → Soft Decline
- If overall confidence < 0.80 OR unresolved discrepancies → Manual Review

**Exit condition**: Decision delivered to applicant.

**Agents**: Eligibility Check Agent, Decision Recommendation Agent.

### Phase 6: Enablement (Conversational)

**Purpose**: Provide personalized recommendations for economic enablement.

**Flow**:
1. Chatbot provides recommendations based on applicant's profile:
   - **Upskilling opportunities**: Training programs matched to resume skills and employment history
   - **Job matching**: Open positions aligned with applicant's experience and location
   - **Career counseling**: Resources for career development, interview preparation
   - **Financial literacy**: Budgeting tools, debt management resources
2. Recommendations rendered as expandable sections in chat
3. Applicant can ask follow-up questions
4. Chatbot provides contact information for relevant government programs
5. Conversation concludes naturally

**Exit condition**: Applicant satisfied or conversation naturally concludes.

**Agent**: Master Orchestrator (uses applicant context from state to generate recommendations).

---

## LangGraph State Model

### State Definition

```python
class ApplicantState(TypedDict):
    # Accumulated messages (add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Phase tracking
    current_phase: str  # "intake" | "document_collection" | "processing" | "review" | "decision" | "enablement"
    phase_completed: dict[str, bool]
    
    # Applicant identity (populated in Phase 1)
    applicant_id: str | None
    identity_number: str | None
    basic_info: dict | None  # name, DOB, nationality, contact, address, marital, family_size, employment, housing, support_category
    
    # Documents (populated in Phase 2)
    uploaded_documents: list[DocumentRef]  # {doc_type, file_path, uploaded_at}
    required_documents: list[str]  # which doc types are needed for this support category
    
    # Processing results (populated in Phase 3)
    extraction_results: dict[str, ExtractionResult]  # keyed by document_id
    validation_results: ValidationSummary  # per-doc + cross-doc validation
    confidence_scores: dict[str, float]
    
    # Review (populated in Phase 4)
    discrepancies: list[Discrepancy]
    discrepancy_resolutions: list[Resolution]
    
    # Decision (populated in Phase 5)
    eligibility_score: float | None
    eligibility_factors: dict | None
    decision: str | None  # "approved" | "soft_decline" | "manual_review"
    decision_explanation: str | None
    
    # Enablement (populated in Phase 6)
    enablement_recommendations: list[Recommendation] | None
```

### Phase Transitions

```
START → intake → document_collection → processing → review → decision → enablement → END
                    ↑                                      |
                    └────── (if new docs uploaded) ────────┘
```

**Transition rules**:
- **Intake → Document Collection**: All required basic_info fields populated
- **Document Collection → Processing**: All required documents uploaded (determined by support_category)
- **Processing → Review**: All documents extracted and validated
- **Review → Decision**: All discrepancies resolved or flagged
- **Review → Document Collection**: If applicant uploads corrected documents (re-process loop)
- **Decision → Enablement**: Decision delivered
- **Enablement → END**: Conversation concludes or applicant has no more questions

---

## Agent Roles

### Master Orchestrator Agent

**Active in**: All phases (runs continuously)

**Role**: The "conductor" that manages the entire workflow. Implemented as the LangGraph state machine itself.

**Responsibilities**:
- Tracks current phase and transitions between phases
- Decides which agent to invoke at each phase
- Manages state (applicant data, documents, results)
- Handles exceptions (e.g., applicant wants to go back, missing documents)
- Coordinates the chatbot interface with backend agents
- Implements the "99% automated" logic — decides when human review is needed

### Data Extraction Agent

**Active in**: Phase 3 (Processing)

**Role**: Extracts structured data from uploaded documents.

**Responsibilities**:
- Receives uploaded documents (PDF, images, XLSX, DOCX)
- Uses ReAct reasoning to decide which extraction tools to call:
  - OCR (PaddleOCR) for scanned documents
  - Table extraction (Camelot) for bank statements, assets/liabilities
  - PDF parsing (PyMuPDF4LLM) for credit reports
  - Resume parsing (SmartResume) for resumes
- Extracts data into PostgreSQL schemas
- Computes field-level confidence scores
- Stores extraction results in `documents` table with `extraction_status`

### Data Validation Agent

**Active in**: Phase 3 (Processing) and Phase 4 (Review)

**Role**: Validates extracted data for consistency and correctness.

**Responsibilities**:
- **Per-document validation** (Phase 3):
  - Runs validation rules from schema spec (Emirates ID checksum, balance reconciliation, credit score range)
  - Checks field-level confidence scores
  - Flags low-confidence extractions for re-extraction or manual review
- **Cross-document validation** (Phase 3-4):
  - Identity match: Emirates ID number consistent across all documents
  - Income consistency: Bank statement salary matches application form
  - Address match: Addresses consistent across documents
  - Employment match: Resume employer matches application form
  - Debt consistency: Credit report balances match assets/liabilities
- **Uses Reflexion reasoning**:
  - Attempt: Initial validation
  - Evaluate: Check if discrepancies are real or extraction errors
  - Critique: Identify root cause (OCR error vs. actual discrepancy)
  - Retry: If confidence is low, request re-extraction or ask applicant for clarification
- Stores validation results in `cross_document_validations` table

### Eligibility Check Agent

**Active in**: Phase 5 (Decision)

**Role**: Computes eligibility score using the ML model.

**Responsibilities**:
- Calls scikit-learn `HistGradientBoostingClassifier`
- Input features: income level, family size, employment history stability, asset/liability ratio, credit score, payment history, demographic profile
- Output: eligibility score (0-1) + feature importance
- Interprets score in context of support category requirements
- Identifies key factors driving the score

### Decision Recommendation Agent

**Active in**: Phase 5 (Decision)

**Role**: Makes the final recommendation and generates explanation.

**Responsibilities**:
- Takes as input: eligibility score, validation results, applicant context, support category requirements
- Makes recommendation: Approve, Soft Decline, or Manual Review
- Generates human-readable explanation:
  - Why the decision was made
  - What factors contributed
  - What could improve eligibility (if declined)
  - Next steps (if approved)
- Uses ReAct reasoning to structure explanation

### Agent Interaction Diagram

```
Applicant (Chat)
    ↓
Master Orchestrator (LangGraph)
    ├─→ Phase 1: Intake (orchestrator collects info directly)
    ├─→ Phase 2: Document Collection (orchestrator manages uploads)
    ├─→ Phase 3: Processing
    │       ├─→ Data Extraction Agent (extracts data)
    │       └─→ Data Validation Agent (validates data)
    ├─→ Phase 4: Review
    │       └─→ Data Validation Agent (helps resolve discrepancies)
    ├─→ Phase 5: Decision
    │       ├─→ Eligibility Check Agent (computes score)
    │       └─→ Decision Recommendation Agent (makes recommendation)
    └─→ Phase 6: Enablement (orchestrator provides recommendations)
```

---

## Streamlit UI Structure

### Page Layout

Single-page Streamlit app with three regions:

```
┌─────────────────────────────────────────────────────┐
│  Header: Logo + "Social Support Application" title  │
├────────────────────────────────────────┬────────────┤
│                                        │            │
│         Chat Area                      │  Sidebar   │
│   (st.chat_message + st.chat_input)    │            │
│                                        │  - Phase   │
│   - User messages                      │    tracker │
│   - Assistant responses                │            │
│   - File upload previews               │  - Docs    │
│   - Inline buttons (approve/decline)   │    status  │
│   - Decision card                      │            │
│   - Enablement recommendations         │  - Status  │
│                                        │    check   │
│                                        │            │
├────────────────────────────────────────┴────────────┤
│  st.chat_input (bottom, accept_file="multiple")     │
└─────────────────────────────────────────────────────┘
```

### Chat Input Configuration

```python
st.chat_input(
    placeholder="Type your message or attach documents...",
    accept_file="multiple",
    file_type=["pdf", "png", "jpg", "jpeg", "xlsx", "docx"],
    submit_mode="disable",  # prevents interrupting LLM responses
)
```

Returns a dict with `.text` and `.files` attributes. The orchestrator inspects both to decide the next action.

### Phase-Specific UI Behavior

**Phase 1 (Intake)**:
- Chat messages are text-only
- Chatbot asks structured questions conversationally
- No file uploads expected yet
- Sidebar shows: "Phase: Intake" with a checklist of required fields

**Phase 2 (Document Collection)**:
- Chatbot messages include document request prompts
- File upload button becomes active in chat input
- When files are uploaded, chat shows preview (file name, size, type)
- Sidebar shows document checklist with status: ✅ uploaded / ⏳ pending / ❌ missing
- Processing indicator appears after upload (using `st.status`)

**Phase 3 (Processing)**:
- Chat shows processing status messages ("Extracting data from your bank statement...")
- Uses `st.status` container with expandable details
- Chat input is disabled during processing (`submit_mode="disable"` handles this)
- Sidebar updates with per-document processing status

**Phase 4 (Review)**:
- Chatbot presents discrepancy findings as structured messages
- Inline buttons for applicant responses: "This is correct" / "I need to correct this"
- If applicant wants to upload corrected docs, file upload re-enables
- Sidebar shows validation status per document

**Phase 5 (Decision)**:
- Decision rendered as a styled card inside `st.chat_message`:
  - Green card for "Approved" with support details
  - Yellow card for "Manual Review" with next steps
  - Red card for "Soft Decline" with reasons
- Explanation follows as regular chat message
- Sidebar shows final decision status

**Phase 6 (Enablement)**:
- Recommendations rendered as expandable sections in chat
- Each recommendation: title, description, relevance to applicant's profile
- Links to government programs (rendered as markdown links)
- Sidebar shows "Application Complete" status

### Performance: Fragment Strategy

The chat area is wrapped in `@st.fragment` to prevent full-page reruns on every widget interaction:

```python
@st.fragment
def chat_fragment():
    # Render chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            render_message(message)
    
    # Chat input
    prompt = st.chat_input(...)
    if prompt:
        handle_input(prompt)
```

Sidebar (phase tracker, doc status) lives outside the fragment — it updates on phase transitions only.

### Status Check Feature (Optional)

Sidebar includes a "Check Application Status" section:
- Text input for Emirates ID
- Button "Check Status"
- Queries PostgreSQL `application_form_data` + `documents` tables
- Shows: application date, current status, decision (if available)

---

## Error Handling and Edge Cases

### Conversation Errors

| Scenario | Handling |
|---|---|
| Applicant provides invalid Emirates ID | Chatbot explains format, asks again. Luhn check runs on every submission. Max 3 attempts before flagging for manual review. |
| Applicant skips required fields | Chatbot gently insists: "I need your contact number to proceed. This is required for your application." |
| Applicant provides contradictory info mid-conversation | Chatbot flags: "Earlier you mentioned you're employed, but now you said unemployed. Which is correct?" |
| Applicant sends irrelevant files (e.g., a photo of their cat) | Chatbot acknowledges receipt, classification agent identifies wrong type, chatbot asks for correct document. |
| Applicant uploads wrong document type for a slot | Chatbot: "This appears to be a resume, but I need your Emirates ID. Could you upload the correct document?" |

### Document Processing Errors

| Scenario | Handling |
|---|---|
| OCR fails on scanned document (low confidence < 0.80) | Extraction agent retries with different OCR settings. If still fails, chatbot asks applicant to upload clearer scan or different format. |
| Document is corrupted or unreadable | Chatbot: "I couldn't read this file. Could you try uploading it again?" |
| Partial extraction (some fields extracted, others failed) | Validation agent identifies missing fields. Chatbot asks applicant to provide missing info conversationally or re-upload. |
| Cross-document discrepancy found | Chatbot presents discrepancy with specifics, asks applicant to clarify or upload corrected document. |
| Applicant uploads corrected document during review | System loops back to Phase 3 for re-processing. Previous extraction results are archived, new ones replace them. |

### System Errors

| Scenario | Handling |
|---|---|
| LLM timeout or failure | Tenacity retry with exponential backoff (3 attempts). If all fail: "I'm experiencing technical difficulties. Please try again in a moment." |
| Database connection failure | LangGraph checkpoint fails gracefully. Chatbot: "I'm having trouble saving your information. Let's try again." |
| Ollama model not loaded | Fallback to StreamLake cloud endpoint if configured. If neither available: clear error message to user. |
| LangGraph recursion limit hit | Orchestrator catches `GraphRecursionError`, escalates to manual review, informs applicant. |

### Applicant Behavior Edge Cases

| Scenario | Handling |
|---|---|
| Applicant wants to go back and change info | Allowed in Phase 1-2. Chatbot updates state, re-validates. If past Phase 3, triggers re-processing. |
| Applicant abandons conversation mid-flow | LangGraph checkpoint persists state. If they return (same session), conversation resumes. |
| Applicant uploads all documents at once | Orchestrator accepts all, classifies each, processes in parallel. No issue — the flow handles this. |
| Applicant has no documents ready | Chatbot explains what's needed, offers to continue with what they have. Can proceed with partial set — decision will be "Manual Review" with a note listing which documents are missing and why they are needed. |
| Applicant is not eligible for any support category | Chatbot explains gently, provides alternative resources, ends conversation gracefully. |

### Confidence-Based Routing

The system uses confidence scores to decide automation vs. human intervention:

| Confidence | Action |
|---|---|
| > 0.95 | Auto-process, no human review needed |
| 0.80 - 0.95 | Auto-process with spot-check flag |
| < 0.80 | Flag for manual review, chatbot explains to applicant |

If the overall application confidence is < 0.80, the decision is "Manual Review" regardless of eligibility score.

---

## Integration with Existing Specs

### Tech Stack Integration

- **LangGraph 1.2.9**: Orchestrates the 6-phase flow with checkpointed state
- **FastAPI 0.139.2**: REST API for document upload, status queries, and decision retrieval
- **Streamlit 1.60**: Chat interface with file upload, fragment-based performance
- **PostgreSQL 17**: Stores applicant data, documents, extraction results, validation results, decisions
- **Qdrant 1.18.0**: Document embeddings for semantic search
- **Neo4j 2026.06.0**: Family relationships and document lineage
- **Ollama + StreamLake**: LLM inference for chatbot and agents
- **Langfuse 4.14.1**: End-to-end observability for all agent actions
- **Scikit-learn 1.9.0**: Eligibility scoring model

### Schema Integration

All data flows through the schemas defined in `2026-07-25-document-processing-schema-design.md`:
- `documents` table tracks all uploaded files
- `emirates_id_data`, `bank_statement_data`, `credit_report_data`, `resume_data`, `assets_liabilities_data`, `application_form_data` store extraction results
- `cross_document_validations` stores validation findings
- `document_audit_log` provides tamper-evident audit trail

### Synthetic Data Integration

The fake data generators defined in `2026-07-25-fake-data-generation-design.md` produce test documents that flow through this user flow:
- Applicant profiles generated with Mimesis
- Emirates ID images with custom generator
- Bank statements with synthetic-statement
- Credit reports with faker-credit-score + reportlab
- Resumes with ResumeCraft
- Assets/liabilities with openpyxl
- Application forms with OCRSmith

---

## Future Improvements

1. **Multi-session support**: Authentication via Emirates ID + PIN, resume conversation from checkpoint
2. **Caseworker dashboard**: Review manual review cases, override decisions, view audit trail
3. **Real-time document preview**: Show applicant a preview of extracted data before submission
4. **Multilingual support**: Chatbot responds in Arabic or English based on applicant preference
5. **Mobile-optimized UI**: Streamlit responsive design for mobile applicants
6. **Voice input**: Streamlit audio input for applicants who prefer speaking
7. **Progressive document upload**: Applicant can upload documents over multiple days before submission
8. **Appeals workflow**: Applicant can appeal decision with additional evidence
9. **Integration with government systems**: API calls to verify Emirates ID, query employment records
10. **Analytics dashboard**: Track application volumes, approval rates, processing times
