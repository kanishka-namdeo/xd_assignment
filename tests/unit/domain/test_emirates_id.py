"""Unit tests for Emirates ID generation and validation."""

import random
from datetime import date

import pytest

from src.data_generation.utils import generate_luhn_id
from src.utils.emirates_id import validate, validate_format, validate_luhn


class TestEmiratesIDGeneration:
    """Tests for Emirates ID number generation."""

    def test_generate_valid_id(self):
        """Generated ID passes Luhn validation."""
        rng = random.Random(42)
        id_number = generate_luhn_id(1990, rng)
        assert validate_luhn(id_number), f"Generated ID {id_number} failed Luhn check"

    def test_id_format(self):
        """Generated ID has correct format."""
        rng = random.Random(42)
        id_number = generate_luhn_id(1990, rng)
        parts = id_number.split("-")
        assert len(parts) == 4, f"Expected 4 parts, got {len(parts)}"
        assert parts[0] == "784", f"Expected country code 784, got {parts[0]}"
        assert len(parts[1]) == 4, f"Expected 4-digit year, got {len(parts[1])}"
        assert len(parts[2]) == 7, f"Expected 7-digit sequence, got {len(parts[2])}"
        assert len(parts[3]) == 1, f"Expected 1-digit checksum, got {len(parts[3])}"

    def test_id_year_matches(self):
        """Generated ID year matches input."""
        rng = random.Random(42)
        id_number = generate_luhn_id(1985, rng)
        year = int(id_number.split("-")[1])
        assert year == 1985

    def test_multiple_ids_unique(self):
        """Multiple generated IDs are unique."""
        rng = random.Random(42)
        ids = [generate_luhn_id(1990, rng) for _ in range(100)]
        assert len(set(ids)) == 100, "Generated duplicate IDs"

    def test_validate_format_valid(self):
        """validate_format accepts correct format."""
        rng = random.Random(42)
        id_number = generate_luhn_id(1990, rng)
        assert validate_format(id_number)

    def test_validate_format_invalid(self):
        """validate_format rejects wrong format."""
        assert not validate_format("123-456")
        assert not validate_format("not-an-id")

    def test_validate_full(self):
        """Full validate checks both format and Luhn."""
        rng = random.Random(42)
        id_number = generate_luhn_id(1990, rng)
        assert validate(id_number)

    def test_deterministic_with_seed(self):
        """Same seed produces same ID."""
        id1 = generate_luhn_id(1990, random.Random(42))
        id2 = generate_luhn_id(1990, random.Random(42))
        assert id1 == id2, "Same seed produced different IDs"

    def test_different_seeds_different_ids(self):
        """Different seeds produce different IDs."""
        id1 = generate_luhn_id(1990, random.Random(42))
        id2 = generate_luhn_id(1990, random.Random(43))
        assert id1 != id2, "Different seeds produced same ID"
