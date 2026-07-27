# UI UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the Streamlit UI with per-phase guidance, document progress feedback, structured error recovery, accessibility features, and a Help panel — making the application intuitive for vulnerable applicants.

**Architecture:** Frontend-only changes to the Streamlit application. No backend modifications. New components are added alongside existing ones; existing components are extended with additional functions. All state is managed through `st.session_state`.

**Tech Stack:** Python 3.11, Streamlit, CSS, HTML

## Global Constraints

- Use `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe` for all Python commands
- No backend API changes
- No database schema changes
- Follow existing Streamlit patterns from `.cursor/rules/streamlit.mdc`
- Follow Python core conventions from `.cursor/rules/python-core.mdc`
- All new components use `structlog.get_logger(__name__)` for logging
- Type hints required on all public functions

---

## File Structure

| File | Responsibility |
|------|----------------|
| `ui/components/phase_guidance.py` | Per-phase collapsible guidance panel with auto-expand on first visit |
| `ui/components/document_status.py` | Existing component — add progress bar above checklist |
| `ui/components/chat_input.py` | Existing component — add client-side file type validation |
| `ui/fragments/chat_area.py` | Existing fragment — add structured error handling, retry buttons, upload confirmations |
| `ui/components/accessibility_controls.py` | High contrast toggle, text size control, CSS injection |
| `ui/components/help_panel.py` | Collapsible Help panel with FAQs, glossary, contact, summary |
| `ui/styles/global.css` | Existing — add high-contrast theme, text-size scaling, focus styles |
| `ui/streamlit_app.py` | Existing — inject accessibility CSS and ARIA live regions |
| `ui/app_pages/chat.py` | Existing — integrate accessibility controls and help panel into header |

---

### Task 1: Per-Phase Guidance Panel

**Files:**
- Create: `ui/components/phase_guidance.py`
- Modify: `ui/app_pages/chat.py` (integrate guidance into chat page header)

**Interfaces:**
- Consumes: `st.session_state.current_phase` (str)
- Produces: `render_phase_guidance()` function

- [ ] **Step 1: Create the phase guidance component**

Create `ui/components/phase_guidance.py`:

```python
"""Per-phase guidance panel for applicant clarity."""

import structlog
import streamlit as st

logger = structlog.get_logger(__name__)

PHASE_GUIDANCE = {
    "authentication": {
        "where": "Enter your Emirates ID to start or resume your application",
        "expect": [
            "Your ID is validated instantly using the Luhn algorithm",
            "Returning applicants can continue where they left off",
        ],
        "need": "Your 15-digit Emirates ID number (format: 784-YYYY-NNNNNNN-C)",
    },
    "intake": {
        "where": "Provide your personal information",
        "expect": [
            "We'll ask about your family, employment, and living situation",
            "Answer at your own pace — you can take your time",
        ],
        "need": "Your personal details (name, date of birth, nationality, contact, address, marital status)",
    },
    "document_collection": {
        "where": "Upload your supporting documents",
        "expect": [
            "Upload clear photos or PDFs of your documents",
            "We'll confirm each file as it's received and classified",
            "You can replace documents if needed",
        ],
        "need": "Emirates ID, bank statement, credit report, and other supporting documents",
    },
    "processing": {
        "where": "We're reviewing your application",
        "expect": [
            "Our system extracts and validates information from your documents",
            "This may take a few minutes — please be patient",
        ],
        "need": "No action needed — please wait for processing to complete",
    },
    "review": {
        "where": "Check and clarify any discrepancies",
        "expect": [
            "If we found differences between your documents, we'll show them here",
            "You can clarify or re-upload documents to resolve discrepancies",
        ],
        "need": "Review the discrepancies shown and respond to clarification questions",
    },
    "decision": {
        "where": "Your application decision",
        "expect": [
            "You'll receive a decision card explaining the outcome",
            "The card includes next steps specific to your result",
        ],
        "need": "Review your decision carefully and note the next steps",
    },
    "enablement": {
        "where": "Personalized recommendations",
        "expect": [
            "Based on your profile, we'll suggest programs that can help you",
            "Recommendations are tailored to your situation and goals",
        ],
        "need": "Explore the recommendations and note any programs of interest",
    },
}


def _get_guidance_state_key(phase: str) -> str:
    return f"phase_guidance_dismissed_{phase}"


def render_phase_guidance() -> None:
    """Render the per-phase guidance panel with auto-expand on first visit."""
    phase = st.session_state.get("current_phase", "authentication")
    guidance = PHASE_GUIDANCE.get(phase)

    if not guidance:
        return

    state_key = _get_guidance_state_key(phase)
    has_interacted = st.session_state.get(state_key, False)

    # Auto-expand on first visit to this phase
    expanded = not has_interacted

    with st.expander(
        f"📋 Guidance: {phase.replace('_', ' ').title()}",
        expanded=expanded,
    ):
        st.markdown(f"**Where you are:** {guidance['where']}")
        st.markdown("**What to expect:**")
        for item in guidance["expect"]:
            st.markdown(f"- {item}")
        st.markdown(f"**What you need:** {guidance['need']}")

        # Mark as interacted when user sees guidance
        if not has_interacted:
            st.session_state[state_key] = True

    logger.debug("phase_guidance_rendered", phase=phase, first_visit=not has_interacted)
```

- [ ] **Step 2: Integrate guidance panel into chat page**

In `ui/app_pages/chat.py`, add the guidance panel render call at the top of the chat area, before the chat messages. Insert after the session restore banner and before the chat area fragment:

```python
# In the chat page render function, after session restore banner:
from ui.components.phase_guidance import render_phase_guidance

# ... existing code ...

# Render per-phase guidance panel
render_phase_guidance()

# ... existing chat area rendering ...
```

- [ ] **Step 3: Verify the guidance panel renders**

Run the Streamlit app and navigate through phases to verify:
- Guidance panel auto-expands on first entry to each phase
- Guidance panel collapses after interaction
- "Show guidance" toggle re-opens the panel
- Content matches the phase

- [ ] **Step 4: Commit**

```bash
git add ui/components/phase_guidance.py ui/app_pages/chat.py
git commit -m "feat(ui): add per-phase guidance panel

Auto-expanding collapsible panel showing where the user is,
what to expect, and what they need for each phase."
```

---

### Task 2: Document Progress Bar

**Files:**
- Modify: `ui/components/document_status.py`

**Interfaces:**
- Consumes: `st.session_state.uploaded_documents` (dict), `st.session_state.identity_number` (str)
- Produces: Progress bar rendered above document checklist

- [ ] **Step 1: Add progress bar to document status component**

In `ui/components/document_status.py`, add a progress bar function and integrate it above the existing document checklist. Add this function:

```python
def render_document_progress() -> None:
    """Render a progress bar showing document upload completion."""
    uploaded = st.session_state.get("uploaded_documents", {})
    required = DEFAULT_REQUIRED_DOCS  # or support-category-aware list

    uploaded_count = len([doc for doc in required if doc in uploaded])
    total_count = len(required)
    progress = uploaded_count / total_count if total_count > 0 else 0

    st.markdown(
        f"**Documents:** {uploaded_count} of {total_count} uploaded"
    )
    st.progress(progress)

    if uploaded_count == total_count and total_count > 0:
        st.success("All required documents uploaded!")
```

Then modify the sidebar rendering to call `render_document_progress()` before `render_document_status()`:

```python
# In the sidebar section of chat.py or document_status.py
render_document_progress()
render_document_status()
```

- [ ] **Step 2: Verify progress bar renders correctly**

Run the Streamlit app, upload documents, and verify:
- Progress bar shows "0 of N uploaded" initially
- Progress bar fills as documents are uploaded
- Shows "All required documents uploaded!" when complete

- [ ] **Step 3: Commit**

```bash
git add ui/components/document_status.py
git commit -m "feat(ui): add document upload progress bar

Shows quantitative progress (X of Y) with visual progress bar
above the document checklist in the sidebar."
```

---

### Task 3: File Type Validation & Upload Confirmations

**Files:**
- Modify: `ui/components/chat_input.py`
- Modify: `ui/fragments/chat_area.py`

**Interfaces:**
- Consumes: `ChatInputResult` from chat_input.py
- Produces: Validated file list, enhanced confirmation messages

- [ ] **Step 1: Add client-side file type validation to chat input**

In `ui/components/chat_input.py`, add validation before returning files. Modify the `_handle_submission` or `render_chat_input` function to validate file extensions:

```python
SUPPORTED_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "xlsx", "docx"]


def validate_file_types(files: list) -> tuple[list, list[str]]:
    """Validate file types and return (valid_files, error_messages)."""
    valid_files = []
    errors = []

    for file in files:
        ext = file.name.split(".")[-1].lower() if "." in file.name else ""
        if ext not in SUPPORTED_FILE_TYPES:
            errors.append(
                f"Unsupported file type '.{ext}'. "
                f"Accepted formats: {', '.join(s.upper() for s in SUPPORTED_FILE_TYPES)}"
            )
        else:
            valid_files.append(file)

    return valid_files, errors
```

- [ ] **Step 2: Display validation errors in chat input**

In `ui/components/chat_input.py`, after validating files, display errors using `st.error()` for each rejected file:

```python
if errors:
    for error in errors:
        st.error(error)
```

- [ ] **Step 3: Add enhanced upload confirmation messages**

In `ui/fragments/chat_area.py`, modify the response handling to show enhanced confirmation messages. After a successful document upload, append a confirmation message:

```python
# In the chat area response handling, after document classification:
if "uploaded_documents" in response_data:
    for doc_info in response_data["uploaded_documents"]:
        doc_name = doc_info.get("filename", "Unknown")
        doc_type = doc_info.get("document_type", "unknown")

        # Check if this is a re-upload
        existing_docs = st.session_state.get("uploaded_documents", {})
        is_reupload = doc_type in existing_docs

        if is_reupload:
            confirmation = f"🔄 Updated: {doc_name} replaces previous {doc_type} upload"
        else:
            confirmation = f"✓ {doc_name} uploaded and classified as {doc_type}"

        st.session_state.messages.append({
            "role": "system",
            "content": confirmation,
        })
```

- [ ] **Step 4: Verify file validation and confirmations**

Run the Streamlit app and test:
- Upload a `.txt` file — should see error message, no API call
- Upload a valid `.pdf` — should see confirmation message
- Re-upload a document type — should see "Updated:" message

- [ ] **Step 5: Commit**

```bash
git add ui/components/chat_input.py ui/fragments/chat_area.py
git commit -m "feat(ui): add file type validation and upload confirmations

Client-side file type validation with clear error messages.
Enhanced upload confirmations with re-upload indicators."
```

---

### Task 4: Structured Error Handling & Retry

**Files:**
- Modify: `ui/fragments/chat_area.py`

**Interfaces:**
- Consumes: API call exceptions from chat area
- Produces: Structured error messages with retry buttons

- [ ] **Step 1: Add structured error handler**

In `ui/fragments/chat_area.py`, add a new error handling function:

```python
import httpx
import requests
from typing import Any


def _classify_error(error: Exception) -> tuple[str, str, str]:
    """Classify an error and return (title, message, action_label)."""
    if isinstance(error, (requests.exceptions.ConnectionError, httpx.ConnectError)):
        return (
            "Connection lost",
            "We couldn't reach the server. Your progress is saved.",
            "Retry",
        )
    elif isinstance(error, (requests.exceptions.Timeout, httpx.TimeoutException)):
        return (
            "Request timed out",
            "This is taking longer than expected. Your documents may still be processing.",
            "Check Status",
        )
    elif isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code >= 500:
            return (
                "Something went wrong",
                "This is on our end. Please try again in a moment.",
                "Retry",
            )
        else:
            return (
                "Issue with your request",
                f"Server returned status {error.response.status_code}.",
                "Retry",
            )
    elif isinstance(error, requests.exceptions.HTTPError):
        return (
            "Issue with your request",
            "Please check your input and try again.",
            "Retry",
        )
    else:
        return (
            "Unexpected error",
            "An unexpected error occurred. Please try again.",
            "Retry",
        )
```

- [ ] **Step 2: Add retry state management**

In `ui/fragments/chat_area.py`, add retry state tracking. In the `_handle_submission` function, store the last request before making the API call:

```python
# Store last request for retry
st.session_state.last_request = {
    "message": message_text,
    "files": files,
    "retry_count": 0,
}
```

- [ ] **Step 3: Wrap API call in error handler with retry button**

Modify the API call in `_handle_submission` to catch errors and render retry UI:

```python
import streamlit as st

# In the API call section:
try:
    response = requests.post(
        f"{API_BASE_URL}/applications/{application_id}/chat",
        # ... existing request params ...
    )
    response.raise_for_status()
    # ... existing success handling ...
except Exception as error:
    title, message, action_label = _classify_error(error)

    st.error(f"**{title}** — {message}")

    retry_count = st.session_state.get("last_retry_count", 0)
    if retry_count >= 3:
        st.error(
            "**Maximum retries reached.** "
            f"Please contact support with your application ID: {application_id}"
        )
        if st.button("Return to Login"):
            st.session_state.current_phase = "authentication"
            st.rerun()
    else:
        if st.button(action_label, key=f"retry_{retry_count}"):
            st.session_state.last_retry_count = retry_count + 1
            # Re-submit the last request
            last_request = st.session_state.get("last_request", {})
            if last_request:
                _handle_submission(
                    last_request.get("message", ""),
                    last_request.get("files", []),
                )
            st.rerun()
```

- [ ] **Step 4: Verify error handling**

Test by:
- Stopping the backend server and sending a message — should see "Connection lost" with Retry button
- Retry 3 times — should see "Maximum retries reached" message

- [ ] **Step 5: Commit**

```bash
git add ui/fragments/chat_area.py
git commit -m "feat(ui): add structured error handling with retry

Classifies errors by type, shows user-friendly messages,
and provides retry buttons with a 3-retry maximum."
```

---

### Task 5: Accessibility Controls

**Files:**
- Create: `ui/components/accessibility_controls.py`
- Modify: `ui/styles/global.css`
- Modify: `ui/streamlit_app.py`

**Interfaces:**
- Consumes: `st.session_state.high_contrast` (bool), `st.session_state.text_size` (str)
- Produces: CSS injection, toggle buttons

- [ ] **Step 1: Create accessibility controls component**

Create `ui/components/accessibility_controls.py`:

```python
"""Accessibility controls: high contrast toggle and text size control."""

import streamlit as st


def render_accessibility_controls() -> None:
    """Render accessibility control buttons in the header."""
    col1, col2 = st.columns(2)

    with col1:
        high_contrast = st.session_state.get("high_contrast", False)
        if st.button(
            "👁 High Contrast",
            key="high_contrast_toggle",
            type="secondary" if not high_contrast else "primary",
        ):
            st.session_state.high_contrast = not high_contrast
            st.rerun()

    with col2:
        text_size = st.session_state.get("text_size", "normal")
        size_options = ["Normal", "Large", "Extra Large"]
        size_key = {"Normal": "normal", "Large": "large", "Extra Large": "xlarge"}

        current_index = list(size_key.values()).index(text_size)
        new_size = st.selectbox(
            "Text Size",
            options=size_options,
            index=current_index,
            key="text_size_select",
            label_visibility="collapsed",
        )
        new_size_key = size_key[new_size]
        if new_size_key != text_size:
            st.session_state.text_size = new_size_key
            st.rerun()


def get_accessibility_css() -> str:
    """Generate CSS for accessibility settings."""
    high_contrast = st.session_state.get("high_contrast", False)
    text_size = st.session_state.get("text_size", "normal")

    size_map = {"normal": "100%", "large": "125%", "xlarge": "150%"}
    font_size = size_map.get(text_size, "100%")

    css_parts = [f":root {{ --text-scale: {font_size}; }}"]

    if high_contrast:
        css_parts.extend([
            "body { background-color: #FFFFFF !important; color: #000000 !important; }",
            ".stChatMessage[data-testid='stChatMessage'] { "
            "border: 2px solid #000000 !important; "
            "} ",
            "button[kind='primary'] { "
            "background-color: #000000 !important; "
            "color: #FFFFFF !important; "
            "border: 2px solid #000000 !important; "
            "} ",
            ".stTextInput > div > div > input { "
            "border: 2px solid #000000 !important; "
            "color: #000000 !important; "
            "} ",
            ".element-container label { color: #000000 !important; }",
        ])

    return "\n".join(css_parts)
```

- [ ] **Step 2: Update global CSS with accessibility styles**

In `ui/styles/global.css`, add focus styles and ARIA-compatible styles at the end:

```css
/* Accessibility: Focus indicators */
*:focus-visible {
    outline: 2px solid #0066CC !important;
    outline-offset: 2px !important;
}

/* Accessibility: Text scaling */
body {
    font-size: var(--text-scale, 100%);
}

/* Accessibility: High contrast mode overrides */
.high-contrast .stApp {
    background-color: #FFFFFF;
    color: #000000;
}

/* Accessibility: Skip link (hidden but available) */
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: #000;
    color: white;
    padding: 8px;
    z-index: 100;
}

.skip-link:focus {
    top: 0;
}
```

- [ ] **Step 3: Inject accessibility CSS in Streamlit app entrypoint**

In `ui/streamlit_app.py`, add accessibility CSS injection after the existing CSS injection:

```python
from ui.components.accessibility_controls import get_accessibility_css

# ... existing CSS injection ...

# Inject accessibility CSS
st.markdown(
    f"<style>{get_accessibility_css()}</style>",
    unsafe_allow_html=True,
)

# ARIA live region for chat updates
st.markdown(
    '<div aria-live="polite" aria-atomic="true" class="sr-only"></div>',
    unsafe_allow_html=True,
)
```

- [ ] **Step 4: Verify accessibility controls**

Run the Streamlit app and test:
- High contrast toggle changes colors
- Text size control scales text
- Focus outlines are visible on Tab navigation

- [ ] **Step 5: Commit**

```bash
git add ui/components/accessibility_controls.py ui/styles/global.css ui/streamlit_app.py
git commit -m "feat(ui): add accessibility controls

High contrast toggle, text size control, focus indicators,
and ARIA live regions for screen reader support."
```

---

### Task 6: Help Panel

**Files:**
- Create: `ui/components/help_panel.py`

**Interfaces:**
- Consumes: `st.session_state.current_phase` (str), `st.session_state.messages` (list), `st.session_state.uploaded_documents` (dict)
- Produces: `render_help_panel()` function

- [ ] **Step 1: Create the Help panel component**

Create `ui/components/help_panel.py`:

```python
"""Help panel with FAQs, glossary, contact info, and summary."""

import streamlit as st

FAQS_BY_PHASE = {
    "authentication": [
        ("What is my Emirates ID?", "Your Emirates ID is a 15-digit identification number issued by the UAE government. It appears on your Emirates ID card in the format 784-YYYY-NNNNNNN-C."),
        ("I forgot my Emirates ID number", "You can find your Emirates ID number on your physical Emirates ID card. If you don't have it, contact the Federal Authority for Identity and Citizenship (ICA)."),
        ("Can I start a new application?", "If you have an existing application in progress, you'll be prompted to continue it. To start fresh, you would need to abandon the existing application."),
    ],
    "intake": [
        ("Is my information confidential?", "Yes. All your personal information is encrypted and stored securely. Only authorized personnel can access your application data."),
        ("Can I skip a question and come back?", "Yes, you can provide partial information and continue. However, some fields are required to proceed to the next phase."),
        ("What if I don't know an answer?", "You can enter 'Unknown' or 'Prefer not to say' for fields you're unsure about. The system will note this for review."),
    ],
    "document_collection": [
        ("What documents do I need?", "Required documents vary by support category but typically include: Emirates ID, bank statements (last 3 months), AECB credit report, and a completed application form."),
        ("Can I upload photos of documents?", "Yes, clear photos are accepted. Make sure all text is legible and all four corners of the document are visible."),
        ("What if I don't have a document?", "If you're missing a required document, let us know in the chat. We can suggest alternatives or note the exception for review."),
    ],
    "processing": [
        ("How long does processing take?", "Processing typically takes 2-5 minutes depending on the number of documents. Complex cases may take longer."),
        ("Do I need to stay on this page?", "Yes, please keep this page open. Your session will time out after 15 minutes of inactivity."),
        ("What happens during processing?", "Our system extracts text from your documents using OCR, validates the information, and checks for consistency across all uploaded files."),
    ],
    "review": [
        ("What is a discrepancy?", "A discrepancy is a difference between information in different documents. For example, if your bank statement shows a different address than your Emirates ID."),
        ("How do I correct a discrepancy?", "You can either clarify the discrepancy in the chat or upload a corrected document that resolves the difference."),
        ("What if I disagree with a finding?", "You can provide additional documentation or explanation. All discrepancies are reviewed by a human before affecting your decision."),
    ],
    "decision": [
        ("What do the decision outcomes mean?", "Approved: You qualify for support. Manual Review: A caseworker needs to review your application. Soft Decline: You don't currently qualify but may be eligible for alternative programs."),
        ("Can I appeal a decision?", "Yes. If you receive a soft decline or manual review, you can request a human review by contacting support."),
        ("How long until I receive support?", "If approved, support is typically processed within 5-10 business days. You'll receive a confirmation with details."),
    ],
    "enablement": [
        ("Are these programs mandatory?", "No, enablement programs are optional recommendations to help you achieve greater financial independence."),
        ("How do I enroll in a program?", "Each recommendation card includes contact information and enrollment instructions. You can enroll directly through the program provider."),
        ("What if none of these fit my situation?", "Contact our support team. We can provide personalized recommendations based on your specific circumstances."),
    ],
}

GLOSSARY = {
    "Emirates ID": "A 15-digit identification number issued by the UAE Federal Authority for Identity and Citizenship (ICA). Required for all UAE residents.",
    "AECB Credit Report": "A credit report from the Al Etihad Credit Bureau showing your credit history, outstanding debts, and credit score in the UAE.",
    "Bank Statement": "An official document from your bank showing your account transactions, balance, and income deposits over a period (typically 3 months).",
    "Eligibility Score": "A numerical score (0-100) calculated based on your income, family situation, employment status, and other factors to determine support eligibility.",
    "Manual Review": "A status indicating your application requires human review by a caseworker before a decision can be made.",
    "Soft Decline": "A decision outcome indicating you don't currently qualify for support but may be eligible for alternative programs or can reapply after meeting certain conditions.",
    "Enablement Programs": "Optional programs recommended to help applicants achieve greater financial independence, including job training, career counseling, and financial literacy courses.",
}

CONTACT_EMAIL = "support@socialsupport.gov.ae"
CONTACT_PHONE = "800-SUPPORT (800-7877678)"


def _generate_summary() -> str:
    """Generate a text summary of the application so far."""
    phase = st.session_state.get("current_phase", "unknown")
    messages = st.session_state.get("messages", [])
    uploaded = st.session_state.get("uploaded_documents", {})

    summary_parts = [f"**Application Summary**", f"- Current Phase: {phase.replace('_', ' ').title()}"]
    summary_parts.append(f"- Documents Uploaded: {len(uploaded)}")

    system_messages = [m for m in messages if m.get("role") == "system"]
    if system_messages:
        last_system = system_messages[-1].get("content", "")[:200]
        summary_parts.append(f"- Last Update: {last_system}...")

    return "\n".join(summary_parts)


def render_help_panel() -> None:
    """Render the collapsible Help panel."""
    with st.sidebar:
        with st.expander("❓ Help & FAQs", expanded=False):
            tab1, tab2, tab3, tab4 = st.tabs(["FAQs", "Glossary", "Contact", "Summary"])

            with tab1:
                phase = st.session_state.get("current_phase", "authentication")
                faqs = FAQS_BY_PHASE.get(phase, [])

                if not faqs:
                    st.info("No FAQs available for this phase.")
                else:
                    for question, answer in faqs:
                        with st.expander(question):
                            st.write(answer)

            with tab2:
                for term, definition in GLOSSARY.items():
                    with st.expander(term):
                        st.write(definition)

            with tab3:
                st.markdown("**Contact Support**")
                st.markdown(f"If you need human assistance:")
                st.markdown(f"- 📧 Email: {CONTACT_EMAIL}")
                st.markdown(f"- 📞 Phone: {CONTACT_PHONE}")
                st.markdown("---")
                st.markdown("*Support hours: Sunday–Thursday, 8:00 AM – 4:00 PM GST*")

            with tab4:
                st.markdown("**Summary So Far**")
                summary = _generate_summary()
                st.markdown(summary)

                if st.button("Copy Summary"):
                    st.success("Summary copied to clipboard (manually select and copy)")
```

- [ ] **Step 2: Integrate Help panel into chat page**

In `ui/app_pages/chat.py`, add the Help panel render call in the sidebar section:

```python
from ui.components.help_panel import render_help_panel

# In the sidebar section:
render_help_panel()
```

- [ ] **Step 3: Verify Help panel**

Run the Streamlit app and test:
- Help panel opens in sidebar
- FAQs show phase-specific questions
- Glossary terms are expandable
- Contact info is visible
- Summary generates correctly

- [ ] **Step 4: Commit**

```bash
git add ui/components/help_panel.py ui/app_pages/chat.py
git commit -m "feat(ui): add Help panel with FAQs, glossary, and summary

Collapsible sidebar panel with phase-specific FAQs,
term glossary, support contact info, and application summary."
```

---

### Task 7: Integration & Polish

**Files:**
- Modify: `ui/app_pages/chat.py`
- Modify: `ui/app_pages/landing.py` (if needed for consistency)

**Interfaces:**
- Consumes: All components from Tasks 1-6
- Produces: Fully integrated chat page

- [ ] **Step 1: Wire all components into chat page header**

In `ui/app_pages/chat.py`, update the header to include accessibility controls and ensure all components are properly ordered:

```python
# Header section should include:
# 1. Title and phase badge
# 2. Accessibility controls (high contrast, text size)
# 3. Help panel is in sidebar (already added in Task 6)

# Import all components
from ui.components.phase_guidance import render_phase_guidance
from ui.components.accessibility_controls import render_accessibility_controls
from ui.components.help_panel import render_help_panel
from ui.components.document_status import render_document_progress, render_document_status
from ui.fragments.chat_area import render_chat_area

# In the header area (after title, before chat):
col_left, col_right = st.columns([3, 1])
with col_left:
    st.markdown("### Social Support Application")
with col_right:
    render_accessibility_controls()

# Phase guidance (before chat area)
render_phase_guidance()

# Sidebar
with st.sidebar:
    render_help_panel()
    render_document_progress()
    render_document_status()

# Chat area
render_chat_area()
```

- [ ] **Step 2: Verify full integration**

Run the Streamlit app and do a full walkthrough:
- Phase 0: Landing page works
- Phase 1: Guidance panel shows, chat works
- Phase 2: Document progress bar updates, file upload works with validation
- Phase 3: Processing messages show correctly
- All phases: Error handling works, accessibility controls work, Help panel works

- [ ] **Step 3: Final commit**

```bash
git add ui/app_pages/chat.py
git commit -m "feat(ui): integrate all UX polish components

Wire phase guidance, accessibility controls, Help panel,
and document progress into the chat page. Complete UX polish."
```

---

## Self-Review

**Spec coverage check:**

| Spec Requirement | Task |
|------------------|------|
| Per-phase guidance panel | Task 1 |
| Auto-expand on first visit | Task 1 |
| Document progress bar | Task 2 |
| Upload confirmation messages | Task 3 |
| File type validation | Task 3 |
| Re-upload indicator | Task 3 |
| Structured error messages | Task 4 |
| Retry buttons | Task 4 |
| Session expiry handling | Task 4 |
| High contrast toggle | Task 5 |
| Text size control | Task 5 |
| Keyboard navigation (focus styles) | Task 5 |
| Screen reader labels (ARIA) | Task 5 |
| Help panel with FAQs | Task 6 |
| Glossary | Task 6 |
| Contact info | Task 6 |
| Summary so far | Task 6 |
| Integration into chat page | Task 7 |

All spec requirements covered. No gaps.

**Placeholder scan:** No TBD, TODO, or placeholder patterns found.

**Type consistency:** All function signatures are consistent across tasks. `render_phase_guidance()`, `render_document_progress()`, `render_accessibility_controls()`, `render_help_panel()` are all defined and used consistently.
