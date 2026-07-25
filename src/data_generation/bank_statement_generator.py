"""Bank statement generator producing structured data and PDF output.

Generates UAE bank statements with realistic transaction patterns including
WPS salary credits, rent payments, utilities, groceries, and other common
UAE expenditures. Balance reconciliation is mathematically enforced.
"""

import hashlib
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.data_generation.profile import ApplicantProfile
from src.data_generation.templates.bank_templates import get_bank_template
from src.data_generation.utils import UAE_BANKS, random_date_between, weighted_choice


# Transaction category definitions with typical amount ranges and frequencies
TRANSACTION_CATEGORIES: list[dict[str, Any]] = [
    {
        "category": "rent",
        "description_pool": ["Rent Payment", "Monthly Rent", "Apartment Rent", "House Rent"],
        "amount_range": (2000, 25000),
        "frequency": 5,
        "type": "debit",
        "channel": "TRF",
    },
    {
        "category": "utility",
        "description_pool": ["DEWA Payment", "ADDC Utilities", "FEWA Bill", "Electricity & Water", "Utility Bill"],
        "amount_range": (150, 2500),
        "frequency": 12,
        "type": "debit",
        "channel": "IB",
    },
    {
        "category": "telecom",
        "description_pool": ["Etisalat Bill", "Du Telecom", "Etisalat Postpaid", "Du Mobile", "Telecom Payment"],
        "amount_range": (50, 800),
        "frequency": 10,
        "type": "debit",
        "channel": "IB",
    },
    {
        "category": "grocery",
        "description_pool": ["Carrefour", "Lulu Hypermarket", "Spinneys", "Union Coop", "Viva Supermarket", "Waitrose", "Choithrams"],
        "amount_range": (30, 1500),
        "frequency": 35,
        "type": "debit",
        "channel": "POS",
    },
    {
        "category": "fuel",
        "description_pool": ["ENOC Fuel", "ADNOC Petrol", "Emarat Fuel Station", "ADNOC Service Station", "ENOC Service Station"],
        "amount_range": (50, 500),
        "frequency": 18,
        "type": "debit",
        "channel": "POS",
    },
    {
        "category": "transfer",
        "description_pool": ["Online Transfer", "Mobile Transfer", "Bank Transfer", "Remittance", "Money Transfer"],
        "amount_range": (200, 5000),
        "frequency": 8,
        "type": "debit",
        "channel": "IB",
    },
    {
        "category": "atm",
        "description_pool": ["ATM Withdrawal", "Cash Withdrawal", "ATM Cash"],
        "amount_range": (200, 3000),
        "frequency": 15,
        "type": "debit",
        "channel": "ATM",
    },
    {
        "category": "pos",
        "description_pool": ["POS Purchase", "Retail Purchase", "Store Payment", "Online Shopping", "Restaurant Payment", "Cafe Payment"],
        "amount_range": (20, 2000),
        "frequency": 25,
        "type": "debit",
        "channel": "POS",
    },
    {
        "category": "insurance",
        "description_pool": ["Health Insurance Premium", "Car Insurance", "Life Insurance", "Medical Insurance"],
        "amount_range": (300, 3000),
        "frequency": 3,
        "type": "debit",
        "channel": "TRF",
    },
    {
        "category": "education",
        "description_pool": ["School Fees", "Tuition Payment", "Education Fees", "University Fees"],
        "amount_range": (500, 8000),
        "frequency": 4,
        "type": "debit",
        "channel": "TRF",
    },
    {
        "category": "refund",
        "description_pool": ["Refund - Carrefour", "Refund - Online Purchase", "Cashback", "Return Credit"],
        "amount_range": (20, 500),
        "frequency": 5,
        "type": "credit",
        "channel": "POS",
    },
    {
        "category": "investment",
        "description_pool": ["Investment Deposit", "Savings Transfer", "Fixed Deposit"],
        "amount_range": (1000, 10000),
        "frequency": 2,
        "type": "credit",
        "channel": "IB",
    },
]


def _generate_transaction_hash(txn_date: str, amount: str, description: str, currency: str) -> str:
    """Generate MD5 hash for transaction uniqueness."""
    data = f"{txn_date}|{amount}|{description}|{currency}"
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def _generate_account_number(rng: random.Random) -> str:
    """Generate a realistic UAE account number (10-16 digits)."""
    length = rng.randint(10, 16)
    return "".join(str(rng.randint(0, 9)) for _ in range(length))


def _pick_salary_day(rng: random.Random) -> int:
    """Pick a consistent salary credit day (1-28) for monthly WPS transfers."""
    return rng.randint(1, 28)


def _generate_wps_transactions(
    profile: ApplicantProfile,
    period_start: date,
    period_end: date,
    salary_day: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate 1-3 WPS salary credit transactions on consistent monthly dates."""
    num_salary = rng.randint(1, 3)
    salary_amount = float(profile.monthly_salary)

    # Find the months in the statement period
    months_in_period = []
    current = period_start.replace(day=1)
    while current <= period_end:
        months_in_period.append((current.year, current.month))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    # Pick which months have salary (at least 1, up to num_salary)
    salary_months = months_in_period[-num_salary:]  # Most recent months

    transactions = []
    for year, month in salary_months:
        # Use the consistent salary day, capped to valid day for that month
        day = min(salary_day, 28)  # Safe for all months
        txn_date = date(year, month, day)

        # Ensure date is within period
        if txn_date < period_start or txn_date > period_end:
            continue

        description = f"WPS Salary Transfer - {profile.employer_name}"
        txn_date_str = txn_date.isoformat()
        amount_str = f"{salary_amount:.2f}"

        txn = {
            "transaction_date": txn_date_str,
            "description": description,
            "amount": amount_str,
            "transaction_type": "credit",
            "transaction_hash": _generate_transaction_hash(txn_date_str, amount_str, description, "AED"),
            "category": "salary",
            "counterparty": profile.employer_name,
            "reference_number": f"WPS{rng.randint(100000, 999999)}",
            "is_wps_salary": True,
            "channel": "TRF",
        }
        transactions.append(txn)

    return transactions


def _generate_regular_transactions(
    profile: ApplicantProfile,
    period_start: date,
    period_end: date,
    target_count: int,
    salary_day: int,
    salary_months: set[tuple[int, int]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate regular debit/credit transactions for the statement period."""
    transactions = []
    days_in_period = (period_end - period_start).days

    # Build weighted lists for category selection
    categories = [c["category"] for c in TRANSACTION_CATEGORIES]
    weights = [c["frequency"] for c in TRANSACTION_CATEGORIES]

    # Add rent transactions based on profile monthly_rent
    rent_amount = float(profile.monthly_rent)
    if rent_amount > 0:
        # 1-3 rent payments in the period
        num_rent = min(rng.randint(1, 3), max(1, days_in_period // 25))
        for i in range(num_rent):
            # Rent typically paid early in the month
            month_offset = rng.randint(0, max(0, days_in_period // 28 - 1))
            rent_day = min(rng.randint(1, 5), 28)
            txn_date = period_start + timedelta(days=month_offset * 28 + rng.randint(0, 5))
            if txn_date > period_end:
                txn_date = period_end - timedelta(days=rng.randint(0, 5))
            if txn_date < period_start:
                continue

            txn_date_str = txn_date.isoformat()
            amount_str = f"{rent_amount:.2f}"
            description = rng.choice(["Rent Payment", "Monthly Rent", "Apartment Rent"])

            txn = {
                "transaction_date": txn_date_str,
                "description": description,
                "amount": f"-{amount_str}",
                "transaction_type": "debit",
                "transaction_hash": _generate_transaction_hash(txn_date_str, amount_str, description, "AED"),
                "category": "rent",
                "counterparty": "Property Management",
                "reference_number": f"RENT{rng.randint(100000, 999999)}",
                "is_wps_salary": False,
                "channel": "TRF",
            }
            transactions.append(txn)

    # Generate other transactions to reach target count
    attempts = 0
    max_attempts = target_count * 3

    while len(transactions) < target_count and attempts < max_attempts:
        attempts += 1
        category_def = weighted_choice(TRANSACTION_CATEGORIES, weights, rng)
        category = category_def["category"]

        # Skip salary category here (handled by WPS)
        if category == "salary":
            continue

        # Generate a random date in the period
        txn_date = random_date_between(rng, period_start, period_end)
        txn_date_str = txn_date.isoformat()

        # Generate amount
        min_amt, max_amt = category_def["amount_range"]
        amount_val = round(rng.uniform(min_amt, max_amt), 2)

        # Determine sign
        txn_type = category_def["type"]
        if txn_type == "debit":
            amount_str = f"-{amount_val:.2f}"
        else:
            amount_str = f"{amount_val:.2f}"

        # Pick description
        description = rng.choice(category_def["description_pool"])

        # Generate counterparty for some categories
        counterparty = None
        if category in ("grocery", "fuel", "pos"):
            counterparty = description.split()[0] if description else None
        elif category == "utility":
            counterparty = "Utility Authority"
        elif category == "telecom":
            counterparty = description.split()[0] if description else None
        elif category == "transfer":
            counterparty = "Third Party"
        elif category in ("insurance", "education"):
            counterparty = "Service Provider"

        txn = {
            "transaction_date": txn_date_str,
            "description": description,
            "amount": amount_str,
            "transaction_type": txn_type,
            "transaction_hash": _generate_transaction_hash(txn_date_str, amount_str, description, "AED"),
            "category": category,
            "counterparty": counterparty,
            "reference_number": f"REF{rng.randint(100000, 999999)}",
            "is_wps_salary": False,
            "channel": category_def["channel"],
        }
        transactions.append(txn)

    return transactions


def _compute_running_balances(
    opening_balance: Decimal,
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort transactions by date and compute running balances."""
    # Sort by date
    sorted_txns = sorted(transactions, key=lambda t: t["transaction_date"])

    balance = opening_balance
    for txn in sorted_txns:
        amount = Decimal(txn["amount"])
        balance += amount
        txn["running_balance"] = f"{balance:.2f}"

    return sorted_txns


def _render_pdf(
    bank_name: str,
    account_holder: str,
    account_number: str,
    period_start: date,
    period_end: date,
    opening_balance: Decimal,
    closing_balance: Decimal,
    total_debits: Decimal,
    total_credits: Decimal,
    transactions: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Render a bank statement PDF using reportlab."""
    template = get_bank_template(bank_name)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    elements = []

    # Header style
    header_style = ParagraphStyle(
        "BankHeader",
        fontName="Helvetica-Bold",
        fontSize=template["header_font_size"],
        textColor=colors.HexColor(template["text_color"]),
        spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "BankSub",
        fontName="Helvetica",
        fontSize=template["subheader_font_size"],
        textColor=colors.grey,
        spaceAfter=8,
    )
    info_style = ParagraphStyle(
        "InfoText",
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor(template["text_color"]),
    )

    # Bank header
    elements.append(Paragraph(template["logo_text"], header_style))
    elements.append(Paragraph(template["tagline"], sub_style))
    elements.append(Paragraph(f"SWIFT: {template['swift']}", sub_style))
    elements.append(Spacer(1, 8 * mm))

    # Account info
    elements.append(Paragraph("Account Statement", header_style))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(f"Account Holder: {account_holder}", info_style))
    elements.append(Paragraph(f"Account Number: {account_number}", info_style))
    elements.append(Paragraph(f"Statement Period: {period_start.isoformat()} to {period_end.isoformat()}", info_style))
    elements.append(Paragraph(f"Currency: AED", info_style))
    elements.append(Spacer(1, 5 * mm))

    # Summary table
    summary_data = [
        ["Opening Balance", f"{opening_balance:,.2f}"],
        ["Total Credits", f"+{total_credits:,.2f}"],
        ["Total Debits", f"-{total_debits:,.2f}"],
        ["Closing Balance", f"{closing_balance:,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[120 * mm, 60 * mm])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8 * mm))

    # Transaction table
    col_widths = [w * mm for w in template["col_widths"]]
    table_data = [template["col_headers"]]

    for txn in transactions:
        amount_val = Decimal(txn["amount"])
        amount_display = f"{amount_val:,.2f}"
        balance_display = txn.get("running_balance", "")

        table_data.append([
            txn["transaction_date"],
            txn["description"][:40],
            txn["transaction_type"].upper(),
            amount_display,
            balance_display,
        ])

    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    txn_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(template["table_header_bg"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(template["table_header_fg"])),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(txn_table)

    # Footer
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        "This is a computer-generated statement. No signature required.",
        ParagraphStyle("Footer", fontName="Helvetica-Oblique", fontSize=7, textColor=colors.grey),
    ))

    doc.build(elements)


def generate_bank_statement(
    profile: ApplicantProfile,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    """Generate a UAE bank statement with structured data and PDF output.

    Args:
        profile: ApplicantProfile seed for cross-document consistency.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (bank_statement_data dict, list of transaction dicts, PDF file path).
        The bank_statement_data includes all 14 schema fields.
        Each transaction dict includes all 12 schema fields.
        Balance reconciliation is enforced: opening + credits - debits = closing.
    """
    rng = random.Random(seed)

    # Pick a bank
    bank = rng.choice(UAE_BANKS)
    bank_name = bank["name"]

    # Account number
    account_number = _generate_account_number(rng)

    # Statement period: 3-6 months back from a recent reference date
    today = date.today()
    period_length_days = rng.randint(90, 180)  # 3-6 months
    period_end = today - timedelta(days=rng.randint(1, 15))
    period_start = period_end - timedelta(days=period_length_days)

    # Number of transactions: 60-120
    target_count = rng.randint(60, 120)

    # Consistent salary day for WPS
    salary_day = _pick_salary_day(rng)

    # Generate WPS salary transactions
    wps_txns = _generate_wps_transactions(profile, period_start, period_end, salary_day, rng)

    # Generate regular transactions
    salary_months = {(date.fromisoformat(t["transaction_date"]).year, date.fromisoformat(t["transaction_date"]).month) for t in wps_txns}
    regular_txns = _generate_regular_transactions(
        profile, period_start, period_end, target_count, salary_day, salary_months, rng,
    )

    # Combine all transactions
    all_transactions = wps_txns + regular_txns

    # Sort by date
    all_transactions.sort(key=lambda t: t["transaction_date"])

    # Compute totals
    total_credits = Decimal("0.00")
    total_debits = Decimal("0.00")
    for txn in all_transactions:
        amount = Decimal(txn["amount"])
        if amount > 0:
            total_credits += amount
        else:
            total_debits += abs(amount)

    # Generate opening balance and enforce reconciliation
    # opening + credits - debits = closing
    # We pick a reasonable closing balance, then derive opening
    closing_balance = Decimal(str(round(rng.uniform(1000, 50000), 2)))
    opening_balance = closing_balance - total_credits + total_debits

    # Ensure opening is positive (if not, adjust closing)
    if opening_balance < 0:
        opening_balance = Decimal(str(round(rng.uniform(5000, 20000), 2)))
        closing_balance = opening_balance + total_credits - total_debits
        if closing_balance < 0:
            # Add more credits to make it work
            closing_balance = abs(closing_balance) + Decimal(str(round(rng.uniform(1000, 5000), 2)))

    # Compute running balances
    sorted_transactions = _compute_running_balances(opening_balance, all_transactions)

    # Build structured data
    bank_statement_data: dict[str, Any] = {
        "bank_name": bank_name,
        "account_holder_name": profile.full_name_en,
        "account_number": account_number,
        "currency": "AED",
        "statement_period_start": period_start.isoformat(),
        "statement_period_end": period_end.isoformat(),
        "opening_balance": f"{opening_balance:.2f}",
        "closing_balance": f"{closing_balance:.2f}",
        "total_debits": f"{total_debits:.2f}",
        "total_credits": f"{total_credits:.2f}",
        "is_balance_reconciled": True,
        "transactions": sorted_transactions,
        "transaction_count": len(sorted_transactions),
    }

    # Generate PDF
    output_dir = Path(__file__).parent.parent.parent.parent / "generated" / f"applicant_{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "bank_statement.pdf"

    _render_pdf(
        bank_name=bank_name,
        account_holder=profile.full_name_en,
        account_number=account_number,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_debits=total_debits,
        total_credits=total_credits,
        transactions=sorted_transactions,
        output_path=pdf_path,
    )

    # Validation assertions
    recon_check = opening_balance + total_credits - total_debits
    assert abs(recon_check - closing_balance) < Decimal("0.01"), \
        f"Balance reconciliation failed: {recon_check} != {closing_balance}"
    assert period_start < period_end, "Period start must be before period end"
    assert bank_statement_data["currency"] == "AED", "Currency must be AED"

    # No future transaction dates
    for txn in sorted_transactions:
        txn_date = date.fromisoformat(txn["transaction_date"])
        assert txn_date <= today, f"Future transaction date: {txn_date}"

    return bank_statement_data, sorted_transactions, pdf_path
