"""Validation tools for Reflexion reasoning loop.

Five tools for the validation agent:
- per_document_validation_tool: Internal consistency checks per document
- cross_document_compare_tool: Cross-document field matching
- discrepancy_classify_tool: Classify OCR errors vs real discrepancies
- applicant_clarify_tool: Generate clarification questions
- validation_confidence_tool: Compute overall validation confidence
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.tools import tool

from src.agents.gates.completeness import validate_completeness
from src.agents.gates.document_integrity import validate_document_integrity

logger = structlog.get_logger(__name__)


@tool
def per_document_validation_tool(
    extracted_data: dict,
    document_type: str,
) -> dict:
    """Validate extracted data within a single document for internal consistency.

    Use for: Checking if transactions sum to totals, dates are valid, required fields present.
    Returns: Validation results with pass/fail per rule and confidence score.

    Args:
        extracted_data: Extracted data dictionary for the document.
        document_type: Document type key (e.g., "bank_statement", "credit_report").

    Returns:
        Dict with validation_results (list of rule checks), overall_status, and confidence.
    """
    start = time.perf_counter()

    logger.debug(
        "validation_tool_start",
        tool="per_document_validation",
        document_type=document_type,
    )

    try:
        is_valid, errors = validate_document_integrity(extracted_data, document_type)

        validation_results = []
        if is_valid:
            validation_results.append({
                "rule": "integrity_check",
                "status": "passed",
                "message": "All integrity checks passed",
            })
        else:
            for error in errors:
                validation_results.append({
                    "rule": "integrity_check",
                    "status": "failed",
                    "message": error,
                })

        overall_status = "valid" if is_valid else "invalid"
        confidence = 1.0 if is_valid else max(0.0, 1.0 - (len(errors) * 0.15))

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "per_document_validation_complete",
            document_type=document_type,
            status=overall_status,
            error_count=len(errors),
            confidence=round(confidence, 2),
            duration_ms=round(duration_ms, 2),
        )

        return {
            "document_type": document_type,
            "validation_results": validation_results,
            "overall_status": overall_status,
            "confidence": confidence,
            "errors": errors,
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "per_document_validation_error",
            document_type=document_type,
            error=str(e),
            duration_ms=round(duration_ms, 2),
        )
        return {
            "document_type": document_type,
            "validation_results": [],
            "overall_status": "error",
            "confidence": 0.0,
            "errors": [str(e)],
        }


@tool
def cross_document_compare_tool(
    extracted_data: dict[str, dict],
    comparison_type: str,
) -> dict:
    """Compare fields across multiple documents for consistency.

    Use for: Checking if identity numbers, names, income, and addresses match across documents.
    Returns: Comparison results with match/mismatch per field and discrepancy details.

    Args:
        extracted_data: Dict mapping document_type -> extracted data dict.
        comparison_type: Type of comparison ("identity_match", "name_consistency", "income_consistency", "address_consistency").

    Returns:
        Dict with results (list of comparisons), overall_match, discrepancies, and confidence.
    """
    start = time.perf_counter()

    logger.debug(
        "cross_document_compare_start",
        comparison_type=comparison_type,
        document_count=len(extracted_data),
    )

    try:
        results = []
        discrepancies = []
        overall_match = True
        confidence = 1.0

        if comparison_type == "identity_match":
            identity_numbers = {}
            for doc_type, data in extracted_data.items():
                identity_num = data.get("identity_number")
                if identity_num:
                    identity_numbers[doc_type] = str(identity_num).replace("-", "").replace(" ", "")

            if len(identity_numbers) >= 2:
                unique_values = set(identity_numbers.values())
                if len(unique_values) > 1:
                    overall_match = False
                    details = ", ".join(f"{k}={v}" for k, v in identity_numbers.items())
                    discrepancies.append({
                        "type": "identity_mismatch",
                        "field": "identity_number",
                        "values": identity_numbers,
                        "details": details,
                    })
                    results.append({
                        "check": "identity_consistency",
                        "status": "mismatch",
                        "message": f"Identity numbers differ: {details}",
                    })
                else:
                    results.append({
                        "check": "identity_consistency",
                        "status": "match",
                        "message": "Identity numbers consistent across documents",
                    })

        elif comparison_type == "name_consistency":
            names = {}
            for doc_type, data in extracted_data.items():
                name = (
                    data.get("full_name_en")
                    or data.get("full_name")
                    or data.get("applicant_name")
                    or data.get("account_holder_name")
                )
                if name:
                    names[doc_type] = " ".join(str(name).strip().lower().split())

            if len(names) >= 2:
                name_list = list(names.items())
                for i in range(len(name_list)):
                    for j in range(i + 1, len(name_list)):
                        doc_a, name_a = name_list[i]
                        doc_b, name_b = name_list[j]
                        tokens_a = set(name_a.split())
                        tokens_b = set(name_b.split())
                        if tokens_a and tokens_b:
                            intersection = tokens_a & tokens_b
                            union = tokens_a | tokens_b
                            similarity = len(intersection) / len(union) if union else 0.0
                            if similarity < 0.6:
                                overall_match = False
                                discrepancies.append({
                                    "type": "name_mismatch",
                                    "field": "name",
                                    "values": {doc_a: name_a, doc_b: name_b},
                                    "similarity": similarity,
                                })
                                results.append({
                                    "check": "name_consistency",
                                    "status": "mismatch",
                                    "message": f"Name mismatch between {doc_a} and {doc_b}: '{name_a}' vs '{name_b}' (similarity={similarity:.2f})",
                                })

        elif comparison_type == "income_consistency":
            income_values = {}
            bank_data = extracted_data.get("bank_statement", {})
            app_data = extracted_data.get("application_form", {})

            if bank_data:
                closing_balance = bank_data.get("closing_balance")
                if closing_balance is not None:
                    income_values["bank_statement"] = float(closing_balance)

            if app_data:
                monthly_income = app_data.get("total_monthly_income")
                if monthly_income is not None:
                    income_values["application_form"] = float(monthly_income)

            if len(income_values) >= 2:
                values = list(income_values.values())
                min_val = min(values)
                max_val = max(values)
                if max_val > 0:
                    variance_pct = ((max_val - min_val) / max_val) * 100
                    if variance_pct > 20:
                        overall_match = False
                        discrepancies.append({
                            "type": "income_mismatch",
                            "field": "income",
                            "values": income_values,
                            "variance_pct": variance_pct,
                        })
                        results.append({
                            "check": "income_consistency",
                            "status": "mismatch",
                            "message": f"Income variance {variance_pct:.1f}% across documents",
                        })
                    else:
                        results.append({
                            "check": "income_consistency",
                            "status": "match",
                            "message": f"Income consistent (variance {variance_pct:.1f}%)",
                        })

        elif comparison_type == "address_consistency":
            addresses = {}
            for doc_type, data in extracted_data.items():
                address = data.get("address")
                if address:
                    addresses[doc_type] = str(address).lower().strip()

            if len(addresses) >= 2:
                addr_list = list(addresses.items())
                for i in range(len(addr_list)):
                    for j in range(i + 1, len(addr_list)):
                        doc_a, addr_a = addr_list[i]
                        doc_b, addr_b = addr_list[j]
                        if addr_a != addr_b and len(addr_a) > 3 and len(addr_b) > 3:
                            overall_match = False
                            discrepancies.append({
                                "type": "address_mismatch",
                                "field": "address",
                                "values": {doc_a: addr_a, doc_b: addr_b},
                            })
                            results.append({
                                "check": "address_consistency",
                                "status": "mismatch",
                                "message": f"Address mismatch between {doc_a} and {doc_b}",
                            })

        if overall_match:
            confidence = 1.0
        else:
            confidence = max(0.0, 1.0 - (len(discrepancies) * 0.1))

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "cross_document_compare_complete",
            comparison_type=comparison_type,
            overall_match=overall_match,
            discrepancy_count=len(discrepancies),
            confidence=round(confidence, 2),
            duration_ms=round(duration_ms, 2),
        )

        return {
            "comparison_type": comparison_type,
            "results": results,
            "overall_match": overall_match,
            "discrepancies": discrepancies,
            "confidence": confidence,
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "cross_document_compare_error",
            comparison_type=comparison_type,
            error=str(e),
            duration_ms=round(duration_ms, 2),
        )
        return {
            "comparison_type": comparison_type,
            "results": [],
            "overall_match": False,
            "discrepancies": [],
            "confidence": 0.0,
            "error": str(e),
        }


@tool
def discrepancy_classify_tool(
    discrepancy: dict,
    extraction_confidence: dict[str, float],
) -> dict:
    """Classify whether a discrepancy is an OCR error or a real inconsistency.

    Use for: Judging if a mismatch is due to extraction error or actual data inconsistency.
    Returns: Classification (ocr_error/real_discrepancy/ambiguous) with confidence and reasoning.

    Args:
        discrepancy: Discrepancy dict with type, field, values, and optional similarity/variance.
        extraction_confidence: Dict mapping document_type -> extraction confidence score.

    Returns:
        Dict with classification, confidence, reasoning, and recommended_action.
    """
    start = time.perf_counter()

    logger.debug(
        "discrepancy_classify_start",
        discrepancy_type=discrepancy.get("type"),
        field=discrepancy.get("field"),
    )

    try:
        disc_type = discrepancy.get("type", "unknown")
        field = discrepancy.get("field", "unknown")
        values = discrepancy.get("values", {})

        avg_confidence = sum(extraction_confidence.values()) / len(extraction_confidence) if extraction_confidence else 0.0

        classification = "ambiguous"
        confidence = 0.5
        reasoning = ""
        recommended_action = "manual_review"

        if disc_type == "name_mismatch":
            similarity = discrepancy.get("similarity", 0.0)
            if similarity >= 0.8 and avg_confidence >= 0.85:
                classification = "ocr_error"
                confidence = 0.85
                reasoning = f"High name similarity ({similarity:.2f}) and high extraction confidence ({avg_confidence:.2f}). Likely OCR variation (e.g., middle initial vs full name)."
                recommended_action = "accept_with_note"
            elif similarity < 0.6:
                classification = "real_discrepancy"
                confidence = 0.90
                reasoning = f"Low name similarity ({similarity:.2f}). Likely real discrepancy requiring clarification."
                recommended_action = "request_clarification"

        elif disc_type == "income_mismatch":
            variance_pct = discrepancy.get("variance_pct", 0.0)
            if variance_pct <= 10 and avg_confidence >= 0.85:
                classification = "ocr_error"
                confidence = 0.80
                reasoning = f"Small income variance ({variance_pct:.1f}%) with high extraction confidence. Likely OCR rounding or formatting difference."
                recommended_action = "accept_with_note"
            elif variance_pct > 20:
                classification = "real_discrepancy"
                confidence = 0.90
                reasoning = f"Large income variance ({variance_pct:.1f}%). Likely real discrepancy requiring clarification."
                recommended_action = "request_clarification"

        elif disc_type == "identity_mismatch":
            classification = "real_discrepancy"
            confidence = 0.95
            reasoning = "Identity number mismatch is critical and unlikely to be OCR error."
            recommended_action = "escalate"

        elif disc_type == "address_mismatch":
            if avg_confidence >= 0.90:
                classification = "real_discrepancy"
                confidence = 0.75
                reasoning = "Address mismatch with high extraction confidence. Applicant may have moved or used different address formats."
                recommended_action = "request_clarification"
            else:
                classification = "ambiguous"
                confidence = 0.60
                reasoning = "Address mismatch with moderate extraction confidence. Could be OCR error or real discrepancy."
                recommended_action = "request_clarification"

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "discrepancy_classified",
            discrepancy_type=disc_type,
            classification=classification,
            confidence=round(confidence, 2),
            recommended_action=recommended_action,
            duration_ms=round(duration_ms, 2),
        )

        return {
            "discrepancy_type": disc_type,
            "field": field,
            "classification": classification,
            "confidence": confidence,
            "reasoning": reasoning,
            "recommended_action": recommended_action,
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "discrepancy_classify_error",
            discrepancy_type=discrepancy.get("type"),
            error=str(e),
            duration_ms=round(duration_ms, 2),
        )
        return {
            "discrepancy_type": discrepancy.get("type", "unknown"),
            "field": discrepancy.get("field", "unknown"),
            "classification": "error",
            "confidence": 0.0,
            "reasoning": f"Classification failed: {e}",
            "recommended_action": "manual_review",
        }


@tool
def applicant_clarify_tool(
    discrepancy: dict,
    applicant_context: dict,
) -> dict:
    """Generate a clarification question for the applicant.

    Use for: Asking applicant to resolve ambiguous discrepancies.
    Returns: Formulated question, context, and priority.

    Args:
        discrepancy: Discrepancy dict with type, field, values, and classification.
        applicant_context: Dict with applicant_id, application_id, support_category, and language preference.

    Returns:
        Dict with question, field, discrepancy_type, priority, and context.
    """
    start = time.perf_counter()

    logger.debug(
        "applicant_clarify_start",
        discrepancy_type=discrepancy.get("type"),
        applicant_id=applicant_context.get("applicant_id"),
    )

    try:
        disc_type = discrepancy.get("type", "unknown")
        field = discrepancy.get("field", "unknown")
        values = discrepancy.get("values", {})
        classification = discrepancy.get("classification", "ambiguous")

        question = ""
        priority = "medium"

        if disc_type == "name_mismatch":
            doc_types = list(values.keys())
            name_values = list(values.values())
            question = (
                f"We noticed a slight difference in how your name appears on your documents. "
                f"On your {doc_types[0]}, it shows '{name_values[0]}', "
                f"but on your {doc_types[1]}, it shows '{name_values[1]}'. "
                f"Could you confirm your full legal name as it appears on your Emirates ID?"
            )
            priority = "medium"

        elif disc_type == "income_mismatch":
            doc_types = list(values.keys())
            income_values = list(values.values())
            question = (
                f"There's a discrepancy in the income information you provided. "
                f"Your {doc_types[0]} shows {income_values[0]:,.2f} AED, "
                f"but your {doc_types[1]} shows {income_values[1]:,.2f} AED. "
                f"Could you clarify your total monthly income?"
            )
            priority = "high"

        elif disc_type == "identity_mismatch":
            question = (
                f"We found inconsistent identity numbers across your documents. "
                f"This is a critical issue that needs to be resolved. "
                f"Please verify your Emirates ID number and ensure all documents match."
            )
            priority = "critical"

        elif disc_type == "address_mismatch":
            doc_types = list(values.keys())
            question = (
                f"We noticed your address appears differently on your documents. "
                f"Could you confirm your current residential address?"
            )
            priority = "low"

        else:
            question = (
                f"We need clarification on some information in your application. "
                f"Please review your documents and ensure all information is consistent."
            )
            priority = "medium"

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "clarification_question_generated",
            discrepancy_type=disc_type,
            priority=priority,
            applicant_id=applicant_context.get("applicant_id"),
            duration_ms=round(duration_ms, 2),
        )

        return {
            "question": question,
            "field": field,
            "discrepancy_type": disc_type,
            "priority": priority,
            "classification": classification,
            "applicant_id": applicant_context.get("applicant_id"),
            "application_id": applicant_context.get("application_id"),
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "applicant_clarify_error",
            discrepancy_type=discrepancy.get("type"),
            error=str(e),
            duration_ms=round(duration_ms, 2),
        )
        return {
            "question": "We need additional information to process your application. Please contact support.",
            "field": discrepancy.get("field", "unknown"),
            "discrepancy_type": discrepancy.get("type", "unknown"),
            "priority": "high",
            "classification": "error",
            "error": str(e),
        }


@tool
def validation_confidence_tool(
    validation_results: dict,
    discrepancies: list[dict],
) -> dict:
    """Compute overall validation confidence score.

    Use for: Assessing whether validation is complete or needs more work.
    Returns: Confidence score, recommendation, and summary.

    Args:
        validation_results: Dict with per_document_validation and cross_document_validation results.
        discrepancies: List of discrepancy dicts with type, classification, confidence, and resolution_status.

    Returns:
        Dict with overall_confidence, recommendation, unresolved_count, and summary.
    """
    start = time.perf_counter()

    logger.debug(
        "validation_confidence_start",
        discrepancy_count=len(discrepancies),
    )

    try:
        confidences = []

        per_doc_results = validation_results.get("per_document_validation", {})
        for doc_id, result in per_doc_results.items():
            if isinstance(result, dict) and "confidence" in result:
                confidences.append(result["confidence"])

        cross_doc_results = validation_results.get("cross_document_validation", {})
        for check_type, result in cross_doc_results.items():
            if isinstance(result, dict) and "confidence" in result:
                confidences.append(result["confidence"])

        base_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        unresolved_discrepancies = [
            d for d in discrepancies
            if d.get("resolution_status") == "unresolved"
        ]
        unresolved_count = len(unresolved_discrepancies)

        critical_discrepancies = [
            d for d in unresolved_discrepancies
            if d.get("discrepancy_type") in ["identity_mismatch", "income_mismatch"]
        ]

        confidence_penalty = unresolved_count * 0.05
        critical_penalty = len(critical_discrepancies) * 0.10
        overall_confidence = max(0.0, base_confidence - confidence_penalty - critical_penalty)

        if overall_confidence >= 0.90 and unresolved_count == 0:
            recommendation = "proceed_to_decision"
        elif overall_confidence >= 0.80:
            recommendation = "proceed_to_review"
        elif overall_confidence >= 0.70:
            recommendation = "manual_review"
        else:
            recommendation = "escalate"

        summary = {
            "total_documents_validated": len(per_doc_results),
            "total_cross_doc_checks": len(cross_doc_results),
            "total_discrepancies": len(discrepancies),
            "unresolved_discrepancies": unresolved_count,
            "critical_discrepancies": len(critical_discrepancies),
            "base_confidence": round(base_confidence, 2),
        }

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "validation_confidence_complete",
            overall_confidence=round(overall_confidence, 2),
            recommendation=recommendation,
            unresolved_count=unresolved_count,
            critical_count=len(critical_discrepancies),
            duration_ms=round(duration_ms, 2),
        )

        return {
            "overall_confidence": overall_confidence,
            "recommendation": recommendation,
            "unresolved_count": unresolved_count,
            "critical_count": len(critical_discrepancies),
            "summary": summary,
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "validation_confidence_error",
            error=str(e),
            duration_ms=round(duration_ms, 2),
        )
        return {
            "overall_confidence": 0.0,
            "recommendation": "escalate",
            "unresolved_count": 0,
            "critical_count": 0,
            "summary": {"error": str(e)},
        }
