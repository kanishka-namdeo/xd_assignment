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
