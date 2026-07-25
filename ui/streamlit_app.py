"""Streamlit entrypoint with st.navigation."""

import streamlit as st

from ui.app_pages import chat, landing

st.set_page_config(
    page_title="Social Support Application",
    page_icon="🇦🇪",
    layout="centered",
)

pages = {
    "landing": st.Page(landing.render, title="Login", path="/"),
    "chat": st.Page(chat.render, title="Application", path="/application"),
}

pg = st.navigation(pages, position="hidden")
pg.run()
