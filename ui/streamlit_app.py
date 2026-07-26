"""Streamlit entrypoint with st.navigation."""

import structlog
import streamlit as st

from ui.app_pages import chat, landing

logger = structlog.get_logger(__name__)

st.set_page_config(
    page_title="Social Support Application",
    page_icon="🇦🇪",
    layout="centered",
)

logger.info("streamlit_app_starting", page_title="Social Support Application")

pages = [
    st.Page(landing.render, title="Login"),
    st.Page(chat.render, title="Application", url_path="/application"),
]

pg = st.navigation(pages, position="hidden")
pg.run()
