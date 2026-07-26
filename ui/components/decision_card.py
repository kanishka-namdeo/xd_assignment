"""Styled decision cards for Phase 5-6 applicant outcomes."""

from datetime import datetime
from typing import Any

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)


def _render_factor_list(factors: list[str], icon: str = "•") -> str:
    """Render a bulleted list of factors as HTML."""
    items = "".join(f"<li>{icon} {factor}</li>" for factor in factors)
    return f"<ul style='list-style:none;padding-left:0;margin:8px 0;'>{items}</ul>"


def _render_next_steps(steps: list[str]) -> str:
    """Render next steps as a numbered list."""
    items = "".join(f"<li>{i + 1}. {step}</li>" for i, step in enumerate(steps))
    return f"<ol style='padding-left:20px;margin:8px 0;'>{items}</ol>"


def _generate_decision_summary(card: dict[str, Any]) -> str:
    """Generate a plain-text decision summary for download."""
    decision_type = card.get("decision", card.get("decision_type", card.get("type", "unknown")))
    score = card.get("eligibility_score", "N/A")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "=" * 50,
        "SOCIAL SUPPORT APPLICATION - DECISION SUMMARY",
        "=" * 50,
        "",
        f"Decision: {decision_type.replace('_', ' ').title()}",
        f"Eligibility Score: {score}/100" if isinstance(score, (int, float)) else f"Eligibility Score: {score}",
        f"Date: {date_str}",
        "",
    ]

    # Key factors / reasons
    factors = card.get("key_factors") or card.get("reasons") or []
    if factors:
        lines.append("Key Factors:")
        for factor in factors:
            lines.append(f"  - {factor}")
        lines.append("")

    additional_info = card.get("additional_info_needed", [])
    if additional_info:
        lines.append("Additional Information Needed:")
        for info in additional_info:
            lines.append(f"  - {info}")
        lines.append("")

    discrepancies = card.get("unresolved_discrepancies", [])
    if discrepancies:
        lines.append("Unresolved Discrepancies:")
        for disc in discrepancies:
            lines.append(f"  - {disc}")
        lines.append("")

    improvements = card.get("improvement_suggestions", [])
    if improvements:
        lines.append("Improvement Suggestions:")
        for imp in improvements:
            lines.append(f"  - {imp}")
        lines.append("")

    # Explanation
    explanation = card.get("explanation", "")
    if explanation:
        lines.append("Explanation:")
        lines.append(f"  {explanation}")
        lines.append("")

    # Next steps
    next_steps = card.get("next_steps", [])
    if next_steps:
        lines.append("Next Steps:")
        for i, step in enumerate(next_steps, 1):
            lines.append(f"  {i}. {step}")
        lines.append("")

    # Support details for approved
    support_amount = card.get("support_amount")
    support_duration = card.get("support_duration")
    if support_amount:
        lines.append(f"Support Amount: AED {support_amount}")
    if support_duration:
        lines.append(f"Support Duration: {support_duration}")

    # Enablement section
    enablement = card.get("enablement_section")
    if enablement and enablement.get("items"):
        lines.append("")
        lines.append(f"Recommended Support Programs: {enablement.get('title', '')}")
        for item in enablement["items"]:
            lines.append(f"  - {item.get('title', '')}: {item.get('description', '')}")

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


def _render_download_button(card: dict[str, Any]) -> None:
    """Render a download button for the decision summary."""
    summary = _generate_decision_summary(card)
    st.download_button(
        label="Download Decision Summary",
        data=summary,
        file_name="decision_summary.txt",
        mime="text/plain",
        use_container_width=True,
    )


def render_decision_card(card: dict[str, Any]) -> None:
    """Render a styled decision card from the formatted card dict.

    Args:
        card: Dictionary containing formatted decision card data with keys:
            - title: str (card header title)
            - decision: str (approved/soft_decline/manual_review)
            - color: str (green/red/orange)
            - icon: str (check_circle/cancel/pending)
            - explanation: str (human-readable explanation)
            - next_steps: list[str]
            - enablement_section: dict | None (optional enablement programs)
    """
    decision_type = card.get("decision", card.get("decision_type", "unknown"))
    logger.info(
        "decision_card_rendered",
        decision_type=decision_type,
        has_enablement=card.get("enablement_section") is not None,
    )

    if _is_formatted_card(card):
        _render_formatted_card(card)
    elif decision_type == "approved":
        _render_approved_card(card)
    elif decision_type == "manual_review":
        _render_manual_review_card(card)
    elif decision_type == "soft_decline":
        _render_soft_decline_card(card)
    else:
        st.warning(f"Unknown decision type: {decision_type}")

    _render_download_button(card)


def _is_formatted_card(card: dict[str, Any]) -> bool:
    """Check if card is from the new decision_formatting_tool format."""
    return "title" in card and "color" in card and "explanation" in card


def _render_formatted_card(card: dict[str, Any]) -> None:
    """Render a card produced by decision_formatting_tool."""
    title = card.get("title", "Decision")
    color = card.get("color", "orange")
    explanation = card.get("explanation", "")
    next_steps = card.get("next_steps", [])
    enablement_section = card.get("enablement_section")

    color_map = {
        "green": {"bg": "#d4edda", "border": "#28a745", "text": "#155724", "subtext": "#5a7a5f", "icon_bg": "#28a745", "icon_char": "\u2713"},
        "red": {"bg": "#f8d7da", "border": "#dc3545", "text": "#721c24", "subtext": "#7a4545", "icon_bg": "#dc3545", "icon_char": "\u2717"},
        "orange": {"bg": "#fff3cd", "border": "#ffc107", "text": "#856404", "subtext": "#7a6c45", "icon_bg": "#ffc107", "icon_char": "!"},
    }
    c = color_map.get(color, color_map["orange"])

    steps_html = _render_next_steps(next_steps) if next_steps else ""

    enablement_html = ""
    if enablement_section and enablement_section.get("items"):
        items = enablement_section["items"]
        section_title = enablement_section.get("title", "Recommended Support Programs")
        item_rows = "".join(
            f"<div style='background:white;border-radius:6px;padding:10px 14px;margin-bottom:6px;'>"
            f"<strong style='color:{c['text']};'>{_escape_html(item.get('title', ''))}</strong>"
            f"<p style='margin:4px 0 0 0;color:{c['subtext']};font-size:13px;'>{_escape_html(item.get('description', ''))}</p>"
            f"</div>"
            for item in items
        )
        enablement_html = f"""
        <details style='margin-top:16px;'>
            <summary style='cursor:pointer;color:{c["text"]};font-size:16px;font-weight:600;margin-bottom:8px;'>{section_title}</summary>
            <div style='margin-top:8px;'>{item_rows}</div>
        </details>
        """

    card_html = f"""
    <div style='
        background: linear-gradient(135deg, {c["bg"]} 0%, {c["bg"]} 100%;
        border-left: 6px solid {c["border"]};
        border-radius: 12px;
        padding: 24px 28px;
        margin: 16px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    '>
        <div style='display:flex;align-items:center;gap:12px;margin-bottom:16px;'>
            <div style='
                width:48px;height:48px;border-radius:50%;
                background:{c["icon_bg"]};color:white;
                display:flex;align-items:center;justify-content:center;
                font-size:24px;font-weight:bold;
            '>{c["icon_char"]}</div>
            <div>
                <h3 style='margin:0;color:{c["text"]};font-size:22px;'>{title}</h3>
            </div>
        </div>

        <div style='
            background:white;border-radius:8px;padding:16px;
            margin-bottom:16px;
            box-shadow:0 1px 4px rgba(0,0,0,0.05);
        '>
            <p style='margin:0;color:{c["text"]};font-size:14px;line-height:1.6;'>{explanation}</p>
        </div>

        {f'<div><h4 style="margin:0 0 8px 0;color:{c["text"]};font-size:16px;">Next Steps</h4>{steps_html}</div>' if steps_html else ''}

        {enablement_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_approved_card(decision: dict[str, Any]) -> None:
    """Render green approved decision card."""
    score = decision.get("eligibility_score", 0)
    support_amount = decision.get("support_amount", "N/A")
    support_duration = decision.get("support_duration", "N/A")
    key_factors = decision.get("key_factors", [])
    next_steps = decision.get("next_steps", [])

    card_html = f"""
    <div style='
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border-left: 6px solid #28a745;
        border-radius: 12px;
        padding: 24px 28px;
        margin: 16px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    '>
        <div style='display:flex;align-items:center;gap:12px;margin-bottom:16px;'>
            <div style='
                width:48px;height:48px;border-radius:50%;
                background:#28a745;color:white;
                display:flex;align-items:center;justify-content:center;
                font-size:24px;font-weight:bold;
            '>✓</div>
            <div>
                <h3 style='margin:0;color:#155724;font-size:22px;'>Application Approved</h3>
                <p style='margin:2px 0 0 0;color:#5a7a5f;font-size:14px;'>Your social support application has been approved</p>
            </div>
        </div>

        <div style='
            background:white;border-radius:8px;padding:16px;
            margin-bottom:16px;
            box-shadow:0 1px 4px rgba(0,0,0,0.05);
        '>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:16px;'>
                <div>
                    <p style='margin:0 0 4px 0;color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;'>Eligibility Score</p>
                    <p style='margin:0;font-size:28px;font-weight:bold;color:#28a745;'>{score}/100</p>
                </div>
                <div>
                    <p style='margin:0 0 4px 0;color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;'>Support Amount</p>
                    <p style='margin:0;font-size:20px;font-weight:bold;color:#155724;'>AED {support_amount}</p>
                </div>
            </div>
            <div style='margin-top:12px;'>
                <p style='margin:0 0 4px 0;color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;'>Support Duration</p>
                <p style='margin:0;font-size:16px;color:#155724;'>{support_duration}</p>
            </div>
        </div>

        <div style='margin-bottom:16px;'>
            <h4 style='margin:0 0 8px 0;color:#155724;font-size:16px;'>Key Factors</h4>
            {_render_factor_list(key_factors, icon="✓")}
        </div>

        <div>
            <h4 style='margin:0 0 8px 0;color:#155724;font-size:16px;'>Next Steps</h4>
            {_render_next_steps(next_steps)}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _render_manual_review_card(decision: dict[str, Any]) -> None:
    """Render yellow manual_review decision card."""
    score = decision.get("eligibility_score", 0)
    additional_info = decision.get("additional_info_needed", [])
    discrepancies = decision.get("unresolved_discrepancies", [])
    next_steps = decision.get("next_steps", [])

    card_html = f"""
    <div style='
        background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
        border-left: 6px solid #ffc107;
        border-radius: 12px;
        padding: 24px 28px;
        margin: 16px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    '>
        <div style='display:flex;align-items:center;gap:12px;margin-bottom:16px;'>
            <div style='
                width:48px;height:48px;border-radius:50%;
                background:#ffc107;color:white;
                display:flex;align-items:center;justify-content:center;
                font-size:24px;font-weight:bold;
            '>!</div>
            <div>
                <h3 style='margin:0;color:#856404;font-size:22px;'>Manual Review Required</h3>
                <p style='margin:2px 0 0 0;color:#7a6c45;font-size:14px;'>Your application needs additional verification</p>
            </div>
        </div>

        <div style='
            background:white;border-radius:8px;padding:16px;
            margin-bottom:16px;
            box-shadow:0 1px 4px rgba(0,0,0,0.05);
        '>
            <p style='margin:0 0 4px 0;color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;'>Eligibility Score</p>
            <p style='margin:0;font-size:28px;font-weight:bold;color:#ffc107;'>{score}/100</p>
        </div>

        {f'''
        <div style='margin-bottom:16px;'>
            <h4 style='margin:0 0 8px 0;color:#856404;font-size:16px;'>Additional Information Needed</h4>
            {_render_factor_list(additional_info, icon="📋")}
        </div>
        ''' if additional_info else ''}

        {f'''
        <div style='margin-bottom:16px;'>
            <h4 style='margin:0 0 8px 0;color:#856404;font-size:16px;'>Unresolved Discrepancies</h4>
            {_render_factor_list(discrepancies, icon="⚠️")}
        </div>
        ''' if discrepancies else ''}

        <div>
            <h4 style='margin:0 0 8px 0;color:#856404;font-size:16px;'>Next Steps</h4>
            {_render_next_steps(next_steps)}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _render_soft_decline_card(decision: dict[str, Any]) -> None:
    """Render red soft_decline decision card."""
    score = decision.get("eligibility_score", 0)
    reasons = decision.get("reasons", [])
    improvements = decision.get("improvement_suggestions", [])
    appeal_process = decision.get("appeal_process", "")
    next_steps = decision.get("next_steps", [])

    card_html = f"""
    <div style='
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border-left: 6px solid #dc3545;
        border-radius: 12px;
        padding: 24px 28px;
        margin: 16px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    '>
        <div style='display:flex;align-items:center;gap:12px;margin-bottom:16px;'>
            <div style='
                width:48px;height:48px;border-radius:50%;
                background:#dc3545;color:white;
                display:flex;align-items:center;justify-content:center;
                font-size:24px;font-weight:bold;
            '>✗</div>
            <div>
                <h3 style='margin:0;color:#721c24;font-size:22px;'>Application Not Approved</h3>
                <p style='margin:2px 0 0 0;color:#7a4545;font-size:14px;'>Your application does not currently meet eligibility criteria</p>
            </div>
        </div>

        <div style='
            background:white;border-radius:8px;padding:16px;
            margin-bottom:16px;
            box-shadow:0 1px 4px rgba(0,0,0,0.05);
        '>
            <p style='margin:0 0 4px 0;color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;'>Eligibility Score</p>
            <p style='margin:0;font-size:28px;font-weight:bold;color:#dc3545;'>{score}/100</p>
        </div>

        <div style='margin-bottom:16px;'>
            <h4 style='margin:0 0 8px 0;color:#721c24;font-size:16px;'>Reasons for Decline</h4>
            {_render_factor_list(reasons, icon="✗")}
        </div>

        {f'''
        <div style='margin-bottom:16px;'>
            <h4 style='margin:0 0 8px 0;color:#721c24;font-size:16px;'>How to Improve Eligibility</h4>
            {_render_factor_list(improvements, icon="→")}
        </div>
        ''' if improvements else ''}

        {f'''
        <div style='
            background:rgba(255,255,255,0.6);border-radius:8px;padding:16px;
            margin-bottom:16px;border:1px solid #f5c6cb;
        '>
            <h4 style='margin:0 0 8px 0;color:#721c24;font-size:16px;'>Appeal Process</h4>
            <p style='margin:0;color:#721c24;font-size:14px;line-height:1.6;'>{appeal_process}</p>
        </div>
        ''' if appeal_process else ''}

        <div>
            <h4 style='margin:0 0 8px 0;color:#721c24;font-size:16px;'>Next Steps</h4>
            {_render_next_steps(next_steps)}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
