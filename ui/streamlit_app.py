"""Streamlit entrypoint with st.navigation."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `ui` is importable
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import structlog
import streamlit as st

from ui.app_pages import chat, landing
from ui.components.accessibility_controls import get_accessibility_css

logger = structlog.get_logger(__name__)

# Inject global custom CSS
_css_path = Path(__file__).resolve().parent / "styles" / "global.css"
if _css_path.exists():
    _css_content = _css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{_css_content}</style>", unsafe_allow_html=True)

# Inject accessibility CSS (after global CSS so it can override)
st.markdown(
    f"<style>{get_accessibility_css()}</style>",
    unsafe_allow_html=True,
)

# ARIA live region for chat updates
st.markdown(
    '<div aria-live="polite" aria-atomic="true" class="sr-only"></div>',
    unsafe_allow_html=True,
)

st.set_page_config(
    page_title="Social Support Application",
    page_icon="🇦🇪",
    layout="centered",
)

logger.info("streamlit_app_starting", page_title="Social Support Application")

login_page = st.Page(landing.render, title="Login")
app_page = st.Page(chat.render, title="Application", url_path="/application")

pages = [login_page, app_page]

# Store page references in session state for navigation
if "pages" not in st.session_state:
    st.session_state.pages = {"login": login_page, "application": app_page}

pg = st.navigation(pages, position="hidden")
pg.run()
