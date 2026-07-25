"""7-phase node functions and gate nodes."""

from langchain_core.messages import BaseMessage

from src.agents.state import ApplicantState


def _get_last_message_content(state: ApplicantState) -> str:
    """Extract text content from the last message, handling both dicts and Message objects."""
    messages = state.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, BaseMessage):
        return last.content
    if isinstance(last, dict):
        return last.get("content", "")
    return str(last)


def _make_assistant_message(content: str) -> dict:
    """Create an assistant message dict."""
    return {"role": "assistant", "content": content}


def intake_node(state: ApplicantState) -> ApplicantState:
    last_message = _get_last_message_content(state)
    return {
        "messages": [
            _make_assistant_message(
                f"Welcome to the Social Support Application. "
                f"You said: '{last_message}'. "
                f"To begin, please tell me your full name as it appears on your Emirates ID."
            )
        ],
        "current_phase": "intake",
    }


def document_collection_node(state: ApplicantState) -> ApplicantState:
    last_message = _get_last_message_content(state)
    return {
        "messages": [
            _make_assistant_message(
                f"Thank you. We are now collecting your documents. "
                f"You said: '{last_message}'. "
                f"Please upload the following documents: Emirates ID, bank statements (last 6 months), "
                f"credit report, and proof of income. You can attach them here."
            )
        ],
        "current_phase": "document_collection",
    }


def processing_node(state: ApplicantState) -> ApplicantState:
    return {
        "messages": [
            _make_assistant_message(
                "Your documents are being processed. "
                "We are extracting and validating the information from your uploaded files. "
                "This may take a few moments."
            )
        ],
        "current_phase": "processing",
    }


def review_node(state: ApplicantState) -> ApplicantState:
    return {
        "messages": [
            _make_assistant_message(
                "Your application is under review. "
                "We are cross-checking your information across all documents for consistency."
            )
        ],
        "current_phase": "review",
    }


def decision_node(state: ApplicantState) -> ApplicantState:
    return {
        "messages": [
            _make_assistant_message(
                "We have reached a decision on your application. "
                "Your eligibility score has been calculated and a decision has been made."
            )
        ],
        "current_phase": "decision",
        "decision": "approved",
        "decision_explanation": "Application meets eligibility criteria based on provided information.",
    }


def enablement_node(state: ApplicantState) -> ApplicantState:
    return {
        "messages": [
            _make_assistant_message(
                "Congratulations! Your application has been approved. "
                "You will receive further instructions on the next steps for your support program. "
                "A case worker will contact you within 5 business days."
            )
        ],
        "current_phase": "enablement",
    }
