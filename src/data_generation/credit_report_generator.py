"""Credit report PDF generator using faker-credit-score + reportlab."""

import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.data_generation.profile import ApplicantProfile
from src.data_generation.utils import random_date_between


# AECB / UAE lender names for realistic facility generation
UAE_LENDERS: list[str] = [
    "Emirates NBD",
    "First Abu Dhabi Bank",
    "Abu Dhabi Commercial Bank",
    "Mashreq Bank",
    "Dubai Islamic Bank",
    "Emirates Islamic Bank",
    "ADIB (Abu Dhabi Islamic Bank)",
    "Sharjah Islamic Bank",
    "Commercial Bank of Dubai",
    "Emirates Development Bank",
    "Abu Dhabi Finance",
    "Shurooq Finance",
]

FACILITY_TYPES: list[str] = ["credit_card", "personal_loan", "mortgage", "auto_loan", "overdraft"]

# Risk-band-dependent late payment probability
RISK_LATE_PROB: dict[str, float] = {
    "Excellent": 0.02,
    "Very Good": 0.05,
    "Good": 0.12,
    "Fair": 0.25,
    "Poor": 0.45,
}

# Risk-band-dependent facility status weights
RISK_STATUS_WEIGHTS: dict[str, dict[str, list[float]]] = {
    "Excellent": {
        "active": [60, 20, 10, 8, 2],
        "closed": [70, 15, 5, 8, 2],
    },
    "Very Good": {
        "active": [55, 22, 12, 9, 2],
        "closed": [65, 18, 7, 8, 2],
    },
    "Good": {
        "active": [45, 25, 15, 12, 3],
        "closed": [55, 20, 10, 12, 3],
    },
    "Fair": {
        "active": [35, 25, 18, 15, 7],
        "closed": [40, 22, 15, 15, 8],
    },
    "Poor": {
        "active": [25, 20, 20, 20, 15],
        "closed": [25, 18, 20, 20, 17],
    },
}


def _score_to_risk_band(score: int) -> str:
    """Map a credit score to its risk band."""
    if score >= 750:
        return "Excellent"
    if score >= 650:
        return "Very Good"
    if score >= 550:
        return "Good"
    if score >= 450:
        return "Fair"
    return "Poor"


def _generate_credit_score(rng: random.Random) -> tuple[int, str]:
    """Generate a credit score (300-900) and its risk band.

    Tries faker-credit-score first; falls back to seeded random.
    """
    try:
        from faker_credit_score import CreditScoreProvider

        fake = CreditScoreProvider()
        fake.seed_instance(rng.randint(0, 2**32 - 1))
        score = int(fake.credit_score())
        score = max(300, min(900, score))
    except Exception:
        score = rng.randint(300, 900)
    return score, _score_to_risk_band(score)


def _generate_facilities(
    rng: random.Random, risk_band: str, monthly_salary: Decimal
) -> list[dict[str, Any]]:
    """Generate credit facility records correlated with risk band."""
    facilities: list[dict[str, Any]] = []
    num_active = rng.randint(1, 8)
    num_closed = rng.randint(0, 5)

    status_weights_active = RISK_STATUS_WEIGHTS[risk_band]["active"]
    status_weights_closed = RISK_STATUS_WEIGHTS[risk_band]["closed"]

    for i in range(num_active):
        fac_type = rng.choice(FACILITY_TYPES)
        lender = rng.choice(UAE_LENDERS)
        acct = f"ACC{rng.randint(100000, 999999)}"
        opened = random_date_between(rng, date.today() - timedelta(days=1825), date.today() - timedelta(days=30))

        if fac_type == "mortgage":
            limit = Decimal(str(rng.uniform(500_000, 3_000_000)))
            balance = Decimal(str(rng.uniform(200_000, float(limit))))
            monthly = Decimal(str(rng.uniform(3_000, 15_000)))
        elif fac_type == "auto_loan":
            limit = Decimal(str(rng.uniform(40_000, 200_000)))
            balance = Decimal(str(rng.uniform(10_000, float(limit))))
            monthly = Decimal(str(rng.uniform(800, 4_000)))
        elif fac_type == "personal_loan":
            limit = Decimal(str(rng.uniform(10_000, 150_000)))
            balance = Decimal(str(rng.uniform(2_000, float(limit))))
            monthly = Decimal(str(rng.uniform(300, 3_000)))
        elif fac_type == "overdraft":
            limit = Decimal(str(rng.uniform(5_000, 50_000)))
            balance = Decimal(str(rng.uniform(0, float(limit) * 0.6)))
            monthly = Decimal(str(rng.uniform(100, 500)))
        else:  # credit_card
            limit = Decimal(str(rng.uniform(5_000, 80_000)))
            balance = Decimal(str(rng.uniform(0, float(limit) * 0.85)))
            monthly = Decimal(str(rng.uniform(200, 2_000)))

        # Payment status correlated with risk band
        late_prob = RISK_LATE_PROB[risk_band]
        r = rng.random()
        if r < late_prob * 0.3:
            pay_status = "90_days_late"
        elif r < late_prob * 0.6:
            pay_status = "60_days_late"
        elif r < late_prob * 0.85:
            pay_status = "30_days_late"
        elif r < late_prob:
            pay_status = "defaulted"
        else:
            pay_status = "current"

        facilities.append(
            {
                "facility_type": fac_type,
                "lender_name": lender,
                "account_number": acct,
                "status": "active",
                "opened_date": opened.isoformat(),
                "closed_date": None,
                "credit_limit": float(limit),
                "current_balance": float(balance),
                "monthly_payment": float(monthly),
                "payment_status": pay_status,
            }
        )

    for i in range(num_closed):
        fac_type = rng.choice(FACILITY_TYPES)
        lender = rng.choice(UAE_LENDERS)
        acct = f"ACC{rng.randint(100000, 999999)}"
        opened = random_date_between(rng, date.today() - timedelta(days=2555), date.today() - timedelta(days=365))
        closed = random_date_between(rng, opened + timedelta(days=180), date.today() - timedelta(days=30))

        if fac_type == "mortgage":
            limit = Decimal(str(rng.uniform(300_000, 2_500_000)))
            balance = Decimal("0.00") if rng.random() > 0.1 else Decimal(str(rng.uniform(1, 50_000)))
            monthly = Decimal(str(rng.uniform(2_000, 12_000)))
        elif fac_type == "auto_loan":
            limit = Decimal(str(rng.uniform(30_000, 180_000)))
            balance = Decimal("0.00") if rng.random() > 0.15 else Decimal(str(rng.uniform(1, 20_000)))
            monthly = Decimal(str(rng.uniform(600, 3_500)))
        elif fac_type == "personal_loan":
            limit = Decimal(str(rng.uniform(5_000, 120_000)))
            balance = Decimal("0.00") if rng.random() > 0.2 else Decimal(str(rng.uniform(1, 15_000)))
            monthly = Decimal(str(rng.uniform(200, 2_500)))
        elif fac_type == "overdraft":
            limit = Decimal(str(rng.uniform(3_000, 40_000)))
            balance = Decimal("0.00")
            monthly = Decimal("0.00")
        else:
            limit = Decimal(str(rng.uniform(3_000, 60_000)))
            balance = Decimal("0.00") if rng.random() > 0.25 else Decimal(str(rng.uniform(1, 10_000)))
            monthly = Decimal("0.00")

        # Closed facilities are more likely to have had late payments
        late_prob = min(0.6, RISK_LATE_PROB[risk_band] * 2)
        r = rng.random()
        if r < late_prob * 0.2:
            pay_status = "90_days_late"
        elif r < late_prob * 0.4:
            pay_status = "60_days_late"
        elif r < late_prob * 0.6:
            pay_status = "30_days_late"
        elif r < late_prob:
            pay_status = "defaulted"
        else:
            pay_status = "current"

        facilities.append(
            {
                "facility_type": fac_type,
                "lender_name": lender,
                "account_number": acct,
                "status": "closed",
                "opened_date": opened.isoformat(),
                "closed_date": closed.isoformat(),
                "credit_limit": float(limit),
                "current_balance": float(balance),
                "monthly_payment": float(monthly),
                "payment_status": pay_status,
            }
        )

    return facilities


def _generate_payment_history(
    rng: random.Random, risk_band: str, num_months: int
) -> list[dict[str, str]]:
    """Generate 24-36 months of payment status history correlated with risk band."""
    late_prob = RISK_LATE_PROB[risk_band]
    history: list[dict[str, str]] = []
    today = date.today()

    statuses = ["current", "late_30", "late_60", "late_90", "default"]

    for i in range(num_months):
        month_date = today - timedelta(days=(num_months - i) * 30)
        r = rng.random()
        if r < late_prob * 0.5:
            status = rng.choice(["late_30", "late_60", "late_90", "default"])
        else:
            status = "current"
        history.append(
            {
                "month": month_date.strftime("%Y-%m"),
                "status": status,
            }
        )

    return history


def _generate_inquiries(rng: random.Random, risk_band: str) -> list[dict[str, Any]]:
    """Generate credit inquiry records. Poor scores tend to have more inquiries."""
    if risk_band == "Poor":
        count = rng.randint(5, 15)
    elif risk_band == "Fair":
        count = rng.randint(3, 10)
    elif risk_band == "Good":
        count = rng.randint(2, 6)
    else:
        count = rng.randint(1, 4)

    inquiries = []
    for _ in range(count):
        inq_date = random_date_between(rng, date.today() - timedelta(days=730), date.today())
        inquirer = rng.choice(UAE_LENDERS)
        purpose = rng.choice(["credit_card", "personal_loan", "auto_loan", "mortgage", "overdraft"])
        inquiries.append(
            {
                "inquiry_date": inq_date.isoformat(),
                "inquirer": inquirer,
                "purpose": purpose,
            }
        )

    return inquiries


def generate_credit_report(
    profile: ApplicantProfile, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    """Generate a synthetic AECB-style credit report.

    Returns:
        credit_report_data: dict mapping to credit_report_data schema (20 fields)
        credit_facilities: list of dicts mapping to credit_facilities schema (11 fields each)
        pdf_path: Path to the generated PDF file
    """
    rng = random.Random(seed)

    # Generate credit score and risk band
    credit_score, risk_band = _generate_credit_score(rng)

    # Generate facilities
    facilities = _generate_facilities(rng, risk_band, profile.monthly_salary)

    # Compute derived values
    active_facilities = [f for f in facilities if f["status"] == "active"]
    closed_facilities = [f for f in facilities if f["status"] != "active"]
    total_outstanding = sum(Decimal(str(f["current_balance"])) for f in facilities)
    total_credit_limit = sum(Decimal(str(f["credit_limit"])) for f in facilities if f.get("credit_limit"))
    utilization = (
        float((total_outstanding / total_credit_limit * 100).quantize(Decimal("0.01")))
        if total_credit_limit > 0
        else 0.0
    )

    # Payment history
    num_months = rng.randint(24, 36)
    payment_history = _generate_payment_history(rng, risk_band, num_months)

    # Late payment counts from history
    late_count = sum(1 for h in payment_history if h["status"] != "current")
    defaulted = sum(1 for f in facilities if f["payment_status"] == "defaulted")
    bounced = rng.randint(0, 3) if risk_band in ("Fair", "Poor") else rng.randint(0, 1)
    court_judgments = rng.randint(0, 2) if risk_band == "Poor" else 0
    has_bankruptcy = risk_band == "Poor" and rng.random() < 0.15

    # Inquiries
    inquiries = _generate_inquiries(rng, risk_band)

    # Score calculation date
    score_date = random_date_between(rng, date.today() - timedelta(days=30), date.today())

    # Build credit_report_data (20 fields)
    credit_data: dict[str, Any] = {
        "cb_subject_id": f"AECB{rng.randint(10000000, 99999999)}",
        "identity_number": profile.identity_number,
        "full_name": profile.full_name_en,
        "credit_score": credit_score,
        "risk_band": risk_band,
        "total_active_accounts": len(active_facilities),
        "total_closed_accounts": len(closed_facilities),
        "total_outstanding_balance": float(total_outstanding),
        "contact_details": {
            "phone": profile.contact_phone,
            "email": profile.contact_email,
            "address": profile.address,
        },
        "employment_info": {
            "employer": profile.employer_name,
            "occupation": profile.occupation,
            "salary": float(profile.monthly_salary),
        },
        "score_calculation_date": score_date.isoformat(),
        "total_credit_limit": float(total_credit_limit),
        "credit_utilization_ratio": utilization,
        "active_facilities": [
            {k: v for k, v in f.items() if k != "status"} for f in active_facilities
        ],
        "closed_facilities": [
            {k: v for k, v in f.items() if k != "status"} for f in closed_facilities
        ],
        "payment_history": payment_history,
        "late_payment_count": late_count,
        "defaulted_accounts": defaulted,
        "bounced_cheques": bounced,
        "court_judgments": court_judgments,
        "has_bankruptcy_records": has_bankruptcy,
        "inquiry_count": len(inquiries),
        "inquiries": inquiries,
    }

    # Build credit_facilities list (11 fields each)
    facility_records: list[dict[str, Any]] = []
    for f in facilities:
        facility_records.append(
            {
                "facility_type": f["facility_type"],
                "lender_name": f["lender_name"],
                "account_number": f["account_number"],
                "status": f["status"],
                "opened_date": f["opened_date"],
                "closed_date": f["closed_date"],
                "credit_limit": f["credit_limit"],
                "current_balance": f["current_balance"],
                "monthly_payment": f["monthly_payment"],
                "payment_status": f["payment_status"],
            }
        )

    # Generate PDF
    pdf_path = _render_credit_report_pdf(credit_data, facility_records, seed)

    return credit_data, facility_records, pdf_path


def _render_credit_report_pdf(
    credit_data: dict[str, Any],
    facilities: list[dict[str, Any]],
    seed: int,
) -> Path:
    """Render an AECB-style credit report PDF using reportlab."""
    output_dir = Path(__file__).parent.parent.parent / "output" / f"applicant_{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "credit_report.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AECBTitle",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#1a3c6e"),
        spaceAfter=6,
    )
    header_style = ParagraphStyle(
        "AECBHeader",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#1a3c6e"),
        spaceBefore=12,
        spaceAfter=6,
    )
    normal_style = styles["Normal"]

    story = []

    # Header
    story.append(Paragraph("AL ETIHAD CREDIT BUREAU", title_style))
    story.append(Paragraph("Credit Report - UAE", styles["Heading3"]))
    story.append(Spacer(1, 0.3 * cm))

    # Subject info
    subject_data = [
        ["Subject Name:", credit_data["full_name"]],
        ["Identity Number:", credit_data["identity_number"]],
        ["AECB Subject ID:", credit_data["cb_subject_id"]],
        ["Report Date:", credit_data["score_calculation_date"]],
    ]
    subject_table = Table(subject_data, colWidths=[4 * cm, 10 * cm])
    subject_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(subject_table)
    story.append(Spacer(1, 0.5 * cm))

    # Credit Score Section
    story.append(Paragraph("Credit Score Summary", header_style))

    risk_colors = {
        "Excellent": colors.HexColor("#27ae60"),
        "Very Good": colors.HexColor("#2ecc71"),
        "Good": colors.HexColor("#f39c12"),
        "Fair": colors.HexColor("#e67e22"),
        "Poor": colors.HexColor("#e74c3c"),
    }
    score_color = risk_colors.get(credit_data["risk_band"], colors.black)

    score_data = [
        ["Credit Score", str(credit_data["credit_score"])],
        ["Risk Band", credit_data["risk_band"]],
        ["Total Active Accounts", str(credit_data["total_active_accounts"])],
        ["Total Closed Accounts", str(credit_data["total_closed_accounts"])],
        ["Total Outstanding Balance", f"AED {credit_data['total_outstanding_balance']:,.2f}"],
        ["Total Credit Limit", f"AED {credit_data['total_credit_limit']:,.2f}"],
        ["Credit Utilization Ratio", f"{credit_data['credit_utilization_ratio']:.1f}%"],
    ]
    score_table = Table(score_data, colWidths=[5 * cm, 7 * cm])
    score_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, 1), (1, 1), score_color),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(score_table)
    story.append(Spacer(1, 0.5 * cm))

    # Adverse remarks
    story.append(Paragraph("Adverse Remarks", header_style))
    adverse_data = [
        ["Late Payment Count", str(credit_data["late_payment_count"])],
        ["Defaulted Accounts", str(credit_data["defaulted_accounts"])],
        ["Bounced Cheques", str(credit_data["bounced_cheques"])],
        ["Court Judgments", str(credit_data["court_judgments"])],
        ["Bankruptcy Records", "Yes" if credit_data["has_bankruptcy_records"] else "No"],
    ]
    adverse_table = Table(adverse_data, colWidths=[5 * cm, 7 * cm])
    adverse_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(adverse_table)
    story.append(Spacer(1, 0.5 * cm))

    # Facilities table
    story.append(Paragraph("Credit Facilities", header_style))
    fac_header = ["Type", "Lender", "Status", "Balance (AED)", "Payment Status"]
    fac_rows = [fac_header]
    for f in facilities:
        fac_rows.append(
            [
                f["facility_type"].replace("_", " ").title(),
                f["lender_name"],
                f["status"].title(),
                f"{f['current_balance']:,.2f}",
                f["payment_status"].replace("_", " ").title(),
            ]
        )
    fac_table = Table(fac_rows, colWidths=[3 * cm, 4.5 * cm, 2 * cm, 3 * cm, 3 * cm])
    fac_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]
        )
    )
    story.append(fac_table)
    story.append(Spacer(1, 0.5 * cm))

    # Payment history summary
    story.append(Paragraph("Payment History Summary", header_style))
    payment_history = credit_data.get("payment_history", [])
    if payment_history:
        # Group by year
        history_by_year: dict[str, dict[str, int]] = {}
        for entry in payment_history:
            year = entry["month"][:4]
            if year not in history_by_year:
                history_by_year[year] = {"current": 0, "late": 0}
            if entry["status"] == "current":
                history_by_year[year]["current"] += 1
            else:
                history_by_year[year]["late"] += 1

        ph_header = ["Year", "On-Time Payments", "Late Payments", "Total"]
        ph_rows = [ph_header]
        for year in sorted(history_by_year.keys(), reverse=True):
            counts = history_by_year[year]
            total = counts["current"] + counts["late"]
            ph_rows.append([year, str(counts["current"]), str(counts["late"]), str(total)])

        ph_table = Table(ph_rows, colWidths=[3 * cm, 4 * cm, 3 * cm, 2 * cm])
        ph_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(ph_table)
    story.append(Spacer(1, 0.5 * cm))

    # Inquiries
    story.append(Paragraph("Credit Inquiries", header_style))
    inquiries = credit_data.get("inquiries", [])
    if inquiries:
        inq_header = ["Date", "Inquirer", "Purpose"]
        inq_rows = [inq_header]
        for inq in inquiries[:15]:  # Limit to 15 for readability
            inq_rows.append([inq["inquiry_date"], inq["inquirer"], inq["purpose"].replace("_", " ").title()])
        inq_table = Table(inq_rows, colWidths=[3 * cm, 5 * cm, 4 * cm])
        inq_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(inq_table)

    # Footer
    story.append(Spacer(1, 0.5 * cm))
    disclaimer = Paragraph(
        "This is a synthetic credit report generated for testing purposes. "
        "It does not represent actual credit data from the Al Etihad Credit Bureau.",
        ParagraphStyle("Disclaimer", parent=normal_style, fontSize=7, textColor=colors.grey),
    )
    story.append(disclaimer)

    doc.build(story)
    return pdf_path
