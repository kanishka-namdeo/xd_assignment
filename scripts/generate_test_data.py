"""Generate synthetic test data for 3 applicant profiles.

Produces three cross-document-consistent applicant profiles:
  1. divorced_employed_good_credit  -> expected: approved
  2. abandoned_unemployed_poor_credit -> expected: manual_review
  3. unknown_parentage_self_employed_borderline -> expected: soft_decline

Each profile includes:
  - Emirates ID image (front/back PNG)
  - Bank statement PDF
  - Credit report PDF
  - Application form PNG
  - profile.json with structured data
"""

import json
import sys
from pathlib import Path

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date, timedelta
from decimal import Decimal

from src.data_generation.applicant_generator import generate_applicant
from src.data_generation.emirates_id_generator import generate_emirates_id
from src.data_generation.bank_statement_generator import generate_bank_statement
from src.data_generation.credit_report_generator import generate_credit_report
from src.data_generation.application_form_generator import generate_application_form
from src.data_generation.profile import ApplicantProfile


OUTPUT_DIR = PROJECT_ROOT / "data" / "test_applicants"


def _build_profile(
    seed: int,
    marital_status: str,
    employment_status: str,
    monthly_salary: Decimal,
    family_size: int,
    support_category: str,
    credit_score_override: int | None = None,
) -> ApplicantProfile:
    """Build a deterministic ApplicantProfile with overridden fields."""
    rng_seed = seed * 1000 + 42
    profile = generate_applicant(rng_seed)

    # Override key fields for the test scenario
    profile_dict = profile.model_dump()
    profile_dict["marital_status"] = marital_status
    profile_dict["employment_status"] = employment_status
    profile_dict["monthly_salary"] = monthly_salary
    profile_dict["other_income"] = Decimal("0")
    profile_dict["total_monthly_income"] = monthly_salary
    profile_dict["family_size"] = family_size
    profile_dict["support_category"] = support_category

    # Set employer based on employment status
    if employment_status == "unemployed":
        profile_dict["employer_name"] = "N/A"
        profile_dict["occupation"] = "N/A"
    elif employment_status == "self_employed":
        profile_dict["employer_name"] = "Self-Employed"
    else:
        profile_dict["employer_name"] = "Al Noor Trading Establishment"
        profile_dict["occupation"] = "Administrative Assistant"

    # Generate dependents based on family_size
    dependents = []
    for i in range(max(0, family_size - 1)):
        dependents.append({
            "name": f"Dependent {i + 1}",
            "age_group": "0-18",
            "relation": "child",
        })
    profile_dict["dependents"] = dependents

    # Housing
    profile_dict["housing_status"] = "rented"
    profile_dict["monthly_rent"] = Decimal("3500") if monthly_salary > 5000 else Decimal("2000")
    profile_dict["monthly_mortgage"] = Decimal("0")

    # Declaration
    profile_dict["is_declaration_signed"] = True
    profile_dict["declaration_date"] = date.today().isoformat()

    # Supporting documents based on category
    support_doc_map = {
        "divorced": ["divorce_certificate", "emirates_id", "bank_statement", "credit_report"],
        "abandoned": ["emirates_id", "bank_statement", "credit_report", "assets_liabilities"],
        "unknown_parentage": ["emirates_id", "bank_statement", "application_form"],
    }
    profile_dict["supporting_documents"] = support_doc_map.get(support_category, ["emirates_id"])

    return ApplicantProfile(**profile_dict)


def _generate_profile_documents(profile: ApplicantProfile, seed: int, output_dir: Path) -> dict:
    """Generate all documents for a profile and save to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    documents = {}

    # 1. Emirates ID
    print(f"  Generating Emirates ID...")
    eid_data, front_img, back_img = generate_emirates_id(profile, seed)
    front_path = output_dir / "emirates_id_front.png"
    back_path = output_dir / "emirates_id_back.png"
    front_img.save(front_path, format="PNG")
    back_img.save(back_path, format="PNG")
    documents["emirates_id"] = {
        "data": eid_data,
        "files": [str(front_path), str(back_path)],
    }

    # 2. Bank Statement
    print(f"  Generating Bank Statement...")
    bank_data, transactions, bank_pdf_path = generate_bank_statement(profile, seed + 1)
    # Move PDF to our output dir
    target_bank_pdf = output_dir / "bank_statement.pdf"
    if bank_pdf_path.exists():
        target_bank_pdf.write_bytes(bank_pdf_path.read_bytes())
    documents["bank_statement"] = {
        "data": bank_data,
        "files": [str(target_bank_pdf)],
    }

    # 3. Credit Report
    print(f"  Generating Credit Report...")
    credit_data, facilities, credit_pdf_path = generate_credit_report(profile, seed + 2)
    target_credit_pdf = output_dir / "credit_report.pdf"
    if credit_pdf_path.exists():
        target_credit_pdf.write_bytes(credit_pdf_path.read_bytes())
    documents["credit_report"] = {
        "data": credit_data,
        "files": [str(target_credit_pdf)],
    }

    # 4. Application Form
    print(f"  Generating Application Form...")
    form_data, form_img_path = generate_application_form(profile, seed + 3)
    target_form_png = output_dir / "application_form.png"
    if form_img_path.exists():
        target_form_png.write_bytes(form_img_path.read_bytes())
    documents["application_form"] = {
        "data": form_data,
        "files": [str(target_form_png)],
    }

    return documents


def generate_profile_1_approved() -> tuple[ApplicantProfile, dict]:
    """Profile 1: Divorced, employed, good credit -> should approve."""
    print("\n[Profile 1] Divorced, Employed, Good Credit (Expected: Approved)")
    profile = _build_profile(
        seed=1,
        marital_status="divorced",
        employment_status="employed",
        monthly_salary=Decimal("15000"),
        family_size=3,
        support_category="divorced",
    )
    print(f"  Name: {profile.full_name_en}")
    print(f"  ID: {profile.identity_number}")
    print(f"  Salary: AED {profile.monthly_salary}")
    print(f"  Status: {profile.marital_status}, {profile.employment_status}")
    return profile


def generate_profile_2_manual_review() -> tuple[ApplicantProfile, dict]:
    """Profile 2: Abandoned, unemployed, poor credit -> should manual_review."""
    print("\n[Profile 2] Abandoned, Unemployed, Poor Credit (Expected: Manual Review)")
    profile = _build_profile(
        seed=2,
        marital_status="abandoned",
        employment_status="unemployed",
        monthly_salary=Decimal("800"),
        family_size=5,
        support_category="abandoned",
    )
    print(f"  Name: {profile.full_name_en}")
    print(f"  ID: {profile.identity_number}")
    print(f"  Salary: AED {profile.monthly_salary}")
    print(f"  Status: {profile.marital_status}, {profile.employment_status}")
    return profile


def generate_profile_3_soft_decline() -> tuple[ApplicantProfile, dict]:
    """Profile 3: Unknown parentage, self-employed, borderline -> should soft_decline."""
    print("\n[Profile 3] Unknown Parentage, Self-Employed, Borderline (Expected: Soft Decline)")
    profile = _build_profile(
        seed=3,
        marital_status="single",
        employment_status="self_employed",
        monthly_salary=Decimal("6500"),
        family_size=2,
        support_category="unknown_parentage",
    )
    print(f"  Name: {profile.full_name_en}")
    print(f"  ID: {profile.identity_number}")
    print(f"  Salary: AED {profile.monthly_salary}")
    print(f"  Status: {profile.marital_status}, {profile.employment_status}")
    return profile


def main() -> None:
    """Generate all test applicant profiles and documents."""
    print("=" * 60)
    print("UAE Social Support Application - Synthetic Test Data Generator")
    print("=" * 60)

    profiles = [
        ("divorced_employed_good_credit", generate_profile_1_approved, "approved"),
        ("abandoned_unemployed_poor_credit", generate_profile_2_manual_review, "manual_review"),
        ("unknown_parentage_self_employed_borderline", generate_profile_3_soft_decline, "soft_decline"),
    ]

    all_profiles = []

    for profile_name, profile_fn, expected in profiles:
        output_dir = OUTPUT_DIR / profile_name
        print(f"\n{'-' * 60}")
        print(f"Generating: {profile_name}")
        print(f"Output: {output_dir}")
        print(f"{'-' * 60}")

        profile = profile_fn()

        # Generate documents
        documents = _generate_profile_documents(profile, hash(profile_name) & 0xFFFF, output_dir)

        # Build profile record
        profile_record = {
            "profile_name": profile_name,
            "expected_decision": expected,
            "applicant": profile.model_dump(mode="json"),
            "documents": {
                doc_type: {
                    "data": doc_info["data"],
                    "files": [Path(f).name for f in doc_info["files"]],
                }
                for doc_type, doc_info in documents.items()
            },
        }
        all_profiles.append(profile_record)

        # Save individual profile.json
        profile_json_path = output_dir / "profile.json"
        with open(profile_json_path, "w", encoding="utf-8") as f:
            json.dump(profile_record, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {profile_json_path}")

    # Save combined profiles.json
    combined_path = OUTPUT_DIR / "profiles.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump({"profiles": all_profiles}, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved combined: {combined_path}")

    # Summary
    print("\n" + "=" * 60)
    print("Generation Complete!")
    print("=" * 60)
    for profile in all_profiles:
        name = profile["profile_name"]
        decision = profile["expected_decision"]
        doc_count = len(profile["documents"])
        print(f"  {name}: {decision} ({doc_count} document types)")

    print(f"\nAll files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
