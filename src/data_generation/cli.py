"""CLI entrypoint for fake data generation.

Usage:
    python -m src.data_generation generate --count 3 --output-dir ./generated_data
    python -m src.data_generation generate --seeds 42 123 999 --output-dir ./output
"""

import json
import random
import shutil
from pathlib import Path

from src.data_generation.applicant_generator import generate_applicant
from src.data_generation.assets_liabilities_generator import generate_assets_liabilities
from src.data_generation.application_form_generator import generate_application_form
from src.data_generation.bank_statement_generator import generate_bank_statement
from src.data_generation.credit_report_generator import generate_credit_report
from src.data_generation.emirates_id_generator import generate_emirates_id
from src.data_generation.profile import ApplicantProfile
from src.data_generation.consistency import validate_consistency
from src.data_generation.resume_generator import generate_resume


def _write_json(path: Path, data: object) -> None:
    """Write data to a JSON file with utf-8 encoding and str default serialization."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def _serialize_profile(profile: ApplicantProfile) -> dict:
    """Serialize ApplicantProfile to a JSON-serializable dict."""
    return profile.model_dump(mode="json")


def generate_applicant_package(seed: int, output_dir: Path) -> Path:
    """Generate all documents for one applicant.

    Args:
        seed: Random seed for reproducibility.
        output_dir: Base output directory. Applicant files go to output_dir/applicant_{seed}/.

    Returns:
        Path to the applicant directory.
    """
    applicant_dir = output_dir / f"applicant_{seed}"
    applicant_dir.mkdir(parents=True, exist_ok=True)

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

    # Write structured JSON metadata alongside document files
    _write_json(applicant_dir / "profile.json", _serialize_profile(profile))
    _write_json(applicant_dir / "emirates_id_data.json", eid_data)
    _write_json(applicant_dir / "bank_statement_data.json", bank_data)
    _write_json(applicant_dir / "credit_report_data.json", credit_data)
    _write_json(applicant_dir / "resume_data.json", resume_data)
    _write_json(applicant_dir / "assets_liabilities_data.json", assets_data)
    _write_json(applicant_dir / "application_form_data.json", form_data)
    _write_json(applicant_dir / "consistency_report.json", consistency_report)

    return applicant_dir


def generate_batch(count: int, seeds: list[int] | None, output_dir: Path) -> Path:
    """Generate multiple applicants.

    Args:
        count: Number of applicants to generate (used if seeds is None).
        seeds: Explicit list of seeds. If provided, overrides count.
        output_dir: Base output directory.

    Returns:
        Path to the output directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if seeds is None:
        # Generate sequential seeds from a random starting point
        start = random.randint(1, 10000)
        seeds = list(range(start, start + count))

    for seed in seeds:
        applicant_dir = generate_applicant_package(seed, output_dir)
        status = "OK" if (applicant_dir / "consistency_report.json").exists() else "FAIL"
        print(f"  [{status}] applicant_{seed}")

    return output_dir


def _main() -> None:
    """CLI entrypoint using argparse."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate synthetic applicant data for UAE Social Support Application testing.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate applicant data packages.")
    gen_parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of applicants to generate (default: 1). Ignored if --seeds is provided.",
    )
    gen_parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="Explicit list of seeds (e.g. --seeds 42 123 999). Overrides --count.",
    )
    gen_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./generated_data"),
        help="Base output directory (default: ./generated_data).",
    )

    args = parser.parse_args()

    if args.command == "generate":
        print(f"Generating {args.seeds or f'{args.count} applicant(s)'} to {args.output_dir.resolve()}")
        generate_batch(count=args.count, seeds=args.seeds, output_dir=args.output_dir)
        print("Done.")


if __name__ == "__main__":
    _main()
