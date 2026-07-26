"""Deterministic completeness validation gate.

Validates that all required documents are processed and that identity
information is consistent across documents. No LLM calls.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _normalize_identity(value: Any) -> str:
    """Normalize identity number by removing dashes and spaces."""
    if value is None:
        return ""
    return str(value).replace("-", "").replace(" ", "").strip()


def _normalize_name(value: Any) -> str:
    """Normalize name for comparison: lowercase, collapse whitespace."""
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _extract_identity_numbers(extracted_data: dict[str, dict]) -> dict[str, str]:
    """Extract identity numbers from each document type.

    Returns dict mapping document_type -> normalized identity number.
    """
    identities: dict[str, str] = {}

    if "emirates_id" in extracted_data:
        eid = extracted_data["emirates_id"].get("identity_number")
        if eid:
            identities["emirates_id"] = _normalize_identity(eid)

    if "credit_report" in extracted_data:
        cr = extracted_data["credit_report"].get("identity_number")
        if cr:
            identities["credit_report"] = _normalize_identity(cr)

    if "application_form" in extracted_data:
        form = extracted_data["application_form"].get("identity_number")
        if form:
            identities["application_form"] = _normalize_identity(form)

    return identities


def _extract_names(extracted_data: dict[str, dict]) -> dict[str, str]:
    """Extract names from each document type.

    Returns dict mapping document_type -> normalized name.
    """
    names: dict[str, str] = {}

    if "emirates_id" in extracted_data:
        name = (
            extracted_data["emirates_id"].get("full_name_en")
            or extracted_data["emirates_id"].get("full_name")
        )
        if name:
            names["emirates_id"] = _normalize_name(name)

    if "credit_report" in extracted_data:
        name = extracted_data["credit_report"].get("full_name")
        if name:
            names["credit_report"] = _normalize_name(name)

    if "application_form" in extracted_data:
        name = extracted_data["application_form"].get("applicant_name")
        if name:
            names["application_form"] = _normalize_name(name)

    if "resume" in extracted_data:
        name = extracted_data["resume"].get("full_name")
        if name:
            names["resume"] = _normalize_name(name)

    if "assets_liabilities" in extracted_data:
        name = extracted_data["assets_liabilities"].get("applicant_name")
        if name:
            names["assets_liabilities"] = _normalize_name(name)

    return names


def _extract_dobs(extracted_data: dict[str, dict]) -> dict[str, str]:
    """Extract dates of birth from each document type.

    Returns dict mapping document_type -> DOB string.
    """
    dobs: dict[str, str] = {}

    if "emirates_id" in extracted_data:
        dob = extracted_data["emirates_id"].get("date_of_birth")
        if dob:
            dobs["emirates_id"] = str(dob)

    if "application_form" in extracted_data:
        dob = extracted_data["application_form"].get("date_of_birth")
        if dob:
            dobs["application_form"] = str(dob)

    if "resume" in extracted_data:
        dob = extracted_data["resume"].get("date_of_birth")
        if dob:
            dobs["resume"] = str(dob)

    return dobs


def _check_identity_consistency(identities: dict[str, str]) -> list[str]:
    """Check that identity numbers are identical across documents."""
    if len(identities) < 2:
        return []

    unique_values = set(identities.values())
    if len(unique_values) > 1:
        details = ", ".join(f"{k}={v}" for k, v in identities.items())
        return [f"Identity number mismatch across documents: {details}"]

    return []


def _check_name_consistency(names: dict[str, str]) -> list[str]:
    """Check that names are reconcilable across documents.

    Uses simple token overlap (Jaccard similarity) with threshold 0.6.
    """
    if len(names) < 2:
        return []

    name_list = list(names.values())
    errors: list[str] = []

    for i in range(len(name_list)):
        for j in range(i + 1, len(name_list)):
            tokens_a = set(name_list[i].split())
            tokens_b = set(name_list[j].split())
            if not tokens_a or not tokens_b:
                continue
            intersection = tokens_a & tokens_b
            union = tokens_a | tokens_b
            similarity = len(intersection) / len(union) if union else 0.0
            if similarity < 0.6:
                doc_keys = list(names.keys())
                errors.append(
                    f"Name mismatch between {doc_keys[i]} and {doc_keys[j]}: "
                    f"'{names[doc_keys[i]]}' vs '{names[doc_keys[j]]}' "
                    f"(similarity={similarity:.2f})"
                )

    return errors


def _check_dob_consistency(dobs: dict[str, str]) -> list[str]:
    """Check that dates of birth are identical across documents."""
    if len(dobs) < 2:
        return []

    unique_values = set(dobs.values())
    if len(unique_values) > 1:
        details = ", ".join(f"{k}={v}" for k, v in dobs.items())
        return [f"Date of birth mismatch across documents: {details}"]

    return []


def validate_completeness(
    validation_results: dict,
    extracted_data: dict[str, dict],
    required_documents: list[str],
) -> tuple[bool, list[str]]:
    """Deterministic validation of completeness.

    Args:
        validation_results: Dict mapping document_type -> validation status.
        extracted_data: Dict mapping document_type -> extracted data dict.
        required_documents: List of document types required for this application.

    Returns:
        (is_complete, missing_items) — missing_items is empty when complete.
    """
    missing_items: list[str] = []

    # Check all required documents are processed
    for doc_type in required_documents:
        if doc_type not in extracted_data:
            missing_items.append(f"Required document not processed: {doc_type}")
        elif doc_type not in validation_results:
            missing_items.append(f"Required document not validated: {doc_type}")

    # Check identity consistency
    identities = _extract_identity_numbers(extracted_data)
    missing_items.extend(_check_identity_consistency(identities))

    # Check name consistency
    names = _extract_names(extracted_data)
    missing_items.extend(_check_name_consistency(names))

    # Check DOB consistency
    dobs = _extract_dobs(extracted_data)
    missing_items.extend(_check_dob_consistency(dobs))

    is_complete = len(missing_items) == 0
    if is_complete:
        logger.info("completeness_passed", required_count=len(required_documents))
    else:
        logger.warning("completeness_failed", missing_count=len(missing_items), missing_items=missing_items)

    return is_complete, missing_items
