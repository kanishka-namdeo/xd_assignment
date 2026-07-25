"""Styled decision cards for Phase 5-6 applicant outcomes."""

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


def render_decision_card(decision: dict[str, Any]) -> None:
    """Render a styled decision card based on the decision type.

    Args:
        decision: Dictionary containing decision data with keys:
            - decision_type: "approved" | "manual_review" | "soft_decline"
            - eligibility_score: int (0-100)
            - support_amount: str (optional, for approved)
            - support_duration: str (optional, for approved)
            - key_factors: list[str] (factors that led to the decision)
            - reasons: list[str] (for soft_decline)
            - unresolved_discrepancies: list[str] (for manual_review)
            - additional_info_needed: list[str] (for manual_review)
            - improvement_suggestions: list[str] (for soft_decline)
            - appeal_process: str (for soft_decline)
            - next_steps: list[str]
    """
    decision_type = decision.get("decision_type", "unknown")
    logger.info(
        "decision_card_rendered",
        decision_type=decision_type,
        eligibility_score=decision.get("eligibility_score"),
    )

    if decision_type == "approved":
        _render_approved_card(decision)
    elif decision_type == "manual_review":
        _render_manual_review_card(decision)
    elif decision_type == "soft_decline":
        _render_soft_decline_card(decision)
    else:
        st.warning(f"Unknown decision type: {decision_type}")


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
