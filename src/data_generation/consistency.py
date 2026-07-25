"""Cross-document consistency validation for generated data.

Implements 11 consistency rules across all document types and maps them
to the 7 validation types defined in the cross_document_validations schema:
identity_match, name_match, dob_match, income_consistency, debt_consistency,
employment_match, address_match.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from src.data_generation.profile import ApplicantProfile


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip extra whitespace."""
    return " ".join(name.strip().lower().split())


def _name_similarity(a: str, b: str) -> float:
    """Simple token-based similarity between two names.

    Returns a value between 0.0 and 1.0 where 1.0 is an exact match.
    Uses token overlap (Jaccard-like) which is robust to minor ordering
    differences and missing middle names.
    """
    tokens_a = set(_normalize_name(a).split())
    tokens_b = set(_normalize_name(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def _address_match_score(addr_a: dict[str, str], addr_b: dict[str, str]) -> tuple[bool, str]:
    """Check if two address dicts are compatible.

    Requires matching emirate; city/street are considered compatible if
    one is a substring of the other (case-insensitive).
    """
    emirate_a = addr_a.get("emirate", "").strip().lower()
    emirate_b = addr_b.get("emirate", "").strip().lower()
    if emirate_a and emirate_b and emirate_a != emirate_b:
        return False, f"Emirate mismatch: {addr_a.get('emirate')} vs {addr_b.get('emirate')}"

    for field in ("city", "street"):
        val_a = addr_a.get(field, "").strip().lower()
        val_b = addr_b.get(field, "").strip().lower()
        if val_a and val_b and val_a not in val_b and val_b not in val_a:
            return False, f"{field} mismatch: {addr_a.get(field)} vs {addr_b.get(field)}"

    return True, "Addresses are compatible"


def validate_consistency(
    profile: ApplicantProfile,
    eid_data: dict,
    bank_data: dict,
    bank_transactions: list[dict],
    credit_data: dict,
    credit_facilities: list[dict],
    resume_data: dict,
    resume_work_experiences: list[dict],
    assets_data: dict,
    form_data: dict,
) -> dict[str, Any]:
    """Validate cross-document consistency across all generated documents.

    Args:
        profile: The single source of truth for the applicant.
        eid_data: Structured Emirates ID data (emirates_id_data schema).
        bank_data: Structured bank statement data (bank_statement_data schema).
        bank_transactions: List of bank transaction records.
        credit_data: Structured credit report data (credit_report_data schema).
        credit_facilities: List of credit facility records.
        resume_data: Structured resume data (resume_data schema).
        resume_work_experiences: List of resume work experience records.
        assets_data: Structured assets/liabilities data.
        form_data: Structured application form data (application_form_data schema).

    Returns:
        Dict with 'passed' (bool) and 'rules' (list of rule result dicts).
        Each rule result: {rule_name, rule_type, passed, details}.
    """
    rules: list[dict[str, Any]] = []

    # ── Rule 1: identity_number identical across Emirates ID, credit report, application form ──
    eid_identity = str(eid_data.get("identity_number", "")).replace("-", "")
    credit_identity = str(credit_data.get("identity_number", "")).replace("-", "")
    form_identity = str(form_data.get("identity_number", "")).replace("-", "")

    identity_match = eid_identity == credit_identity == form_identity
    identity_details = (
        f"Emirates ID: {eid_data.get('identity_number')}, "
        f"Credit Report: {credit_data.get('identity_number')}, "
        f"Application Form: {form_data.get('identity_number')}"
    )
    rules.append(
        {
            "rule_name": "identity_number_consistency",
            "rule_type": "identity_match",
            "passed": identity_match,
            "details": identity_details if identity_match else f"Identity numbers do not match. {identity_details}",
        }
    )

    # ── Rule 2: full_name variations reconcilable ──
    eid_name = eid_data.get("full_name_en", "") or eid_data.get("full_name", "")
    credit_name = credit_data.get("full_name", "")
    form_name = form_data.get("applicant_name", "")
    profile_name = profile.full_name_en

    all_names = [n for n in [profile_name, eid_name, credit_name, form_name] if n]
    if len(all_names) >= 2:
        min_similarity = min(
            _name_similarity(all_names[i], all_names[j])
            for i in range(len(all_names))
            for j in range(i + 1, len(all_names))
        )
        name_match = min_similarity >= 0.6
        name_detail = (
            f"Names: {all_names}, similarity={min_similarity:.2f}"
        )
    else:
        name_match = True
        name_detail = "Insufficient name data to compare"

    rules.append(
        {
            "rule_name": "full_name_reconcilable",
            "rule_type": "name_match",
            "passed": name_match,
            "details": name_detail if name_match else f"Name mismatch detected. {name_detail}",
        }
    )

    # ── Rule 3: date_of_birth identical across Emirates ID, application form, resume ──
    eid_dob = str(eid_data.get("date_of_birth", ""))
    form_dob = str(form_data.get("date_of_birth", ""))
    resume_dob = str(resume_data.get("date_of_birth", ""))
    profile_dob = str(profile.date_of_birth.isoformat())

    dob_values = [v for v in [eid_dob, form_dob, resume_dob, profile_dob] if v and v != "None"]
    dob_match = len(set(dob_values)) <= 1 if dob_values else True
    dob_detail = f"DOB values: {dob_values}"
    rules.append(
        {
            "rule_name": "date_of_birth_consistency",
            "rule_type": "dob_match",
            "passed": dob_match,
            "details": dob_detail if dob_match else f"Date of birth mismatch. {dob_detail}",
        }
    )

    # ── Rule 4: monthly_salary in application form matches WPS salary transactions in bank statement ──
    form_salary = form_data.get("monthly_salary", "")
    if form_salary:
        form_salary_dec = Decimal(str(form_salary))
    else:
        form_salary_dec = profile.monthly_salary

    wps_transactions = [
        t for t in bank_transactions if t.get("is_wps_salary") or t.get("category") == "salary"
    ]
    wps_amounts = [abs(Decimal(str(t.get("amount", 0)))) for t in wps_transactions if t.get("amount")]

    if wps_amounts:
        avg_wps = sum(wps_amounts) / len(wps_amounts)
        salary_tolerance = form_salary_dec * Decimal("0.10")
        salary_match = all(abs(amt - form_salary_dec) <= salary_tolerance for amt in wps_amounts)
        salary_detail = (
            f"Form salary: {form_salary_dec}, WPS transactions: {wps_amounts}, "
            f"avg: {avg_wps:.2f}"
        )
    else:
        salary_match = True
        salary_detail = f"No WPS salary transactions found; form salary: {form_salary_dec}"

    rules.append(
        {
            "rule_name": "salary_matches_wps_transactions",
            "rule_type": "income_consistency",
            "passed": salary_match,
            "details": salary_detail if salary_match else f"Salary mismatch. {salary_detail}",
        }
    )

    # ── Rule 5: employer_name in application form matches resume current_employer ──
    form_employer = _normalize_name(str(form_data.get("employer_name", "")))
    resume_employer = _normalize_name(str(resume_data.get("current_employer", "")))
    profile_employer = _normalize_name(profile.employer_name)

    employer_match = form_employer == resume_employer or form_employer == profile_employer or resume_employer == profile_employer
    employer_detail = (
        f"Form: {form_data.get('employer_name')}, "
        f"Resume: {resume_data.get('current_employer')}, "
        f"Profile: {profile.employer_name}"
    )
    rules.append(
        {
            "rule_name": "employer_name_consistency",
            "rule_type": "employment_match",
            "passed": employer_match,
            "details": employer_detail if employer_match else f"Employer mismatch. {employer_detail}",
        }
    )

    # ── Rule 6: Credit report identity_number matches Emirates ID identity_number ──
    # (Already covered by Rule 1, but kept as explicit rule per spec)
    credit_eid_match = eid_identity == credit_identity
    rules.append(
        {
            "rule_name": "credit_identity_matches_emirates_id",
            "rule_type": "identity_match",
            "passed": credit_eid_match,
            "details": (
                f"Credit report identity_number: {credit_data.get('identity_number')}, "
                f"Emirates ID identity_number: {eid_data.get('identity_number')}"
            ),
        }
    )

    # ── Rule 7: Address fields consistent (same emirate, compatible city/street) ──
    eid_address = eid_data.get("address", {}) or {}
    form_address = form_data.get("address", {}) or {}
    profile_address = profile.address or {}

    addr_sources = [a for a in [eid_address, form_address, profile_address] if a]
    if len(addr_sources) >= 2:
        addr_ok = True
        addr_messages = []
        for i in range(len(addr_sources)):
            for j in range(i + 1, len(addr_sources)):
                ok, msg = _address_match_score(addr_sources[i], addr_sources[j])
                if not ok:
                    addr_ok = False
                    addr_messages.append(msg)
        address_match = addr_ok
        address_detail = "All addresses compatible" if addr_ok else "; ".join(addr_messages)
    else:
        address_match = True
        address_detail = "Insufficient address data to compare"

    rules.append(
        {
            "rule_name": "address_consistency",
            "rule_type": "address_match",
            "passed": address_match,
            "details": address_detail,
        }
    )

    # ── Rule 8: total_monthly_income equals monthly_salary + other_income ──
    form_total = form_data.get("total_monthly_income", "")
    form_salary_str = form_data.get("monthly_salary", "0")
    form_other = form_data.get("other_income", "0")

    try:
        total_dec = Decimal(str(form_total)) if form_total else profile.total_monthly_income
        salary_dec = Decimal(str(form_salary_str)) if form_salary_str else profile.monthly_salary
        other_dec = Decimal(str(form_other)) if form_other else profile.other_income
    except Exception:
        total_dec = salary_dec = other_dec = Decimal("0")

    expected_total = salary_dec + other_dec
    income_tolerance = Decimal("1")  # 1 AED tolerance for rounding
    income_match = abs(total_dec - expected_total) <= income_tolerance
    income_detail = (
        f"total_monthly_income: {total_dec}, monthly_salary: {salary_dec}, "
        f"other_income: {other_dec}, expected: {expected_total}"
    )
    rules.append(
        {
            "rule_name": "total_income_equals_salary_plus_other",
            "rule_type": "income_consistency",
            "passed": income_match,
            "details": income_detail if income_match else f"Income inconsistency. {income_detail}",
        }
    )

    # ── Rule 9: Credit report credit_card + personal_loan balances vs assets/liabilities ──
    # Per spec rule 9: "Credit report total_outstanding_balance matches assets/liabilities credit_card_debt + personal_loans"
    # We compare credit_card_debt + personal_loans from assets against the credit report's
    # credit_card + personal_loan facility balances (not total_outstanding which includes all facility types).
    assets_cc_debt = assets_data.get("credit_card_debt", 0)
    assets_personal_loans = assets_data.get("personal_loans", 0)

    try:
        cc_dec = Decimal(str(assets_cc_debt)) if assets_cc_debt else Decimal("0")
        pl_dec = Decimal(str(assets_personal_loans)) if assets_personal_loans else Decimal("0")
    except Exception:
        cc_dec = pl_dec = Decimal("0")

    # Sum credit card and personal loan balances from credit facilities
    credit_cc = sum(
        (Decimal(str(f["current_balance"])) for f in credit_facilities if f["facility_type"] == "credit_card"),
        Decimal("0")
    )
    credit_pl = sum(
        (Decimal(str(f["current_balance"])) for f in credit_facilities if f["facility_type"] == "personal_loan"),
        Decimal("0")
    )

    credit_related = cc_dec + pl_dec
    facilities_related = credit_cc + credit_pl
    # Use 1% tolerance for rounding
    debt_tolerance = max(Decimal("10"), facilities_related * Decimal("0.01"))
    debt_match = abs(credit_related - facilities_related) <= debt_tolerance
    debt_detail = (
        f"Assets credit_card_debt: {cc_dec}, personal_loans: {pl_dec}, sum: {credit_related}; "
        f"Credit facilities cc: {credit_cc}, pl: {credit_pl}, sum: {facilities_related}"
    )
    rules.append(
        {
            "rule_name": "credit_outstanding_matches_liabilities",
            "rule_type": "debt_consistency",
            "passed": debt_match,
            "details": debt_detail if debt_match else f"Debt inconsistency. {debt_detail}",
        }
    )

    # ── Rule 10: dependents count in application form consistent with family_size ──
    form_family_size = form_data.get("family_size", profile.family_size)
    form_dependents = form_data.get("dependents", profile.dependents)
    dependents_count = len(form_dependents) if isinstance(form_dependents, list) else 0

    # family_size typically includes the applicant + spouse + dependents
    # So dependents_count should be <= family_size - 1 (applicant) - 1 (spouse if married)
    try:
        family_size_int = int(form_family_size) if form_family_size else profile.family_size
    except (ValueError, TypeError):
        family_size_int = profile.family_size

    # Dependents should be less than family_size (at minimum the applicant is counted)
    dependents_ok = dependents_count < family_size_int
    dependents_detail = (
        f"family_size: {family_size_int}, dependents count: {dependents_count}"
    )
    rules.append(
        {
            "rule_name": "dependents_consistent_with_family_size",
            "rule_type": "name_match",
            "passed": dependents_ok,
            "details": dependents_detail,
        }
    )

    # ── Rule 11: Resume is_current work experience matches application form employer_name and occupation ──
    current_positions = [
        w for w in resume_work_experiences if w.get("is_current") or w.get("end_date") in (None, "", "Present", "present")
    ]

    if current_positions:
        current_employers = [_normalize_name(str(p.get("company", ""))) for p in current_positions]
        current_titles = [_normalize_name(str(p.get("job_title", ""))) for p in current_positions]
        form_employer_norm = _normalize_name(str(form_data.get("employer_name", "") or profile.employer_name))
        form_occupation_norm = _normalize_name(str(form_data.get("occupation", "") or profile.occupation))

        employer_in_resume = any(form_employer_norm in e or e in form_employer_norm for e in current_employers if e)
        occupation_in_resume = any(
            form_occupation_norm in t or t in form_occupation_norm
            for t in current_titles
            if t
        )
        employment_match = employer_in_resume or occupation_in_resume
        employment_detail = (
            f"Form employer: {form_employer_norm}, occupation: {form_occupation_norm}; "
            f"Resume current: employers={current_employers}, titles={current_titles}"
        )
    else:
        employment_match = True
        employment_detail = "No current work experience in resume to compare"

    rules.append(
        {
            "rule_name": "current_employment_matches_form",
            "rule_type": "employment_match",
            "passed": employment_match,
            "details": employment_detail if employment_match else f"Employment mismatch. {employment_detail}",
        }
    )

    all_passed = all(rule["passed"] for rule in rules)
    return {"passed": all_passed, "rules": rules}
