# Streamlit Frontend

## Purpose
Chat-based user interface for applicant interaction with the Social Support Application system. Implements the 7-phase applicant flow: authentication (Phase 0), intake, document collection, processing, review, decision, enablement (Phases 1-6).

## Ownership
- Primary: Development Team
- Review Required: UI changes require review

## Local Contracts

### Streamlit Conventions
Streamlit patterns (navigation, caching, performance) are defined in `.cursor/rules/streamlit.mdc`. Key conventions:
- Use `st.navigation` with `st.Page` API — not legacy `pages/` directory
- Use `app_pages/` directory for page modules
- Use `@st.fragment` for partial reruns
- Use `@st.cache_data` with `ttl` for serializable values
- Use `@st.cache_resource` for global objects

### File Organization
- `streamlit_app.py`: Entrypoint with `st.navigation` setup and global CSS injection
- `app_pages/`: Page definitions (landing.py, chat.py)
- `components/`: Reusable UI elements (decision cards, discrepancy cards, document status, phase tracker, chat input, phase guidance, accessibility controls, help panel, enablement section)
- `fragments/`: `@st.fragment` wrapped sections for partial reruns (chat_area)
- `styles/`: Global CSS stylesheets

### Chat Interface
- Use `st.chat_message` and `st.chat_input` for conversation
- Enable file upload: `st.chat_input(accept_file="multiple", file_type=["pdf", "xlsx", "docx", "png", "jpg"])`
- Use `submit_mode="disable"` to prevent interrupting LLM responses
- Render decision cards as styled `st.chat_message` content

### Session State Contracts
The following session state keys are set by the UI and consumed by components:
- `st.session_state.identity_number` — set on login, used by chat and document status
- `st.session_state.applicant_info` — set on login, used by chat for personalization
- `st.session_state.uploaded_documents` — normalized dict keyed by `doc_type` (not `document_type`)
- `st.session_state.current_phase` — tracks active phase for phase tracker and chat input
- `st.session_state.high_contrast` — bool, accessibility high contrast mode toggle
- `st.session_state.text_size` — str ("normal", "large", "xlarge"), accessibility text size
- `st.session_state.last_request` — dict with "message" and "files" for error retry
- `st.session_state.last_retry_count` — int, retry attempt counter for error recovery

### Phase Label Contract
Phase keys in `PHASE_LABELS` use `"authentication"` (not `"auth"`) to match backend state.

## Work Guidance

### Adding a New Page
1. Create file in `app_pages/` (e.g., `app_pages/status.py`)
2. Define page using `st.Page` in `streamlit_app.py`
3. Add to navigation with `st.navigation`

### Adding a New Component
1. Create file in `components/` (e.g., `components/upload_progress.py`)
2. Implement as reusable function or class
3. Import and use in pages

### Optimizing Performance
1. Wrap expensive sections in `@st.fragment` for partial reruns
2. Follow caching conventions in `.cursor/rules/streamlit.mdc`

## Verification
- Manual testing via Streamlit dev server
- Visual regression testing (future)

## Child DOX Index
None - single-level structure.
