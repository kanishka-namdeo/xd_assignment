# Streamlit Frontend

## Purpose
Chat-based user interface for applicant interaction with the Social Support Application system. Implements the 7-phase applicant flow: authentication (Phase 0), intake, document collection, processing, review, decision, enablement (Phases 1-6).

## Ownership
- Primary: Development Team
- Review Required: UI changes require review

## Local Contracts

### Navigation Pattern
Use `st.navigation` with `st.Page` API (2025-2026 standard). Do NOT use `pages/` directory (legacy auto-discovery). Use `app_pages/` instead.

### File Organization
- `streamlit_app.py`: Entrypoint with `st.navigation` setup
- `app_pages/`: Page definitions (landing.py, chat.py)
- `components/`: Reusable UI elements (decision cards, document status, phase tracker)
- `fragments/`: `@st.fragment` wrapped sections for partial reruns

### Performance Rules
- Use `@st.fragment` for chat area to prevent full-page reruns
- Use `@st.cache_data` with `ttl` for API responses
- Use `@st.cache_resource` for global objects (DB connections, ML models)
- Never store large DataFrames in `st.session_state`

### Chat Interface
- Use `st.chat_message` and `st.chat_input` for conversation
- Enable file upload: `st.chat_input(accept_file="multiple", file_type=["pdf", "xlsx", "docx", "png", "jpg"])`
- Use `submit_mode="disable"` to prevent interrupting LLM responses
- Render decision cards as styled `st.chat_message` content

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
1. Wrap expensive sections in `@st.fragment`
2. Cache API calls with `@st.cache_data(ttl=300)`
3. Cache global objects with `@st.cache_resource`
4. Avoid storing large data in session state

## Verification
- Manual testing via Streamlit dev server
- Visual regression testing (future)

## Child DOX Index
None - single-level structure.
