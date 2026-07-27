"""Sidebar Help panel with FAQs, glossary, contact info, and application summary."""

import streamlit as st
import structlog

logger = structlog.get_logger(__name__)

CONTACT_EMAIL = "support@socialsupport.gov.ae"
CONTACT_PHONE = "800-SUPPORT (800-7877678)"

FAQS_BY_PHASE: dict[str, list[dict[str, str]]] = {
    "authentication": [
        {
            "question": "What is my Emirates ID number?",
            "answer": "Your Emirates ID is a 15-digit number printed on the front of your ID card, formatted as 784-YYYY-NNNNNNN-C.",
        },
        {
            "question": "Can I resume a previous application?",
            "answer": "Yes. Enter the same Emirates ID you used before and your session will be restored automatically.",
        },
        {
            "question": "Is my information secure?",
            "answer": "Yes. All data is encrypted and stored securely. Only authorised personnel can access your application.",
        },
    ],
    "intake": [
        {
            "question": "What information do I need to provide?",
            "answer": "You will be asked about your family situation, employment, income, and living arrangements. Answer honestly — this helps us find the right support for you.",
        },
        {
            "question": "Do I have to answer every question?",
            "answer": "You can skip questions, but providing complete information helps us assess your eligibility more accurately.",
        },
        {
            "question": "Can I change my answers later?",
            "answer": "Yes. You can go back and clarify any information during the Review phase.",
        },
    ],
    "document_collection": [
        {
            "question": "What documents do I need to upload?",
            "answer": "At minimum: your Emirates ID, a bank statement, and a credit report. Additional documents may be requested based on your situation.",
        },
        {
            "question": "What file formats are accepted?",
            "answer": "PDF, PNG, JPG, JPEG, XLSX, and DOCX files are accepted. Photos of documents are fine — just make sure the text is clear and readable.",
        },
        {
            "question": "Can I upload documents later?",
            "answer": "Yes. You can return to this phase and upload additional documents at any time before the Review phase.",
        },
    ],
    "processing": [
        {
            "question": "How long does processing take?",
            "answer": "Processing usually takes a few minutes. The system extracts and validates information from your documents automatically.",
        },
        {
            "question": "Can I continue using the app while waiting?",
            "answer": "Yes. You can review your uploaded documents or explore the Help panel while processing completes.",
        },
    ],
    "review": [
        {
            "question": "What are discrepancies?",
            "answer": "Discrepancies are differences found between your documents — for example, if your name is spelled differently on two IDs. Most are minor and easily resolved.",
        },
        {
            "question": "How do I resolve a discrepancy?",
            "answer": "You can either provide a clarification in the chat or re-upload a clearer version of the document in question.",
        },
        {
            "question": "What happens if I ignore discrepancies?",
            "answer": "Unresolved discrepancies may delay your application or result in a manual review.",
        },
    ],
    "decision": [
        {
            "question": "What decisions are possible?",
            "answer": "Your application can be approved, sent for manual review, or declined. Each decision includes a detailed explanation and next steps.",
        },
        {
            "question": "Can I appeal a decision?",
            "answer": "Yes. If your application is declined, you can request a manual review by contacting support or uploading additional supporting documents.",
        },
        {
            "question": "How will I receive my decision?",
            "answer": "Your decision will appear as a decision card in the chat, with a detailed explanation and any next steps.",
        },
    ],
    "enablement": [
        {
            "question": "What are enablement recommendations?",
            "answer": "Based on your profile, we suggest programs and services that may help you — such as job training, financial counselling, or housing support.",
        },
        {
            "question": "Are these recommendations mandatory?",
            "answer": "No. Recommendations are suggestions only. You can choose which programs to explore.",
        },
        {
            "question": "How do I apply for a recommended program?",
            "answer": "Each recommendation includes contact information and application instructions. You can also ask support for assistance.",
        },
    ],
}

GLOSSARY: dict[str, str] = {
    "Emirates ID": "A 15-digit national identification number issued by the UAE government. Required for all residents.",
    "Bank Statement": "A record of your account transactions, typically covering the last 3–6 months. Used to verify income and expenses.",
    "Credit Report": "A report from the Al Etihad Credit Bureau (AECB) showing your credit history, outstanding debts, and credit score.",
    "Support Category": "The classification of your support request (e.g., divorced, abandoned, unknown parentage, health disability). Determines which documents are required.",
    "Eligibility": "Whether you qualify for social support based on income, family situation, and other criteria.",
    "Discrepancy": "A difference or inconsistency between information found in your documents. Most are minor and easily resolved.",
    "Manual Review": "A human officer reviews your application when the automated system cannot make a clear decision.",
    "Soft Decline": "An initial decline that can be reconsidered with additional documentation or clarification.",
    "Enablement": "Personalized recommendations for programs and services that can support your situation and goals.",
    "Luhn Algorithm": "A mathematical formula used to validate identification numbers, including Emirates IDs.",
}


def _generate_summary() -> dict[str, str | int]:
    """Generate an application summary from session state."""
    messages = st.session_state.get("messages", [])
    if not isinstance(messages, list):
        messages = []

    documents = st.session_state.get("uploaded_documents", {})
    if isinstance(documents, list):
        uploaded_count = len(documents)
    elif isinstance(documents, dict):
        uploaded_count = len(documents)
    else:
        uploaded_count = 0

    current_phase = st.session_state.get("current_phase", "intake")
    applicant_info = st.session_state.get("applicant_info", {}) or {}

    user_messages = sum(1 for m in messages if m.get("role") == "user")
    assistant_messages = sum(1 for m in messages if m.get("role") == "assistant")

    return {
        "current_phase": current_phase,
        "total_messages": len(messages),
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "documents_uploaded": uploaded_count,
        "support_category": applicant_info.get("support_category", "Not yet determined"),
        "marital_status": applicant_info.get("marital_status", "Not yet provided"),
    }


def _render_faqs() -> None:
    """Render the FAQs tab with phase-specific questions."""
    current_phase = st.session_state.get("current_phase", "intake")
    faqs = FAQS_BY_PHASE.get(current_phase) or FAQS_BY_PHASE.get("intake", [])

    st.markdown(
        "**FAQs for current phase:** "
        f"{current_phase.replace('_', ' ').title()}"
    )
    st.markdown("---")

    for i, faq in enumerate(faqs):
        with st.expander(f"Q{i + 1}: {faq['question']}", expanded=False):
            st.markdown(faq["answer"])

    st.markdown("---")
    st.caption("Tip: You can also ask questions in the chat at any time.")


def _render_glossary() -> None:
    """Render the Glossary tab with term definitions."""
    st.markdown("Common terms used in the application process:")
    st.markdown("---")

    for term, definition in GLOSSARY.items():
        with st.expander(term, expanded=False):
            st.markdown(definition)


def _render_contact() -> None:
    """Render the Contact tab with support information."""
    st.markdown("### Support Contact")
    st.markdown(
        "If you need assistance, our support team is available:"
    )
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Email**")
        st.markdown(f"[{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL})")
    with col2:
        st.markdown("**Phone**")
        st.markdown(CONTACT_PHONE)

    st.markdown("---")
    st.markdown("**Hours:** Sunday – Thursday, 8:00 AM – 6:00 PM GST")
    st.info(
        "For urgent matters, call the phone number above. "
        "For non-urgent questions, you can also use the chat."
    )


def _render_summary() -> None:
    """Render the Application Summary tab."""
    summary = _generate_summary()

    st.markdown("### Application Summary")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current Phase", summary["current_phase"].replace("_", " ").title())
        st.metric("Documents Uploaded", str(summary["documents_uploaded"]))
        st.metric("Total Messages", str(summary["total_messages"]))
    with col2:
        st.metric("Support Category", str(summary["support_category"]))
        st.metric("Marital Status", str(summary["marital_status"]))

    st.markdown("---")

    if summary["total_messages"] > 0:
        st.caption(
            f"Your session includes {summary['user_messages']} your messages and "
            f"{summary['assistant_messages']} responses."
        )
    else:
        st.caption("No messages yet. Start by typing in the chat.")

    if st.button("Refresh Summary", key="refresh_summary"):
        st.rerun()


def render_help_panel() -> None:
    """Render the Help panel in the sidebar with four tabs."""
    with st.sidebar.expander("❓ Help & Support", expanded=False):
        tab_faqs, tab_glossary, tab_contact, tab_summary = st.tabs(
            ["FAQs", "Glossary", "Contact", "Summary"]
        )

        with tab_faqs:
            _render_faqs()

        with tab_glossary:
            _render_glossary()

        with tab_contact:
            _render_contact()

        with tab_summary:
            _render_summary()

    logger.debug("help_panel_rendered")
