"""Application form layout templates for OCRSmith / Pillow rendering.

Defines the visual layout of the UAE Social Support Application form:
field positions, font sizes, bilingual labels (English/Arabic), and
section groupings used by the application_form_generator.
"""

from typing import Any

FORM_WIDTH: int = 595  # A4 width in points at 72 DPI
FORM_HEIGHT: int = 842  # A4 height in points
MARGIN: int = 40
LINE_HEIGHT: int = 22
SECTION_GAP: int = 12
FIELD_LABEL_WIDTH: int = 140
FIELD_INPUT_WIDTH: int = 180
TWO_COL_GAP: int = 20

FORM_SECTIONS: list[dict[str, Any]] = [
    {
        "key": "personal_info",
        "label_en": "Personal Information",
        "label_ar": "المعلومات الشخصية",
        "fields": [
            {
                "key": "applicant_name",
                "label_en": "Applicant Name",
                "label_ar": "اسم مقدم الطلب",
                "width": FIELD_INPUT_WIDTH * 2 + TWO_COL_GAP,
            },
            {
                "key": "identity_number",
                "label_en": "Emirates ID Number",
                "label_ar": "رقم الهوية",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "date_of_birth",
                "label_en": "Date of Birth",
                "label_ar": "تاريخ الميلاد",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "nationality",
                "label_en": "Nationality",
                "label_ar": "الجنسية",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "gender",
                "label_en": "Gender",
                "label_ar": "الجنس",
                "width": FIELD_INPUT_WIDTH,
            },
        ],
    },
    {
        "key": "address",
        "label_en": "Address",
        "label_ar": "العنوان",
        "fields": [
            {
                "key": "emirate",
                "label_en": "Emirate",
                "label_ar": "الإمارة",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "city",
                "label_en": "City",
                "label_ar": "المدينة",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "street",
                "label_en": "Street / Area",
                "label_ar": "الشارع / المنطقة",
                "width": FIELD_INPUT_WIDTH * 2 + TWO_COL_GAP,
            },
            {
                "key": "po_box",
                "label_en": "P.O. Box",
                "label_ar": "ص.ب",
                "width": FIELD_INPUT_WIDTH,
            },
        ],
    },
    {
        "key": "family",
        "label_en": "Family Information",
        "label_ar": "معلومات الأسرة",
        "fields": [
            {
                "key": "marital_status",
                "label_en": "Marital Status",
                "label_ar": "الحالة الاجتماعية",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "family_size",
                "label_en": "Family Size",
                "label_ar": "عدد أفراد الأسرة",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "dependents",
                "label_en": "Dependents",
                "label_ar": "المعالون",
                "width": FIELD_INPUT_WIDTH * 2 + TWO_COL_GAP,
            },
        ],
    },
    {
        "key": "employment",
        "label_en": "Employment Information",
        "label_ar": "معلومات التوظيف",
        "fields": [
            {
                "key": "employment_status",
                "label_en": "Employment Status",
                "label_ar": "حالة التوظيف",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "employer_name",
                "label_en": "Employer Name",
                "label_ar": "اسم صاحب العمل",
                "width": FIELD_INPUT_WIDTH * 2 + TWO_COL_GAP,
            },
            {
                "key": "occupation",
                "label_en": "Occupation",
                "label_ar": "المهنة",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "monthly_salary",
                "label_en": "Monthly Salary (AED)",
                "label_ar": "الراتب الشهري (درهم)",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "other_income",
                "label_en": "Other Income (AED)",
                "label_ar": "دخل آخر (درهم)",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "total_monthly_income",
                "label_en": "Total Monthly Income (AED)",
                "label_ar": "إجمالي الدخل الشهري (درهم)",
                "width": FIELD_INPUT_WIDTH,
            },
        ],
    },
    {
        "key": "housing",
        "label_en": "Housing Information",
        "label_ar": "معلومات السكن",
        "fields": [
            {
                "key": "housing_status",
                "label_en": "Housing Status",
                "label_ar": "حالة السكن",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "monthly_rent",
                "label_en": "Monthly Rent (AED)",
                "label_ar": "الإيجار الشهري (درهم)",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "monthly_mortgage",
                "label_en": "Monthly Mortgage (AED)",
                "label_ar": "القسط الشهري (درهم)",
                "width": FIELD_INPUT_WIDTH,
            },
        ],
    },
    {
        "key": "support",
        "label_en": "Support Request",
        "label_ar": "طلب الدعم",
        "fields": [
            {
                "key": "support_category",
                "label_en": "Support Category",
                "label_ar": "فئة الدعم",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "supporting_documents",
                "label_en": "Supporting Documents",
                "label_ar": "المستندات المؤيدة",
                "width": FIELD_INPUT_WIDTH * 2 + TWO_COL_GAP,
            },
        ],
    },
    {
        "key": "declaration",
        "label_en": "Declaration",
        "label_ar": "الإقرار",
        "fields": [
            {
                "key": "is_declaration_signed",
                "label_en": "Declaration Signed",
                "label_ar": "توقيع الإقرار",
                "width": FIELD_INPUT_WIDTH,
            },
            {
                "key": "declaration_date",
                "label_en": "Declaration Date",
                "label_ar": "تاريخ الإقرار",
                "width": FIELD_INPUT_WIDTH,
            },
        ],
    },
]

# Font configuration for form rendering
FONT_CONFIG: dict[str, Any] = {
    "section_font": "Helvetica-Bold",
    "section_font_size": 12,
    "label_font": "Helvetica",
    "label_font_size": 9,
    "value_font": "Helvetica",
    "value_font_size": 10,
    "arabic_font": "Helvetica",  # Use a font with Arabic glyph support in production
    "arabic_font_size": 9,
    "title_font": "Helvetica-Bold",
    "title_font_size": 16,
}

# Form header
FORM_HEADER: dict[str, str] = {
    "title_en": "Social Support Application Form",
    "title_ar": "نموذج طلب الدعم الاجتماعي",
    "subtitle_en": "Ministry of Community Development",
    "subtitle_ar": "وزارة تنمية المجتمع",
}


def get_form_template() -> dict[str, Any]:
    """Return the complete form layout template."""
    return {
        "page_width": FORM_WIDTH,
        "page_height": FORM_HEIGHT,
        "margin": MARGIN,
        "line_height": LINE_HEIGHT,
        "section_gap": SECTION_GAP,
        "field_label_width": FIELD_LABEL_WIDTH,
        "field_input_width": FIELD_INPUT_WIDTH,
        "two_col_gap": TWO_COL_GAP,
        "sections": FORM_SECTIONS,
        "fonts": FONT_CONFIG,
        "header": FORM_HEADER,
    }
