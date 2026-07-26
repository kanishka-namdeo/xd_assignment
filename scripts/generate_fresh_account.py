"""Generate a single fresh applicant account with full document set.

Usage:
    python scripts/generate_fresh_account.py
    python scripts/generate_fresh_account.py --seed 42
    python scripts/generate_fresh_account.py --seed 42 --output-dir ./my_accounts
"""

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

import structlog

# Ensure stdout uses UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_generation.applicant_generator import generate_applicant
from src.data_generation.assets_liabilities_generator import generate_assets_liabilities
from src.data_generation.application_form_generator import generate_application_form
from src.data_generation.bank_statement_generator import generate_bank_statement
from src.data_generation.credit_report_generator import generate_credit_report
from src.data_generation.emirates_id_generator import generate_emirates_id
from src.data_generation.consistency import validate_consistency
from src.data_generation.resume_generator import generate_resume

logger = structlog.get_logger(__name__)


def _write_json(path: Path, data: object) -> None:
    """Write data to a JSON file with utf-8 encoding and str default serialization."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def generate_fresh_account(seed: int, output_dir: Path) -> tuple[Path, bool, object]:
    """Generate all documents for one applicant and validate consistency.

    Args:
        seed: Random seed for reproducibility.
        output_dir: Base output directory. Applicant files go to output_dir/applicant_{seed}/.

    Returns:
        Tuple of (applicant_dir, consistency_passed, profile).
    """
    applicant_dir = output_dir / f"applicant_{seed}"
    applicant_dir.mkdir(parents=True, exist_ok=True)

    logger.info("fresh_account_start", seed=seed, output_dir=str(output_dir))

    # Phase 0: Generate profile
    profile = generate_applicant(seed)

    # Phase 1: Emirates ID (returns PIL Images, not files)
    eid_data, front_img, back_img = generate_emirates_id(profile, seed)
    front_img.save(applicant_dir / "emirates_id_front.png")
    back_img.save(applicant_dir / "emirates_id_back.png")

    # Phase 2: Bank statement
    bank_data, bank_transactions, bank_pdf_path = generate_bank_statement(profile, seed)
    if bank_pdf_path.exists():
        shutil.copy2(bank_pdf_path, applicant_dir / "bank_statement.pdf")

    # Phase 3: Credit report
    credit_data, credit_facilities, credit_pdf_path = generate_credit_report(profile, seed)
    if credit_pdf_path.exists():
        shutil.copy2(credit_pdf_path, applicant_dir / "credit_report.pdf")

    # Phase 4: Resume
    resume_data, work_experiences, resume_docx_path = generate_resume(profile, seed)
    if resume_docx_path.exists():
        shutil.copy2(resume_docx_path, applicant_dir / "resume.docx")

    # Phase 5: Assets & liabilities (requires credit_data for cross-document consistency)
    assets_data, assets_xlsx_path = generate_assets_liabilities(profile, credit_data, seed, credit_facilities)
    if assets_xlsx_path.exists():
        shutil.copy2(assets_xlsx_path, applicant_dir / "assets_liabilities.xlsx")

    # Phase 6: Application form
    form_data, form_png_path = generate_application_form(profile, seed)
    if form_png_path.exists():
        shutil.copy2(form_png_path, applicant_dir / "application_form.png")

    # Phase 7: Cross-document consistency validation
    consistency_report = validate_consistency(
        profile=profile,
        eid_data=eid_data,
        bank_data=bank_data,
        bank_transactions=bank_transactions,
        credit_data=credit_data,
        credit_facilities=credit_facilities,
        resume_data=resume_data,
        resume_work_experiences=work_experiences,
        assets_data=assets_data,
        form_data=form_data,
    )

    passed = consistency_report.get("passed", False)

    # Write structured JSON metadata alongside document files
    _write_json(applicant_dir / "profile.json", profile.model_dump(mode="json"))
    _write_json(applicant_dir / "emirates_id_data.json", eid_data)
    _write_json(applicant_dir / "bank_statement_data.json", bank_data)
    _write_json(applicant_dir / "credit_report_data.json", credit_data)
    _write_json(applicant_dir / "resume_data.json", resume_data)
    _write_json(applicant_dir / "assets_liabilities_data.json", assets_data)
    _write_json(applicant_dir / "application_form_data.json", form_data)

    if passed:
        _write_json(applicant_dir / "consistency_report.json", consistency_report)
        logger.info("fresh_account_complete", seed=seed, passed=True)
    else:
        logger.warning("fresh_account_consistency_failed", seed=seed, rules=consistency_report.get("rules"))

    return applicant_dir, passed, profile


def _print_summary(applicant_dir: Path, profile, seed: int, output_dir: Path) -> None:
    """Print a copy-paste-friendly summary block."""
    summary = (
        "\n"
        "============================================================\n"
        "  FRESH ACCOUNT READY\n"
        "============================================================\n"
        f"  Emirates ID: {profile.identity_number}\n"
        f"  Name:        {profile.full_name_en}\n"
        f"  DOB:         {profile.date_of_birth}\n"
        f"  Salary:      AED {profile.monthly_salary}\n"
        f"  Category:    {profile.support_category}\n"
        f"  Status:      {profile.employment_status}\n"
        f"  Output:      {output_dir.resolve()}/applicant_{seed}/\n"
        "  Documents:   emirates_id_front.png, emirates_id_back.png,\n"
        "               bank_statement.pdf, credit_report.pdf,\n"
        "               resume.docx, assets_liabilities.xlsx,\n"
        "               application_form.png\n"
        "============================================================\n"
    )
    print(summary)


def main() -> None:
    """CLI entrypoint for generating a single fresh applicant account."""
    parser = argparse.ArgumentParser(
        description="Generate a single fresh applicant account with full document set and consistency validation.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility. If not provided, a random seed is chosen.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/fresh_accounts"),
        help="Base output directory (default: data/fresh_accounts/).",
    )

    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randint(1, 999_999)
    output_dir = args.output_dir

    print(f"Generating fresh account with seed={seed} -> {output_dir.resolve()}/applicant_{seed}/")

    applicant_dir, passed, profile = generate_fresh_account(seed, output_dir)

    if not passed:
        print(f"ERROR: Consistency validation failed for seed={seed}. No consistency_report.json written.")
        sys.exit(1)

    _print_summary(applicant_dir, profile, seed, output_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
