"""Phase 6 expandable recommendations."""

from typing import Any

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

CATEGORY_ICONS = {
    "upskilling": "📚",
    "job_matching": "💼",
    "career_counseling": "🎯",
    "financial_literacy": "💰",
    "training": "🎓",
    "support_programs": "🏛️",
}


def render_enablement_section(recommendations: list[str] | None = None) -> None:
    """Render the enablement section for Phase 6.

    Args:
        recommendations: List of recommendation strings to display.
            Each string should be in format "Title: Description".
    """
    logger.debug("enablement_section_rendered", recommendation_count=len(recommendations) if recommendations else 0)

    if not recommendations:
        st.subheader("Economic Enablement")
        st.caption("No personalized recommendations available yet.")
        return

    st.subheader("Economic Enablement Recommendations")
    st.caption("Personalized recommendations based on your profile and decision outcome.")

    for rec in recommendations:
        # Parse "Title: Description" format
        if ":" in rec:
            title, description = rec.split(":", 1)
            title = title.strip()
            description = description.strip()
        else:
            title = rec
            description = ""

        # Try to find a matching icon
        icon = "📋"
        for key, possible_icon in CATEGORY_ICONS.items():
            if key.lower() in title.lower() or key.lower() in description.lower():
                icon = possible_icon
                break

        with st.expander(f"{icon} {title}"):
            if description:
                st.markdown(description)
            st.caption("Recommended based on your employment status, skills, and application outcome.")
