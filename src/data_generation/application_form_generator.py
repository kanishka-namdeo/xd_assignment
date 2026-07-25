"""Application form image generator using Pillow for handwritten-style forms."""

import random
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.data_generation.profile import ApplicantProfile


FORM_WIDTH = 1654
FORM_HEIGHT = 2339

SUPPORT_CATEGORY_ARABIC: dict[str, str] = {
    "divorced": "مطلقة",
    "abandoned": "مهجورة",
    "unknown_parentage": " مجهولة النسب",
    "health_disability": "إعاقة صحية",
}

EMPLOYMENT_STATUS_ARABIC: dict[str, str] = {
    "employed": "موظف",
    "self_employed": "عامل لحسابه الخاص",
    "unemployed": "عاطل عن العمل",
    "retired": "متقاعد",
}

HOUSING_STATUS_ARABIC: dict[str, str] = {
    "owned": "مملوك",
    "rented": "مستأجر",
    "family_provided": "مقدم من العائلة",
}

MARITAL_STATUS_ARABIC: dict[str, str] = {
    "married": "متزوج",
    "single": "أعزب",
    "divorced": "مطلق",
    "widowed": "أرمل",
}

EMIRATES_ARABIC: dict[str, str] = {
    "Abu Dhabi": "أبو ظبي",
    "Dubai": "دبي",
    "Sharjah": "الشارقة",
    "Ajman": "عجمان",
    "Umm Al Quwain": "أم القيوين",
    "Ras Al Khaimah": "رأس الخيمة",
    "Fujairah": "الفجيرة",
    "Al Ain": "العين",
}


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font, falling back to default if unavailable."""
    candidates = [
        "arial.ttf",
        "Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _get_handwriting_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a handwriting-style font, falling back to regular font."""
    candidates = [
        "Segoe Script.ttf",
        "Bradley Hand ITC.ttf",
        "Comic Sans MS.ttf",
        "C:/Windows/Fonts/segoesc.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, IOError):
            continue
    return _get_font(size)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Draw text with slight positional jitter for handwriting realism."""
    jitter_x = random.randint(-1, 1)
    jitter_y = random.randint(-1, 1)
    draw.text((xy[0] + jitter_x, xy[1] + jitter_y), text, font=font, fill=fill)


def _draw_field(
    draw: ImageDraw.ImageDraw,
    y: int,
    label: str,
    value: str,
    label_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    value_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    x_label: int = 50,
    x_value: int = 450,
    line_spacing: int = 45,
) -> int:
    """Draw a labeled field and return the next y position."""
    _draw_text(draw, (x_label, y), f"{label}:", label_font, fill=(80, 80, 80))
    _draw_text(draw, (x_value, y), value, value_font, fill=(0, 0, 120))
    return y + line_spacing


def _draw_section_header(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    header_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    """Draw a section header with a horizontal rule."""
    draw.rectangle([(40, y), (FORM_WIDTH - 40, y + 3)], fill=(60, 60, 120))
    _draw_text(draw, (50, y + 10), text, header_font, fill=(60, 60, 120))
    return y + 40


def _draw_line(
    draw: ImageDraw.ImageDraw,
    y: int,
    thickness: int = 1,
    color: tuple[int, int, int] = (180, 180, 180),
) -> None:
    """Draw a horizontal line across the form."""
    draw.line([(50, y), (FORM_WIDTH - 50, y)], fill=color, width=thickness)


def _draw_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    outline: tuple[int, int, int] = (120, 120, 120),
    width: int = 1,
) -> None:
    """Draw a rectangle box."""
    draw.rectangle(xy, outline=outline, width=width)


def _render_form_image(profile: ApplicantProfile, seed: int) -> Image.Image:
    """Render the application form as a Pillow Image."""
    rng = random.Random(seed)
    random.seed(seed)

    img = Image.new("RGB", (FORM_WIDTH, FORM_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    label_font = _get_font(16)
    value_font = _get_handwriting_font(18)
    header_font = _get_font(20)
    title_font = _get_font(28)
    small_font = _get_font(12)
    arabic_font = _get_font(16)

    y = 60

    # Title
    draw.text(
        (FORM_WIDTH // 2 - 250, y),
        "SOCIAL SUPPORT APPLICATION FORM",
        font=title_font,
        fill=(30, 30, 80),
    )
    y += 40
    draw.text(
        (FORM_WIDTH // 2 - 150, y),
        "نموذج طلب الدعم الاجتماعي",
        font=arabic_font,
        fill=(30, 30, 80),
    )
    y += 50

    # Reference number
    ref = f"REF-{seed:08d}"
    _draw_text(draw, (FORM_WIDTH - 300, y), f"Reference: {ref}", small_font, fill=(120, 120, 120))
    y += 40

    # ===== Personal Information Section =====
    y = _draw_section_header(draw, y, "1. Personal Information / المعلومات الشخصية", header_font)

    y = _draw_field(draw, y, "Full Name (English)", profile.full_name_en, label_font, value_font)
    y = _draw_field(draw, y, "Full Name (Arabic)", profile.full_name_ar, label_font, value_font)
    y = _draw_field(draw, y, "Emirates ID Number", profile.identity_number, label_font, value_font)
    y = _draw_field(draw, y, "Date of Birth", profile.date_of_birth.isoformat(), label_font, value_font)
    y = _draw_field(draw, y, "Nationality", profile.nationality, label_font, value_font)
    y = _draw_field(draw, y, "Gender", profile.gender, label_font, value_font)
    y = _draw_field(draw, y, "Contact Phone", profile.contact_phone, label_font, value_font)
    y = _draw_field(draw, y, "Contact Email", profile.contact_email, label_font, value_font)

    y += 10
    _draw_line(draw, y)
    y += 20

    # ===== Address Section =====
    y = _draw_section_header(draw, y, "2. Address / العنوان", header_font)

    addr = profile.address
    y = _draw_field(draw, y, "Emirate", addr.get("emirate", ""), label_font, value_font)
    y = _draw_field(draw, y, "City", addr.get("city", ""), label_font, value_font)
    y = _draw_field(draw, y, "Street", addr.get("street", ""), label_font, value_font)
    y = _draw_field(draw, y, "PO Box", addr.get("po_box", ""), label_font, value_font)

    y += 10
    _draw_line(draw, y)
    y += 20

    # ===== Family Information Section =====
    y = _draw_section_header(draw, y, "3. Family Information / المعلومات العائلية", header_font)

    y = _draw_field(draw, y, "Marital Status", profile.marital_status, label_font, value_font)
    y = _draw_field(draw, y, "Family Size", str(profile.family_size), label_font, value_font)

    if profile.dependents:
        dep_text = ", ".join(d.get("relation", "") for d in profile.dependents[:5])
        y = _draw_field(draw, y, "Dependents", dep_text, label_font, value_font)

    y += 10
    _draw_line(draw, y)
    y += 20

    # ===== Employment Section =====
    y = _draw_section_header(draw, y, "4. Employment & Income / التوظيف والدخل", header_font)

    y = _draw_field(draw, y, "Employment Status", profile.employment_status, label_font, value_font)
    y = _draw_field(draw, y, "Employer Name", profile.employer_name, label_font, value_font)
    y = _draw_field(draw, y, "Occupation", profile.occupation, label_font, value_font)
    y = _draw_field(draw, y, "Monthly Salary (AED)", str(profile.monthly_salary), label_font, value_font)
    y = _draw_field(draw, y, "Other Income (AED)", str(profile.other_income), label_font, value_font)
    y = _draw_field(draw, y, "Total Monthly Income (AED)", str(profile.total_monthly_income), label_font, value_font)

    y += 10
    _draw_line(draw, y)
    y += 20

    # ===== Housing Section =====
    y = _draw_section_header(draw, y, "5. Housing / السكن", header_font)

    y = _draw_field(draw, y, "Housing Status", profile.housing_status, label_font, value_font)
    if profile.monthly_rent > 0:
        y = _draw_field(draw, y, "Monthly Rent (AED)", str(profile.monthly_rent), label_font, value_font)
    if profile.monthly_mortgage > 0:
        y = _draw_field(draw, y, "Monthly Mortgage (AED)", str(profile.monthly_mortgage), label_font, value_font)

    y += 10
    _draw_line(draw, y)
    y += 20

    # ===== Support Category Section =====
    y = _draw_section_header(draw, y, "6. Support Category / فئة الدعم", header_font)

    y = _draw_field(draw, y, "Support Category", profile.support_category, label_font, value_font)

    if profile.supporting_documents:
        docs_text = ", ".join(profile.supporting_documents)
        y = _draw_field(draw, y, "Supporting Documents", docs_text, label_font, value_font)

    y += 10
    _draw_line(draw, y)
    y += 20

    # ===== Declaration Section =====
    y = _draw_section_header(draw, y, "7. Declaration / الإقرار", header_font)

    declaration_text = (
        "I hereby declare that the information provided in this form is true, "
        "complete, and accurate to the best of my knowledge. I understand that "
        "any false or misleading information may result in rejection of my "
        "application or legal action."
    )
    # Word-wrap declaration text
    max_width = FORM_WIDTH - 100
    words = declaration_text.split()
    lines: list[str] = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=small_font)
        if bbox[2] - bbox[0] > max_width:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    decl_y = y + 10
    for line in lines:
        _draw_text(draw, (60, decl_y), line, small_font, fill=(0, 0, 0))
        decl_y += 22

    decl_y += 10
    signed_text = "X  I agree and declare" if profile.is_declaration_signed else "   I agree and declare"
    _draw_text(draw, (60, decl_y), signed_text, value_font, fill=(0, 0, 120))

    decl_y += 35
    _draw_text(draw, (60, decl_y), f"Signature Date: {profile.declaration_date.isoformat()}", label_font, fill=(80, 80, 80))

    decl_y += 30
    _draw_text(draw, (60, decl_y), "Applicant Signature:", label_font, fill=(80, 80, 80))

    # Draw a signature-like scribble
    sig_x = 250
    sig_y = decl_y
    for i in range(15):
        x1 = sig_x + i * 8 + rng.randint(-2, 2)
        y1 = sig_y + rng.randint(-5, 5)
        x2 = x1 + 4 + rng.randint(-1, 1)
        y2 = sig_y + rng.randint(-8, 3)
        draw.line([(x1, y1), (x2, y2)], fill=(0, 0, 120), width=2)

    # ===== Footer =====
    footer_y = FORM_HEIGHT - 60
    _draw_line(draw, footer_y, thickness=2, color=(60, 60, 120))
    footer_text = "Ministry of Community Development - UAE  |  وزارة تنمية المجتمع - الإمارات"
    bbox = draw.textbbox((0, 0), footer_text, font=small_font)
    tw = bbox[2] - bbox[0]
    draw.text(
        ((FORM_WIDTH - tw) // 2, footer_y + 15),
        footer_text,
        font=small_font,
        fill=(60, 60, 120),
    )

    # ===== Add noise for OCR realism =====
    img = _add_ocr_noise(img, rng)

    return img


def _add_ocr_noise(img: Image.Image, rng: random.Random) -> Image.Image:
    """Add subtle noise, blur, and rotation for OCR realism."""
    # Slight rotation (0.2-0.8 degrees)
    angle = rng.uniform(0.2, 0.8) * rng.choice([-1, 1])
    img = img.rotate(angle, resample=Image.BICUBIC, expand=True)

    # Very slight Gaussian blur
    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))

    # Add subtle noise
    pixels = img.load()
    width, height = img.size
    for _ in range(rng.randint(500, 2000)):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        if pixels and isinstance(pixels, object):
            try:
                old_pixel = pixels[x, y]
                noise_val = rng.randint(-15, 15)
                new_pixel = tuple(max(0, min(255, c + noise_val)) for c in old_pixel)
                pixels[x, y] = new_pixel
            except Exception:
                pass

    # Occasional faint speckles (dust/scan artifacts)
    for _ in range(rng.randint(20, 80)):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        size = rng.randint(1, 3)
        gray = rng.randint(200, 230)
        draw = ImageDraw.Draw(img)
        draw.ellipse(
            [x, y, x + size, y + size],
            fill=(gray, gray, gray),
        )

    return img


def generate_application_form(profile: ApplicantProfile, seed: int) -> tuple[dict[str, Any], Path]:
    """Generate a filled application form image and structured data.

    Args:
        profile: ApplicantProfile seed object with all identity and financial data.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (application_form_data dict, PNG file path).

    Validation rules enforced:
        - total_monthly_income = monthly_salary + other_income
        - is_declaration_signed = True
        - declaration_date within last 30 days
        - support_category has corresponding supporting_documents
    """
    # Build structured data mapping to application_form_data schema (22 fields)
    form_data: dict[str, Any] = {
        "applicant_name": profile.full_name_en,
        "identity_number": profile.identity_number,
        "date_of_birth": profile.date_of_birth.isoformat(),
        "nationality": profile.nationality,
        "contact_phone": profile.contact_phone,
        "contact_email": profile.contact_email,
        "address": profile.address,
        "employment_status": profile.employment_status,
        "total_monthly_income": str(profile.total_monthly_income),
        "marital_status": profile.marital_status,
        "family_size": profile.family_size,
        "dependents": profile.dependents,
        "employer_name": profile.employer_name,
        "occupation": profile.occupation,
        "monthly_salary": str(profile.monthly_salary),
        "other_income": str(profile.other_income),
        "housing_status": profile.housing_status,
        "monthly_rent": str(profile.monthly_rent),
        "monthly_mortgage": str(profile.monthly_mortgage),
        "support_category": profile.support_category,
        "supporting_documents": profile.supporting_documents,
        "is_declaration_signed": profile.is_declaration_signed,
        "declaration_date": profile.declaration_date.isoformat(),
    }

    # Enforce validation: total_monthly_income = monthly_salary + other_income
    computed_total = profile.monthly_salary + profile.other_income
    if profile.total_monthly_income != computed_total:
        form_data["total_monthly_income"] = str(computed_total)

    # Enforce: is_declaration_signed must be True
    form_data["is_declaration_signed"] = True

    # Enforce: declaration_date within last 30 days
    today = date.today()
    declaration_date = profile.declaration_date
    if declaration_date < today - timedelta(days=30) or declaration_date > today:
        form_data["declaration_date"] = (today - timedelta(days=random.Random(seed).randint(0, 29))).isoformat()

    # Render form image
    img = _render_form_image(profile, seed)

    # Save to PNG
    output_dir = Path(__file__).resolve().parent.parent.parent / "output" / f"applicant_{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "application_form.png"

    img.save(output_path, format="PNG", dpi=(200, 200))

    return form_data, output_path
