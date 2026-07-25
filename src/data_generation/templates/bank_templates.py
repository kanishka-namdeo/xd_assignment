"""UAE bank layout templates for PDF rendering.

Each template defines the visual configuration for generating a realistic
bank statement PDF: colors, fonts, header layout, and column widths.
"""

from typing import Any


def get_bank_template(bank_name: str) -> dict[str, Any]:
    """Return the layout template for a given UAE bank name.

    Falls back to Emirates NBD template if bank_name is not recognized.
    """
    templates: dict[str, dict[str, Any]] = {
        "Emirates NBD": {
            "bank_name": "Emirates NBD",
            "swift": "EBILAEAD",
            "header_color": "#003DA5",
            "text_color": "#1A1A2E",
            "accent_color": "#003DA5",
            "logo_text": "EmiratesNBD",
            "tagline": "A world of finance",
            "header_font_size": 16,
            "subheader_font_size": 9,
            "table_header_bg": "#003DA5",
            "table_header_fg": "#FFFFFF",
            "col_widths": [28, 130, 60, 60, 52],
            "col_headers": ["Date", "Description", "Type", "Amount (AED)", "Balance (AED)"],
        },
        "First Abu Dhabi Bank": {
            "bank_name": "First Abu Dhabi Bank",
            "swift": "ABORAEAD",
            "header_color": "#6C1D5F",
            "text_color": "#1A1A2E",
            "accent_color": "#6C1D5F",
            "logo_text": "FAB",
            "tagline": "Forward. For you.",
            "header_font_size": 16,
            "subheader_font_size": 9,
            "table_header_bg": "#6C1D5F",
            "table_header_fg": "#FFFFFF",
            "col_widths": [28, 130, 60, 60, 52],
            "col_headers": ["Date", "Description", "Type", "Amount (AED)", "Balance (AED)"],
        },
        "Abu Dhabi Commercial Bank": {
            "bank_name": "Abu Dhabi Commercial Bank",
            "swift": "ADCBAEAD",
            "header_color": "#E30613",
            "text_color": "#1A1A2E",
            "accent_color": "#E30613",
            "logo_text": "ADCB",
            "tagline": "Your bank for life",
            "header_font_size": 16,
            "subheader_font_size": 9,
            "table_header_bg": "#E30613",
            "table_header_fg": "#FFFFFF",
            "col_widths": [28, 130, 60, 60, 52],
            "col_headers": ["Date", "Description", "Type", "Amount (AED)", "Balance (AED)"],
        },
        "Mashreq Bank": {
            "bank_name": "Mashreq Bank",
            "swift": "MSRCAEAD",
            "header_color": "#D71920",
            "text_color": "#1A1A2E",
            "accent_color": "#D71920",
            "logo_text": "Mashreq",
            "tagline": "Always with you",
            "header_font_size": 16,
            "subheader_font_size": 9,
            "table_header_bg": "#D71920",
            "table_header_fg": "#FFFFFF",
            "col_widths": [28, 130, 60, 60, 52],
            "col_headers": ["Date", "Description", "Type", "Amount (AED)", "Balance (AED)"],
        },
        "Dubai Islamic Bank": {
            "bank_name": "Dubai Islamic Bank",
            "swift": "DUIBAEAD",
            "header_color": "#006747",
            "text_color": "#1A1A2E",
            "accent_color": "#006747",
            "logo_text": "DIB",
            "tagline": "Islamic banking, forward.",
            "header_font_size": 16,
            "subheader_font_size": 9,
            "table_header_bg": "#006747",
            "table_header_fg": "#FFFFFF",
            "col_widths": [28, 130, 60, 60, 52],
            "col_headers": ["Date", "Description", "Type", "Amount (AED)", "Balance (AED)"],
        },
    }
    return templates.get(bank_name, templates["Emirates NBD"])
