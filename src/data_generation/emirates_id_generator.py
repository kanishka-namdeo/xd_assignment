"""Emirates ID number and card image generator with Luhn checksum."""

import random
from datetime import date, timedelta
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.data_generation.profile import ApplicantProfile
from src.data_generation.utils import generate_luhn_id, random_date_between
from src.utils.emirates_id import validate


# Card dimensions: 85.60mm x 53.98mm at 300 DPI
CARD_WIDTH_PX = 1009
CARD_HEIGHT_PX = 638

# MRZ zone dimensions (bottom ~1/3 of back card)
MRZ_LINE_HEIGHT = 42
MRZ_TOP_Y = CARD_HEIGHT_PX - (MRZ_LINE_HEIGHT * 3 + 30)


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font if available, fall back to default."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: str | None = None,
    outline: str | None = None,
    width: int = 1,
) -> None:
    """Draw a rounded rectangle using PIL primitives."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_header_band(draw: ImageDraw.ImageDraw, width: int, height: int, text_en: str, text_ar: str) -> None:
    """Draw the UAE header band at the top of the card."""
    # Dark green header band
    draw.rectangle([0, 0, width, height], fill="#006B3F")
    # Falcon emblem placeholder - gold circle
    center_x = width // 2
    draw.ellipse([center_x - 25, 10, center_x + 25, 60], fill="#C8A951")
    # UAE text
    font = _get_font(24)
    draw.text((20, 20), text_en, fill="white", font=font)
    draw.text((width - 200, 20), text_ar, fill="white", font=font)


def _draw_photo_placeholder(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    """Draw a photo placeholder area."""
    _draw_rounded_rect(draw, [x, y, x + w, y + h], radius=8, fill="#D3D3D3", outline="#808080", width=2)
    font = _get_font(14)
    draw.text((x + w // 2 - 30, y + h // 2 - 8), "[ PHOTO ]", fill="#606060", font=font)


def _draw_field_label_value(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    value: str,
    label_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    value_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    label_color: str = "#555555",
    value_color: str = "#111111",
) -> int:
    """Draw a field label and value, return next y position."""
    draw.text((x, y), label, fill=label_color, font=label_font)
    draw.text((x, y + 20), value, fill=value_color, font=value_font)
    return y + 50


def _compute_mrz_check_digit(data: str) -> str:
    """Compute ICAO 9303 check digit for an MRZ field."""
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(data):
        if ch == "<":
            val = 0
        elif ch.isdigit():
            val = int(ch)
        elif ch.isalpha():
            val = ord(ch.upper()) - ord("A") + 10
        else:
            val = 0
        total += val * weights[i % 3]
    return str(total % 10)


def _generate_mrz_lines(
    identity_number: str,
    full_name_en: str,
    nationality: str,
    date_of_birth: date,
    gender: str,
    expiry_date: date,
) -> tuple[str, str, str]:
    """Generate 3-line ICAO 9303 MRZ for UAE Emirates ID.

    UAE uses country code ARE and ID type I (identity card).
    The identity_number is in format 784-YYYY-NNNNNNN-C (15 chars with dashes).
    For MRZ, we strip dashes to get 14 digits.
    """
    # Line 1: ID type (I) + issuing state (ARE) + name
    # Names are formatted as SURNAME<<GIVEN<NAME> padded with <
    name_parts = full_name_en.upper().split()
    if len(name_parts) >= 2:
        surname = name_parts[0]
        given = "<<".join(name_parts[1:])
    else:
        surname = full_name_en.upper()
        given = ""
    name_field = f"{surname}<<{given}"
    name_field = name_field.replace(" ", "<")[:30].ljust(30, "<")
    line1 = f"I<ARE{name_field}"

    # Line 2: ID number + check + nationality + DOB + sex + expiry + optional
    # Strip dashes from identity number: 784-YYYY-NNNNNNN-C -> 784YYYYNNNNNNNC (14 chars)
    id_digits = identity_number.replace("-", "")
    if len(id_digits) > 14:
        id_digits = id_digits[:14]
    id_digits = id_digits.ljust(14, "<")
    id_check = _compute_mrz_check_digit(id_digits)

    dob_str = date_of_birth.strftime("%y%m%d")
    dob_check = _compute_mrz_check_digit(dob_str)

    sex = "M" if gender == "Male" else "F"

    exp_str = expiry_date.strftime("%y%m%d")
    exp_check = _compute_mrz_check_digit(exp_str)

    # Nationality code (3 letters)
    nationality_code = nationality[:3].upper().ljust(3, "<")

    # Optional data (residency info) - 14 chars
    optional = "<<<<<<<<<<<<<<<<"

    line2 = f"{id_digits}{id_check}{nationality_code}{dob_str}{dob_check}{sex}{exp_str}{exp_check}{optional}"

    # Line 3: Additional data (for ID cards, often empty or has extra info)
    line3 = "<<" + "UAE" + identity_number.replace("-", "").ljust(27, "<")

    return line1, line2, line3


def _render_front_card(data: dict[str, Any]) -> Image.Image:
    """Render the front side of the Emirates ID card."""
    img = Image.new("RGB", (CARD_WIDTH_PX, CARD_HEIGHT_PX), "#F5F5F0")
    draw = ImageDraw.Draw(img)

    # Background pattern - subtle geometric design
    for i in range(0, CARD_WIDTH_PX, 40):
        draw.line([(i, 0), (i, CARD_HEIGHT_PX)], fill="#E8E8E0", width=1)

    # Header band
    _draw_header_band(draw, CARD_WIDTH_PX, 70, "UAE", "الإمارات")

    # Photo placeholder (left side)
    _draw_photo_placeholder(draw, 30, 90, 180, 230)

    # Fields (right side)
    label_font = _get_font(16)
    value_font = _get_font(20)
    bold_font = _get_font(22)

    y = 95
    y = _draw_field_label_value(draw, 230, y, "Full Name (EN)", data["full_name_en"], label_font, bold_font)
    y = _draw_field_label_value(draw, 230, y, "Full Name (AR)", data.get("full_name_ar", ""), label_font, value_font)
    y = _draw_field_label_value(draw, 230, y, "Emirates ID No.", data["identity_number"], label_font, bold_font)
    y = _draw_field_label_value(draw, 230, y, "Nationality", data["nationality"], label_font, value_font)
    y = _draw_field_label_value(draw, 230, y, "Date of Birth", data["date_of_birth"], label_font, value_font)
    y = _draw_field_label_value(draw, 230, y, "Gender", data["gender"], label_font, value_font)
    y = _draw_field_label_value(draw, 230, y, "Expiry Date", data["expiry_date"], label_font, value_font)

    # Footer with card type
    draw.rectangle([0, CARD_HEIGHT_PX - 30, CARD_WIDTH_PX, CARD_HEIGHT_PX], fill="#006B3F")
    font_footer = _get_font(14)
    draw.text((20, CARD_HEIGHT_PX - 25), "EMIRATES IDENTITY CARD", fill="white", font=font_footer)
    draw.text((CARD_WIDTH_PX - 250, CARD_HEIGHT_PX - 25), "بطاقة هوية", fill="white", font=font_footer)

    return img


def _render_back_card(data: dict[str, Any]) -> Image.Image:
    """Render the back side of the Emirates ID card with MRZ zone."""
    img = Image.new("RGB", (CARD_WIDTH_PX, CARD_HEIGHT_PX), "#F5F5F0")
    draw = ImageDraw.Draw(img)

    # Background pattern
    for i in range(0, CARD_WIDTH_PX, 40):
        draw.line([(i, 0), (i, CARD_HEIGHT_PX)], fill="#E8E8E0", width=1)

    # Header band
    _draw_header_band(draw, CARD_WIDTH_PX, 70, "UAE", "الإمارات")

    # Card number
    label_font = _get_font(16)
    value_font = _get_font(18)
    draw.text((30, 90), "Card Number", fill="#555555", font=label_font)
    draw.text((30, 112), data.get("card_number", data["identity_number"]), fill="#111111", font=value_font)

    # Issue date
    draw.text((30, 150), "Issue Date", fill="#555555", font=label_font)
    draw.text((30, 172), data.get("issue_date", ""), fill="#111111", font=value_font)

    # Barcode placeholder
    barcode_x = 30
    barcode_y = 220
    barcode_w = CARD_WIDTH_PX - 60
    barcode_h = 80
    _draw_rounded_rect(draw, [barcode_x, barcode_y, barcode_x + barcode_w, barcode_y + barcode_h],
                       radius=4, fill="white", outline="#CCCCCC", width=1)
    # Draw barcode lines
    bar_rng = random.Random(42)
    for i in range(barcode_x + 10, barcode_x + barcode_w - 10, 4):
        bar_height = bar_rng.randint(30, barcode_h - 10)
        bar_top = barcode_y + (barcode_h - bar_height) // 2
        draw.rectangle([i, bar_top, i + 2, bar_top + bar_height], fill="#111111")

    # MRZ zone - 3 lines of ICAO 9303 format
    mrz_y = MRZ_TOP_Y
    mrz_font = _get_font(MRZ_LINE_HEIGHT)

    # MRZ background
    draw.rectangle([0, mrz_y - 10, CARD_WIDTH_PX, CARD_HEIGHT_PX], fill="#E0E0D8")
    draw.text((15, mrz_y + 5), "MRZ", fill="#888888", font=_get_font(12))

    identity_number = data["identity_number"]
    full_name_en = data["full_name_en"]
    nationality = data["nationality"]
    dob = date.fromisoformat(data["date_of_birth"]) if isinstance(data["date_of_birth"], str) else data["date_of_birth"]
    gender = data["gender"]
    expiry = date.fromisoformat(data["expiry_date"]) if isinstance(data["expiry_date"], str) else data["expiry_date"]

    line1, line2, line3 = _generate_mrz_lines(identity_number, full_name_en, nationality, dob, gender, expiry)

    # Draw MRZ lines in monospace-style font
    mrz_color = "#1A1A1A"
    draw.text((10, mrz_y + 35), line1, fill=mrz_color, font=mrz_font)
    draw.text((10, mrz_y + 35 + MRZ_LINE_HEIGHT), line2, fill=mrz_color, font=mrz_font)
    draw.text((10, mrz_y + 35 + MRZ_LINE_HEIGHT * 2), line3, fill=mrz_color, font=mrz_font)

    return img


def generate_emirates_id(profile: ApplicantProfile, seed: int) -> tuple[dict[str, Any], Image.Image, Image.Image]:
    """Generate Emirates ID data and card images.

    Args:
        profile: ApplicantProfile with identity information.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (emirates_id_data dict, front card Image, back card Image).
        The identity_number in the returned dict is generated using generate_luhn_id
        and may differ from profile.identity_number if the profile already has one.
    """
    rng = random.Random(seed)

    # Use the identity_number from the profile (already Luhn-valid)
    identity_number = profile.identity_number

    # Validate the ID
    if not validate(identity_number):
        raise ValueError(f"Profile Emirates ID failed validation: {identity_number}")

    # Generate dates
    today = date.today()
    # Issue date: 2-5 years ago
    years_ago = rng.randint(2, 5)
    issue_date = random_date_between(rng, today - timedelta(days=(years_ago + 1) * 365), today - timedelta(days=years_ago * 365))
    # Expiry: issue + 5 or 10 years (UAE citizens get 10, residents get 5 typically)
    validity_years = 10 if profile.nationality == "Emirati" else rng.choice([5, 10])
    expiry_date = issue_date.replace(year=issue_date.year + validity_years)

    # Card number (same as identity number, different formatting sometimes)
    card_number = identity_number

    # Build structured data dict (20 fields from emirates_id_data schema)
    data: dict[str, Any] = {
        # Required fields
        "identity_number": identity_number,
        "full_name_en": profile.full_name_en,
        "nationality": profile.nationality,
        "date_of_birth": profile.date_of_birth.isoformat(),
        "gender": profile.gender,
        "expiry_date": expiry_date.isoformat(),
        # Optional fields
        "full_name_ar": profile.full_name_ar,
        "card_number": card_number,
        "issue_date": issue_date.isoformat(),
        "is_mrz_verified": True,
        "address": profile.address,
        "occupation": profile.occupation,
        "employer_name": profile.employer_name,
        "marital_status": profile.marital_status,
        "mother_name": profile.mother_name,
        "sponsor_name": profile.sponsor_name,
        "sponsor_type": profile.sponsor_type,
        "residency_type": profile.residency_type,
        "residency_number": profile.residency_number,
        # Extraction confidence score (0.0-1.0)
        "extraction_confidence": round(rng.uniform(0.92, 0.99), 3),
    }

    # Render card images
    front_image = _render_front_card(data)
    back_image = _render_back_card(data)

    return data, front_image, back_image
