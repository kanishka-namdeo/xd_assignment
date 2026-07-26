"""Cross-document comparison functions.

Pure domain logic for comparing extracted data across multiple documents.
No I/O operations.
"""

from typing import Any


def check_identity_match(extracted_data: dict[str, dict]) -> dict[str, Any]:
    """Check if identity numbers match across all documents.

    Args:
        extracted_data: Dict mapping document_type -> extracted data dict.

    Returns:
        Comparison result with status, message, and discrepancies.
    """
    identity_numbers: dict[str, str] = {}
    for doc_type, data in extracted_data.items():
        identity_num = data.get("identity_number")
        if identity_num:
            identity_numbers[doc_type] = str(identity_num).replace("-", "").replace(" ", "")

    results = []
    discrepancies = []

    if len(identity_numbers) >= 2:
        unique_values = set(identity_numbers.values())
        if len(unique_values) > 1:
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

    return {
        "comparison_type": "identity_match",
        "results": results,
        "overall_match": len(discrepancies) == 0,
        "discrepancies": discrepancies,
        "confidence": 1.0 if not discrepancies else max(0.0, 1.0 - len(discrepancies) * 0.15),
    }


def check_name_consistency(extracted_data: dict[str, dict]) -> dict[str, Any]:
    """Check if names are consistent across documents.

    Args:
        extracted_data: Dict mapping document_type -> extracted data dict.

    Returns:
        Comparison result with pairwise name similarity checks.
    """
    names: dict[str, str] = {}
    for doc_type, data in extracted_data.items():
        name = (
            data.get("full_name_en")
            or data.get("full_name")
            or data.get("applicant_name")
            or data.get("account_holder_name")
        )
        if name:
            names[doc_type] = " ".join(str(name).strip().lower().split())

    results = []
    discrepancies = []
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
                similarity = len(intersection) / len(union)
                if similarity < 0.6:
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

    return {
        "comparison_type": "name_consistency",
        "results": results,
        "overall_match": len(discrepancies) == 0,
        "discrepancies": discrepancies,
        "confidence": 1.0 if not discrepancies else max(0.0, 1.0 - len(discrepancies) * 0.1),
    }


def check_income_consistency(extracted_data: dict[str, dict]) -> dict[str, Any]:
    """Check if income values are consistent across documents.

    Args:
        extracted_data: Dict mapping document_type -> extracted data dict.

    Returns:
        Comparison result with income variance analysis.
    """
    income_values: dict[str, float] = {}
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

    results = []
    discrepancies = []

    if len(income_values) >= 2:
        values = list(income_values.values())
        min_val = min(values)
        max_val = max(values)
        if max_val > 0:
            variance_pct = ((max_val - min_val) / max_val) * 100
            if variance_pct > 20:
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

    return {
        "comparison_type": "income_consistency",
        "results": results,
        "overall_match": len(discrepancies) == 0,
        "discrepancies": discrepancies,
        "confidence": 1.0 if not discrepancies else max(0.0, 1.0 - len(discrepancies) * 0.1),
    }


def check_address_consistency(extracted_data: dict[str, dict]) -> dict[str, Any]:
    """Check if addresses are consistent across documents.

    Args:
        extracted_data: Dict mapping document_type -> extracted data dict.

    Returns:
        Comparison result with address mismatch details.
    """
    addresses: dict[str, str] = {}
    for doc_type, data in extracted_data.items():
        address = data.get("address")
        if address:
            addresses[doc_type] = str(address).lower().strip()

    results = []
    discrepancies = []
    addr_list = list(addresses.items())

    for i in range(len(addr_list)):
        for j in range(i + 1, len(addr_list)):
            doc_a, addr_a = addr_list[i]
            doc_b, addr_b = addr_list[j]
            if addr_a != addr_b and len(addr_a) > 3 and len(addr_b) > 3:
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

    return {
        "comparison_type": "address_consistency",
        "results": results,
        "overall_match": len(discrepancies) == 0,
        "discrepancies": discrepancies,
        "confidence": 1.0 if not discrepancies else max(0.0, 1.0 - len(discrepancies) * 0.1),
    }


COMPARISONS: dict[str, Any] = {
    "identity_match": check_identity_match,
    "name_consistency": check_name_consistency,
    "income_consistency": check_income_consistency,
    "address_consistency": check_address_consistency,
}
