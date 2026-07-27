# Repo Presentation Enhancement Design

> **Date:** 2026-07-28  
> **Status:** Approved  
> **Scope:** Optimize repository presentation for case study evaluation and portfolio showcase

---

## Executive Summary

This design enhances the repository's presentation to make evaluation criteria trivially easy to verify while creating a portfolio-quality showcase. The current implementation has all the substance (241+ tests, 5 agents, 4 databases, 7-phase flow) but requires evaluators to hunt for evidence. This design maps every evaluation criterion to an obvious artifact, adds visual polish, and promotes the solution summary to a first-class deliverable.

**Primary goals:**
1. Evaluator can verify all 7 evaluation criteria within 5 minutes of opening the repo
2. README is visually compelling and portfolio-ready
3. Solution summary is prominent and addresses all case study requirements
4. Visual assets demonstrate the working system

---

## Problem Statement: Gap Analysis

### Case Study Requirements vs. Current State

The AI Case Study spec defines **7 evaluation criteria** and **4 submission requirements**. Here's the gap analysis:

#### Evaluation Criteria Gaps

| # | Criterion | Current State | Gap |
|---|-----------|---------------|-----|
| 1 | **Functionality** — addresses all core requirements using recommended tools | All requirements implemented (multimodal processing, 5 agents, reasoning frameworks, local LLM, observability) | No explicit mapping — evaluator must infer from code |
| 2 | **Code Quality** — clean, modular, documented | Four-layer architecture, 241+ tests, DOX framework, ADRs | Evidence is scattered across multiple docs |
| 3 | **Solution Design** — scalable architecture, AI/ML principles | 10-section architecture doc, 6 ADRs, mermaid diagram | Mermaid doesn't render on all GitHub views; ML algorithm justification is thin |
| 4 | **Integration** — effective component integration, APIs, data pipelines | FastAPI endpoints, PostgreSQL/Neo4j/Qdrant integration, Langfuse tracing | Integration story is implicit, not narrated |
| 5 | **Demo UI** — user-friendly | Streamlit chat UI with 7-phase flow, accessibility controls, phase guidance | No screenshots or guided walkthrough in README |
| 6 | **Problem-Solving** — challenges addressed during development | Multiple challenges solved (state management, PII redaction, agent coordination, deterministic gates) | No "Challenges & Solutions" section exists |
| 7 | **Communication** — clear, thorough documentation | README, solution-summary, architecture.md, 6 ADRs, 12 design specs, DOX framework | Documentation is comprehensive but not organized for evaluator navigation |

#### Submission Requirements Gaps

| # | Requirement | Current State | Gap |
|---|-------------|---------------|-----|
| 1 | Source code via private GitHub link | ✅ Complete | None |
| 2 | README.md with clear run instructions | ✅ Complete (213 lines) | Missing evaluator-facing content |
| 3 | Solution summary document (up to 10 pages) | ✅ Complete (`docs/solution-summary.md`) | Buried in `docs/` — should be at root |
| 4 | Specific tool justification for data types (text, images, tabular) | ⚠️ Partial | Tool table covers *why* each tech was chosen, but not *which tool handles which data type* |
| 5 | Scikit-learn algorithm justification | ⚠️ Thin | ML model is a stub; no algorithm choice documented |

#### Missing Artifacts

- **Visual assets** — No screenshots, no rendered architecture diagram, no demo walkthrough
- **Evaluation criterion mapping** — No table linking criteria to repo evidence
- **Challenges narrative** — No section addressing criterion #6
- **Data-type tool justification** — Case study section 4 explicitly asks for this
- **Reasoning framework visibility** — ReAct and Reflexion are implemented but barely mentioned in README

---

## Design Decisions

### Decision 1: README Restructure

**Goal:** Add evaluator-facing content above existing setup instructions without disrupting them.

**New README structure:**

1. **Visual banner**
   - Project title: "UAE Social Support Application — Workflow Automation"
   - One-line description: "AI-driven 7-phase chat-based system for automated social support benefit decisions"
   - Key metrics badges: `5 Agents` `241+ Tests` `4 Databases` `7 Phases` `19 Tools` `6 ADRs`

2. **Evaluation criterion mapping table**
   - 7-row table mapping each case study criterion to where in the repo the evaluator finds it
   - Example row: "Code Quality → `src/` (four-layer architecture), `tests/` (241+ unit tests), `docs/adr/` (6 architecture decision records), `AGENTS.md` (DOX framework)"

3. **Architecture diagram**
   - Rendered PNG from existing mermaid diagram in `solution-summary.md`
   - Stored at `docs/images/architecture.png`
   - Embedded as `![Architecture](docs/images/architecture.png)`

4. **Key highlights section**
   - **Reasoning frameworks:** ReAct (extraction agent), Reflexion (validation agent) — with brief explanation of why each was chosen
   - **Deterministic gates:** 4 gates (document integrity, completeness, eligibility rules, retry logic) for <5ms validation
   - **Multimodal processing:** PDF (pymupdf4llm), images (PaddleOCR), tabular (camelot-py), DOCX (python-docx), XLSX (openpyxl)
   - **ML eligibility:** Scikit-learn pipeline with feature engineering (demographic + financial features)
   - **Observability:** Langfuse v4 traces every LLM call and agent transition

5. **Demo walkthrough**
   - Numbered steps to reproduce the full 7-phase flow in <5 minutes
   - Prerequisites: Docker, Python 3.11.12, Ollama (optional)
   - Steps:
     1. Start infrastructure: `docker compose up -d`
     2. Run migrations: `alembic upgrade head`
     3. Generate test data: `python scripts/generate_test_data.py`
     4. Start backend: `uvicorn src.main:app --reload --port 8000`
     5. Start frontend: `streamlit run ui/streamlit_app.py`
     6. Open `http://localhost:8501`
     7. Login with test Emirates ID (e.g., `784-1990-1234567-8`)
     8. Complete intake (13 fields)
     9. Upload documents from `data/test_applicants/divorced_employed_good_credit/`
     10. Review decision card and enablement recommendations

6. **Challenges & Solutions section**
   - 4-5 real development challenges with how they were solved
   - Examples:
     - **Challenge:** State management across 7 asynchronous phases with document uploads  
       **Solution:** LangGraph `PostgresSaver` checkpointer with `state_snapshot` JSONB column for inspection and recovery
     - **Challenge:** PII egress to third-party LLM APIs  
       **Solution:** Local-first Ollama with StreamLake fallback; structlog PII redaction processor masks identity numbers, names, account numbers
     - **Challenge:** Cross-document consistency validation (identity, income, address across 6 document types)  
       **Solution:** Domain comparison functions (`domain/cross_document.py`) with discrepancy classification (OCR error vs. real discrepancy) and Reflexion loop for low-confidence cases
     - **Challenge:** Agent coordination without tight coupling  
       **Solution:** Four-layer architecture with strict dependency direction (API → Services → Agents → Infrastructure); agents obtain services via dependency injection, not direct imports
     - **Challenge:** Debugging ReAct/Reflexion loops with multiple LLM iterations  
       **Solution:** Langfuse v4 self-hosted tracing with trace-level visibility into every LLM call, agent node transition, and tool invocation

7. **Existing content** (unchanged)
   - Prerequisites
   - Quick Start (8 steps)
   - Running Tests (unit, integration, evals)
   - Architecture Overview (4-layer table)
   - Project Structure (directory table)
   - Configuration (env vars)
   - Troubleshooting (9 common issues)

**Rationale:** Evaluators spend <10 minutes on initial repo review. The evaluator-facing content (criteria table, architecture diagram, highlights, demo walkthrough, challenges) must be above the fold. Existing setup content remains intact for developers who want to run the system.

---

### Decision 2: Promote Solution Summary to Root

**Goal:** Make the solution summary a first-class deliverable, as the case study spec requires.

**Changes:**

1. **Move file:** `docs/solution-summary.md` → `SOLUTION_SUMMARY.md` at repo root
2. **Add section: Data-Type Tool Justification**
   - Case study section 4 explicitly asks: "Select and justify specific tools to handle specific data types (text, images, tabular data)"
   - Current tool table covers *why* each technology was chosen, but not *which tool handles which data type*
   - New section:
     ```
     ## Data-Type Tool Justification
     
     | Data Type | Tool | Justification |
     |-----------|------|---------------|
     | **Text** (PDF, DOCX) | pymupdf4llm, python-docx | pymupdf4llm extracts text + layout from PDFs with high fidelity; python-docx handles DOCX with preserved formatting. Both are pure Python, no external dependencies. |
     | **Images** (PNG, JPG) | PaddleOCR | State-of-the-art OCR for Arabic + English text; handles low-quality scans and handwritten forms. Local inference (no PII egress). |
     | **Tabular** (PDF tables, XLSX) | camelot-py, openpyxl | camelot-py extracts tables from PDFs using lattice/stream detection; openpyxl reads XLSX with full cell-type support. Both preserve table structure for downstream validation. |
     | **Structured data** (JSON) | Pydantic v2 | All agent I/O validated against Pydantic schemas with `field_validator` and `model_validator`. Enforces business rules (Emirates ID length, income thresholds) at parse time. |
     ```

3. **Add section: Scikit-Learn Algorithm Justification**
   - Case study section 4 asks: "Scikit-learn algorithms for classification, explaining your choices based on data characteristics and problem statement"
   - Current ML model is a stub (`src/ml/eligibility_model.py`), but we can document the intended algorithm choice
   - New section:
     ```
     ## Scikit-Learn Algorithm Justification
     
     **Intended algorithm:** Gradient Boosting Classifier (or RandomForest as baseline)
     
     **Rationale based on data characteristics:**
     - **Feature types:** Mixed (demographic: categorical + numerical; financial: continuous). Gradient boosting handles mixed types without extensive preprocessing.
     - **Dataset size:** Synthetic test data is small (<1000 profiles). Gradient boosting performs well on small-to-medium datasets without overfitting (unlike deep learning).
     - **Interpretability requirement:** Government social support decisions must be explainable. Gradient boosting provides feature importance scores (via `feature_importances_`), supporting the "explanation" output in the decision agent.
     - **Class imbalance:** Approval rates may be skewed (e.g., 60% approve, 30% manual review, 10% soft decline). Gradient boosting supports `class_weight` parameter to handle imbalance.
     - **Non-linear relationships:** Income thresholds, residency duration requirements, and family size interactions are non-linear. Tree-based models capture these without manual feature engineering.
     
     **Baseline comparison:** Logistic regression as baseline for interpretability; if performance is comparable, prefer logistic regression for simplicity. Otherwise, gradient boosting.
     
     **Current status:** ML model is a stub in prototype phase. Real model requires training data from historical applications (not available for prototype). Feature engineering pipeline (`src/ml/feature_engineering.py`) is complete and ready for model training.
     ```

4. **Update references:**
   - `README.md`: Change link from `docs/solution-summary.md` to `SOLUTION_SUMMARY.md`
   - `AGENTS.md`: Update Child DOX Index to reflect new location
   - `docs/AGENTS.md`: Remove `solution-summary.md` from Child DOX Index
   - Any internal links in other docs

**Rationale:** The case study spec explicitly requires "a solution summary document (up to 10 pages)" as a submission artifact. Having it in `docs/` makes it feel like an internal doc rather than a deliverable. Moving it to root signals it's a first-class artifact.

---

### Decision 3: Visual Assets

**Goal:** Generate screenshots and architecture diagram to embed in README and solution summary.

**Assets to generate:**

1. **Architecture diagram PNG**
   - Render the existing mermaid diagram from `SOLUTION_SUMMARY.md` as a PNG image
   - Tool: Mermaid CLI (`mmdc`) or online renderer (mermaid.live)
   - Store at: `docs/images/architecture.png`
   - Embed in README: `![Architecture](docs/images/architecture.png)`
   - Embed in SOLUTION_SUMMARY.md: `![Architecture](docs/images/architecture.png)`

2. **Chat UI screenshots**
   - Use Playwright to capture the Streamlit UI at key phases:
     - **Landing page** — Login form with Emirates ID input
     - **Intake phase** — Chat interface with applicant providing personal details
     - **Document upload** — Chat input with file attachments (PDF, PNG)
     - **Decision card** — Approval outcome with explanation and enablement recommendations
     - **Enablement section** — Post-decision recommendations (upskilling, job matching)
   - Store at: `docs/images/ui-*.png` (e.g., `ui-landing.png`, `ui-intake.png`, `ui-upload.png`, `ui-decision.png`, `ui-enablement.png`)
   - Embed in README Demo Walkthrough section

3. **Optional: Animated GIF**
   - Short GIF showing the 7-phase flow end-to-end
   - Lower priority — screenshots cover the same ground
   - If generated, store at `docs/images/demo-flow.gif`

**Storage location:** `docs/images/` directory, referenced by relative paths in markdown.

**Generation method:**
- **Architecture diagram:** Use mermaid CLI or manual rendering from existing mermaid code
- **UI screenshots:** Use `playwright-video-recorder` skill or direct Playwright scripts against the running Streamlit app
- **Prerequisites:** System must be running (backend + frontend + infrastructure)

**Rationale:** Visual assets make the repo immediately more compelling. Evaluators can see the working system without running it. Architecture diagram provides a quick mental model before diving into details.

---

## Implementation Approach

### Phase 1: Documentation Updates (2-3 hours)

1. **Restructure README.md**
   - Add evaluator-facing header (badges, criterion table, architecture diagram, highlights, demo walkthrough, challenges)
   - Preserve existing setup content
   - Update links to point to `SOLUTION_SUMMARY.md`

2. **Promote solution-summary.md**
   - Move `docs/solution-summary.md` → `SOLUTION_SUMMARY.md`
   - Add "Data-Type Tool Justification" section
   - Add "Scikit-Learn Algorithm Justification" section
   - Update all internal references

3. **Update AGENTS.md files**
   - Root `AGENTS.md`: Update Child DOX Index to reflect `SOLUTION_SUMMARY.md` at root
   - `docs/AGENTS.md`: Remove `solution-summary.md` from Child DOX Index

### Phase 2: Visual Asset Generation (1-2 hours)

1. **Architecture diagram**
   - Render mermaid diagram as PNG
   - Store at `docs/images/architecture.png`

2. **UI screenshots**
   - Start system: `docker compose up -d`, `uvicorn src.main:app`, `streamlit run ui/streamlit_app.py`
   - Use Playwright to capture screenshots at each phase
   - Store at `docs/images/ui-*.png`

3. **Optional: Animated GIF**
   - If time permits, generate demo-flow.gif showing the 7-phase flow

### Phase 3: Verification (30 minutes)

1. **Review README**
   - Verify all 7 evaluation criteria are mapped
   - Verify architecture diagram renders
   - Verify all links work

2. **Review SOLUTION_SUMMARY.md**
   - Verify data-type tool justification section is complete
   - Verify scikit-learn algorithm justification is complete
   - Verify page count is ≤10 pages

3. **Review visual assets**
   - Verify all images are clear and correctly labeled
   - Verify images are embedded correctly in README and SOLUTION_SUMMARY.md

---

## Success Criteria

### Evaluator Experience

- [ ] Evaluator can find evidence for all 7 evaluation criteria within 5 minutes
- [ ] README is visually compelling (architecture diagram, screenshots, badges)
- [ ] Solution summary is prominent (at root, not buried in `docs/`)
- [ ] Demo walkthrough is reproducible in <5 minutes

### Portfolio Quality

- [ ] README is suitable for sharing on LinkedIn, portfolio sites, or job applications
- [ ] Architecture diagram is clear and professional
- [ ] Screenshots demonstrate the working system
- [ ] Challenges & Solutions section tells a compelling development story

### Completeness

- [ ] All case study submission requirements are explicitly addressed
- [ ] Data-type tool justification section is complete
- [ ] Scikit-learn algorithm justification is complete (even if ML model is a stub)
- [ ] All internal links are updated

---

## Future Improvements

### Post-Implementation

1. **Video demo** — Record a 2-3 minute video walkthrough of the full 7-phase flow
2. **Interactive demo** — Deploy a public demo (if possible with synthetic data)
3. **Real ML model** — Train the eligibility model on historical data (when available)
4. **Arabic localization** — Add Arabic prompts and RTL UI support
5. **Production deployment guide** — Document production deployment (managed databases, cloud LLM, monitoring)

### Continuous Enhancement

1. **Update screenshots** — Regenerate screenshots when UI changes
2. **Add more challenges** — Expand Challenges & Solutions section as new challenges arise
3. **Add testimonials** — If the system is used in production, add user testimonials
4. **Add metrics** — Track and display real metrics (e.g., "99% automation rate", "5-minute decision time")

---

## Appendix: Evaluation Criterion Mapping

This table will be embedded in the README:

| # | Evaluation Criterion | Where to Find Evidence |
|---|----------------------|------------------------|
| 1 | **Functionality** — addresses all core requirements | `SOLUTION_SUMMARY.md` (architecture diagram, data flow), `src/agents/` (5 agents), `src/infrastructure/document_processing/` (multimodal processing), `src/ml/` (ML eligibility) |
| 2 | **Code Quality** — clean, modular, documented | `src/` (four-layer architecture), `tests/` (241+ unit tests), `docs/adr/` (6 architecture decision records), `AGENTS.md` (DOX framework), `docs/architecture.md` (10-section architecture doc) |
| 3 | **Solution Design** — scalable architecture, AI/ML principles | `SOLUTION_SUMMARY.md` (tool justification, modular breakdown), `docs/architecture.md` (data flow, state persistence), `docs/adr/` (design decisions), `src/ml/feature_engineering.py` (ML pipeline) |
| 4 | **Integration** — effective component integration, APIs, data pipelines | `src/api/v1/` (FastAPI endpoints), `src/infrastructure/db/` (PostgreSQL), `src/infrastructure/graph/` (Neo4j), `src/infrastructure/vector/` (Qdrant), `src/infrastructure/observability/` (Langfuse tracing) |
| 5 | **Demo UI** — user-friendly | `ui/` (Streamlit chat UI), `docs/images/ui-*.png` (screenshots), Demo Walkthrough section below |
| 6 | **Problem-Solving** — challenges addressed | Challenges & Solutions section below |
| 7 | **Communication** — clear, thorough documentation | `README.md`, `SOLUTION_SUMMARY.md`, `docs/architecture.md`, `docs/adr/` (6 ADRs), `docs/superpowers/specs/` (12 design specs), `AGENTS.md` (DOX framework) |

---

*Design approved: 2026-07-28*
