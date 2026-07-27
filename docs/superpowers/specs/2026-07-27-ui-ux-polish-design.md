# UI UX Polish Design — Structured Guidance for Vulnerable Applicants

**Date:** 2026-07-27
**Status:** Approved
**Scope:** Frontend-only UX improvements to the Streamlit application

---

## Executive Summary

The Social Support Application UI is functionally complete but lacks the guidance and feedback mechanisms that vulnerable applicants (divorced individuals, abandoned spouses, persons of unknown parentage, disabled applicants) need to complete the 7-phase flow with confidence. This spec defines five UX improvements that address progress clarity, error recovery, document feedback, and accessibility — all within the existing Streamlit framework with no backend changes.

---

## Problem Statement

Live testing and design review identified three root causes of applicant anxiety:

1. **Progress uncertainty** — Users don't know where they are in the process, what's coming next, or how much is left
2. **Opaque document handling** — No confirmation that uploads were received, no progress toward document requirements, no feedback on rejected files
3. **Dead-end errors** — Errors appear as cryptic messages with no recovery path, leaving users stuck

Additionally, the UI has zero accessibility features, excluding applicants with visual impairments or low tech literacy.

---

## Design Principles

- **Clarity over cleverness** — Every screen tells the user where they are, what to do, and what happens next
- **Recovery, not failure** — Every error has a clear explanation and an actionable next step
- **Progressive disclosure** — Guidance is available but not intrusive; auto-expands on first visit, collapses after interaction
- **Inclusive by default** — Accessibility features are built in, not bolted on

---

## Per-Section Design

### Section 1: Per-Phase Guidance Panel

**Purpose:** Eliminate progress uncertainty by showing users exactly where they are and what to expect.

**Behavior:**
- Collapsible panel rendered at the top of the chat area (above messages)
- Auto-expands on first entry to each phase, collapses after user's first interaction
- "Show guidance" toggle always visible to re-open
- Three sections per phase:
  - **Where you are** — phase name and one-sentence description
  - **What to expect** — 2-3 bullet points about system behavior
  - **What you need** — specific items required (e.g., "Emirates ID, bank statement PDF")

**Content by phase:**

| Phase | Where You Are | What to Expect | What You Need |
|-------|---------------|----------------|---------------|
| 0 — Authentication | Enter your Emirates ID to start or resume your application | Your ID is validated instantly. Returning applicants can continue where they left off | Your 15-digit Emirates ID number |
| 1 — Intake | Provide your personal information | We'll ask about your family, employment, and living situation. Answer at your own pace | Your personal details ready |
| 2 — Document Collection | Upload your supporting documents | Upload clear photos or PDFs. We'll confirm each file as it's received | Emirates ID, bank statement, credit report, and other documents |
| 3 — Processing | We're reviewing your application | Our system extracts and validates information from your documents. This may take a few minutes | No action needed — please wait |
| 4 — Review | Check and clarify any discrepancies | If we found differences between your documents, we'll ask you to clarify or re-upload | Review the discrepancies shown |
| 5 — Decision | Your application decision | You'll receive a decision card explaining the outcome and next steps | Review your decision carefully |
| 6 — Enablement | Personalized recommendations | Based on your profile, we'll suggest programs that can help you | Explore the recommendations |

**Implementation:**
- New file: `ui/components/phase_guidance.py`
- `render_phase_guidance(phase: str, has_interacted: bool) -> None`
- Phase content stored in a module-level dictionary
- State tracked in `st.session_state.phase_guidance_dismissed[phase]`
- No backend changes

---

### Section 2: Document Progress & Feedback

**Purpose:** Give users clear, quantitative feedback on document upload progress and file handling.

**Changes:**

**2a — Progress bar in sidebar**
- Added above the document checklist in `document_status.py`
- Shows "X of Y required documents uploaded" with a visual progress bar
- Bar fills proportionally (green for completed, gray for remaining)
- Updates reactively when documents are uploaded

**2b — Upload confirmation messages**
- When a document is successfully classified, append an inline confirmation in chat
- Format: "✓ [Document name] uploaded and classified as [document type]"
- Distinguish from system messages with a subtle green checkmark icon

**2c — File type validation**
- Before sending to API, validate file extension against allowed types
- Rejected files show: "Unsupported file type ([.ext]). Accepted formats: PDF, PNG, JPG, XLSX, DOCX"
- Validation happens client-side — no API call for rejected files

**2d — Re-upload indicator**
- When uploading a replacement for an already-uploaded document type:
  "Updated: [filename] replaces previous [document type] upload"
- Helps users understand they've successfully updated a document

**Implementation:**
- Modify `ui/components/document_status.py` — add progress bar
- Modify `ui/fragments/chat_area.py` — add file type validation and enhanced confirmations
- Modify `ui/components/chat_input.py` — add client-side file type check
- No backend changes

---

### Section 3: Error Handling & Recovery

**Purpose:** Turn dead-end errors into recoverable situations with clear explanations and retry paths.

**Error types and handling:**

| Error Type | User Message | Explanation | Action |
|------------|--------------|-------------|--------|
| Network/Connection | "Connection lost" | "We couldn't reach the server. Your progress is saved." | [Retry] button |
| Timeout | "Request timed out" | "This is taking longer than expected. Your documents may still be processing." | [Check Status] button |
| Server error (5xx) | "Something went wrong" | "This is on our end. Please try again in a moment." | [Retry] button |
| Client error (4xx) | "Issue with your request" | Specific message based on error code | Contextual action |
| Invalid document | "File couldn't be read" | "We couldn't extract information from this file. Please upload a clearer copy." | [Re-upload] button |
| Session expired | "Session expired" | "Your session has expired for security. Log in again to continue." | [Log in again] button (preserves application ID) |

**Retry button behavior:**
- Re-sends the last user message and attached files to the API
- Shows a loading spinner while retrying
- Clears the error message on success
- Maximum 3 retries before showing a "Contact support" message with the application ID and a link back to the landing page

**Implementation:**
- Modify `ui/fragments/chat_area.py` — wrap API call in structured error handler
- New helper: `_handle_api_error(error: Exception, last_message: str, last_files: list) -> None`
- Error type detection via `isinstance` checks (ConnectionError, Timeout, HTTPStatusError)
- Retry state stored in `st.session_state.last_request` (message + files)
- No backend changes

---

### Section 4: Accessibility Features

**Purpose:** Make the application usable by applicants with visual impairments, low tech literacy, or accessibility needs.

**4a — High contrast toggle**
- Toggle button in the chat page header (eye icon)
- Switches to high-contrast color scheme:
  - Background: white (#FFFFFF)
  - Text: black (#000000)
  - User chat bubbles: dark blue (#003366) with white text
  - Assistant chat bubbles: light gray (#F0F0F0) with black text
  - Borders: 2px solid black on all cards and inputs
  - Buttons: black background, white text, 2px border
- State persisted in `st.session_state.high_contrast`
- Applied via CSS class toggle on the body

**4b — Text size control**
- Slider in the header with three positions: Normal / Large / Extra Large
- Applies CSS `font-size` scaling: 100% / 125% / 150%
- State persisted in `st.session_state.text_size`
- Applied via CSS custom property

**4c — Keyboard navigation**
- All interactive elements reachable via Tab key
- Custom HTML elements get `tabindex="0"`
- Focus order: guidance toggle → chat messages → chat input → file upload → sidebar elements
- Visible focus outlines on all interactive elements (2px solid blue outline)

**4d — Screen reader labels**
- `aria-label` on all custom interactive elements:
  - Chat input: "Type your message here"
  - File upload button: "Upload documents"
  - Retry button: "Retry the last action"
  - Guidance toggle: "Show or hide guidance for this step"
  - Help panel toggle: "Open help and FAQs"
  - High contrast toggle: "Toggle high contrast mode"
  - Text size control: "Adjust text size"
- `aria-live="polite"` on the chat message area so new messages are announced
- `role="status"` on progress indicators

**Implementation:**
- New file: `ui/components/accessibility_controls.py`
- Modify `ui/styles/global.css` — add high-contrast theme, text-size scaling, focus styles
- Add `aria-label` and `tabindex` to custom HTML in all components
- Inject accessibility CSS via `st.markdown` in `streamlit_app.py`
- Modify `ui/streamlit_app.py` — inject accessibility CSS and ARIA live regions

---

### Section 5: Help Panel

**Purpose:** Provide on-demand assistance so users can get answers without leaving the application.

**Behavior:**
- Collapsible panel accessible from a "?" button in the header
- Four tabs:
  1. **FAQs** — Phase-specific frequently asked questions
  2. **Glossary** — Definitions of key terms
  3. **Contact** — Support information
  4. **Summary** — "Summary so far" feature

**FAQ content by phase:**

| Phase | FAQs |
|-------|------|
| 0 — Authentication | "What is my Emirates ID?", "I forgot my Emirates ID number", "Can I start a new application?" |
| 1 — Intake | "Is my information confidential?", "Can I skip a question and come back?", "What if I don't know an answer?" |
| 2 — Document Collection | "What documents do I need?", "Can I upload photos of documents?", "What if I don't have a document?" |
| 3 — Processing | "How long does processing take?", "Do I need to stay on this page?", "What happens during processing?" |
| 4 — Review | "What is a discrepancy?", "How do I correct a discrepancy?", "What if I disagree with a finding?" |
| 5 — Decision | "What do the decision outcomes mean?", "Can I appeal a decision?", "How long until I receive support?" |
| 6 — Enablement | "Are these programs mandatory?", "How do I enroll in a program?", "What if none of these fit my situation?" |

**Glossary terms:**
- Emirates ID, AECB Credit Report, Bank Statement, Eligibility Score, Manual Review, Soft Decline, Enablement Programs

**Contact section:**
- Placeholder for support email and phone number
- "If you need human assistance, contact us at [email] or [phone]"

**Summary so far:**
- Button that generates a text summary from session state
- Includes: phases completed, documents uploaded, current phase, last system message
- Displayed inline in the panel

**Implementation:**
- New file: `ui/components/help_panel.py`
- `render_help_panel()` with `st.tabs` for the four sections
- FAQ data stored as nested dictionary keyed by phase
- Summary generated from `st.session_state.messages` and `st.session_state.current_phase`
- No backend changes

---

## Files Changed

| File | Change |
|------|--------|
| `ui/components/phase_guidance.py` | New — per-phase guidance panel |
| `ui/components/document_status.py` | Modified — add progress bar |
| `ui/components/chat_input.py` | Modified — add file type validation |
| `ui/fragments/chat_area.py` | Modified — structured error handling, retry buttons, upload confirmations |
| `ui/components/accessibility_controls.py` | New — high contrast toggle, text size control |
| `ui/components/help_panel.py` | New — Help panel with FAQs, glossary, contact, summary |
| `ui/styles/global.css` | Modified — high-contrast theme, text-size scaling, focus styles, ARIA support |
| `ui/app_pages/chat.py` | Modified — integrate accessibility controls and help panel into header |
| `ui/streamlit_app.py` | Modified — inject accessibility CSS and ARIA live regions |

**Total:** 2 new files, 7 modified files. No backend changes.

---

## Out of Scope

- Arabic language support (planned for future iteration)
- Backend API changes
- Database schema changes
- Agent behavior modifications
- Comprehensive UI test suite (separate initiative)

---

## Success Criteria

1. Users complete the full 7-phase flow without confusion or errors
2. Fewer support queries about "where am I" or "what do I do next"
3. Basic accessibility: keyboard navigation, screen reader friendly, high contrast support
4. All error states have a recovery path (no dead-end errors)
5. Document upload progress is visible and quantified at all times

---

## Future Improvements

- Arabic language support with RTL layout
- Voice input for applicants with mobility impairments
- Progressive Web App (PWA) support for offline capability
- Comprehensive UI test suite with Playwright
- A/B testing of guidance panel placement (top vs sidebar)
