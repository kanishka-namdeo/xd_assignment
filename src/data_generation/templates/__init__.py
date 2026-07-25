"""UAE bank and application form templates for document rendering."""

from src.data_generation.templates.bank_templates import get_bank_template
from src.data_generation.templates.form_templates import FIELD_INPUT_WIDTH, FIELD_LABEL_WIDTH, get_form_template

__all__ = [
    "get_bank_template",
    "get_form_template",
    "FIELD_LABEL_WIDTH",
    "FIELD_INPUT_WIDTH",
]
