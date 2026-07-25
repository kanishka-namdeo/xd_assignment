"""Shared utilities for data generation (Luhn algorithm, IBAN generation, etc.)."""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from src.utils.emirates_id import luhn_check_digit


def generate_luhn_id(birth_year: int, rng: random.Random) -> str:
    """Generate a Luhn-valid 15-digit Emirates ID.

    Format: 784-YYYY-NNNNNNN-C
    - 784: ISO 3166-1 numeric code for UAE
    - YYYY: birth year
    - NNNNNNN: 7-digit random sequence
    - C: Luhn check digit
    """
    sequence = "".join(str(rng.randint(0, 9)) for _ in range(7))
    body = f"784{birth_year}{sequence}"
    check = luhn_check_digit(body)
    return f"784-{birth_year}-{sequence}-{check}"


def generate_iban(bank_code: str, account_number: str) -> str:
    """Generate a UAE IBAN with Mod-97 checksum.

    Format: AE + 2 check digits + 3-digit bank code + 16-digit account number.
    The account_number is left-padded with zeros to 16 digits.
    """
    account_padded = account_number.zfill(16)[:16]
    country_code = "AE"
    check_digits = "00"
    bban = f"{bank_code}{account_padded}"

    numeric_str = f"{country_code}{check_digits}{bban}"
    alpha_to_digit = ""
    for ch in numeric_str:
        if ch.isalpha():
            alpha_to_digit += str(ord(ch.upper()) - ord("A") + 10)
        else:
            alpha_to_digit += ch

    remainder = int(alpha_to_digit) % 97
    check = 98 - remainder
    check_str = f"{check:02d}"

    return f"{country_code}{check_str}{bank_code}{account_padded}"


def weighted_choice(choices: list[Any], weights: list[float], rng: random.Random) -> Any:
    """Seeded weighted random selection from a list of choices."""
    if len(choices) != len(weights):
        raise ValueError("choices and weights must have the same length")
    if not choices:
        raise ValueError("choices list cannot be empty")
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    r = rng.random() * total
    cumulative = 0.0
    for choice, weight in zip(choices, weights):
        cumulative += weight
        if r <= cumulative:
            return choice
    return choices[-1]


def random_decimal(rng: random.Random, min_val: float, max_val: float, places: int = 2) -> Decimal:
    """Generate a seeded Decimal value within [min_val, max_val]."""
    if min_val > max_val:
        min_val, max_val = max_val, min_val
    value = rng.uniform(min_val, max_val)
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str))


def random_date_between(rng: random.Random, start: date, end: date) -> date:
    """Generate a seeded random date between start and end (inclusive)."""
    if start > end:
        start, end = end, start
    days_between = (end - start).days
    random_days = rng.randint(0, days_between)
    return start + timedelta(days=random_days)


UAE_BANKS: list[dict[str, str]] = [
    {"name": "Emirates NBD", "code": "001", "swift": "EBILAEAD"},
    {"name": "First Abu Dhabi Bank", "code": "002", "swift": "ABORAEAD"},
    {"name": "Abu Dhabi Commercial Bank", "code": "003", "swift": "ADCBAEAD"},
    {"name": "Mashreq Bank", "code": "004", "swift": "MSRCAEAD"},
    {"name": "Dubai Islamic Bank", "code": "005", "swift": "DUIBAEAD"},
]

UAE_EMIRATES: list[str] = [
    "Abu Dhabi",
    "Dubai",
    "Sharjah",
    "Ajman",
    "Umm Al Quwain",
    "Ras Al Khaimah",
    "Fujairah",
]

SUPPORT_CATEGORIES: list[dict[str, Any]] = [
    {"name": "divorced", "weight": 30},
    {"name": "abandoned", "weight": 25},
    {"name": "unknown_parentage", "weight": 20},
    {"name": "health_disability", "weight": 25},
]

EMPLOYMENT_STATUSES: list[dict[str, Any]] = [
    {"status": "employed", "weight": 60},
    {"status": "self_employed", "weight": 15},
    {"status": "unemployed", "weight": 15},
    {"status": "retired", "weight": 10},
]

HOUSING_STATUSES: list[dict[str, Any]] = [
    {"status": "rented", "weight": 40},
    {"status": "owned", "weight": 35},
    {"status": "family_provided", "weight": 25},
]

MARITAL_STATUSES: list[dict[str, Any]] = [
    {"status": "married", "weight": 45},
    {"status": "single", "weight": 20},
    {"status": "divorced", "weight": 20},
    {"status": "widowed", "weight": 15},
]
