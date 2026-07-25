"""Emirates ID Luhn checksum and format validation."""

import re


UAE_ID_PATTERN = re.compile(r"^(784|866|978)-\d{4}-\d{6,7}-\d$")


def _strip_and_normalize(emirates_id: str) -> str:
    return emirates_id.replace("-", "").replace(" ", "").strip()


def validate_format(emirates_id: str) -> bool:
    return bool(UAE_ID_PATTERN.match(emirates_id.strip()))


def luhn_check_digit(digits: str) -> int:
    """Compute Luhn check digit for a numeric string (excluding check digit)."""
    total = 0
    reverse_digits = digits[::-1]
    for i, ch in enumerate(reverse_digits):
        n = int(ch)
        if i % 2 == 0:  # Double every second digit from the right (even indices in reversed body)
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - (total % 10)) % 10


def validate_luhn(emirates_id: str) -> bool:
    digits = _strip_and_normalize(emirates_id)
    if not digits.isdigit():
        return False
    if len(digits) not in (14, 15):
        return False
    body = digits[:-1]
    check = int(digits[-1])
    return luhn_check_digit(body) == check


def validate(emirates_id: str) -> bool:
    return validate_format(emirates_id) and validate_luhn(emirates_id)
