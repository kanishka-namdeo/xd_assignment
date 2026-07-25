"""Applicant profile generator using Mimesis + pandas."""

import random
from datetime import date, timedelta
from decimal import Decimal

from mimesis import Address, Datetime, Person
from mimesis.enums import Gender
from mimesis.locales import Locale

from src.data_generation.profile import ApplicantProfile
from src.data_generation.utils import (
    EMPLOYMENT_STATUSES,
    HOUSING_STATUSES,
    SUPPORT_CATEGORIES,
    UAE_EMIRATES,
    generate_luhn_id,
    random_date_between,
    random_decimal,
    weighted_choice,
)

NATIONALITY_WEIGHTS = [
    ("UAE", 60),
    ("GCC", 20),
    ("Other", 20),
]

OCCUPATIONS = [
    "Engineer",
    "Teacher",
    "Accountant",
    "Nurse",
    "Driver",
    "Sales Manager",
    "Administrative Assistant",
    "IT Specialist",
    "Doctor",
    "Shop Owner",
    "Consultant",
    "Mechanic",
    "Electrician",
    "Receptionist",
    "Security Guard",
]

UAE_CITIES = [
    "Abu Dhabi",
    "Dubai",
    "Sharjah",
    "Ajman",
    "Umm Al Quwain",
    "Ras Al Khaimah",
    "Fujairah",
    "Al Ain",
]

SUPPORT_DOCUMENT_MAP: dict[str, list[str]] = {
    "divorced": ["divorce_certificate", "emirates_id", "bank_statement", "credit_report"],
    "abandoned": ["emirates_id", "bank_statement", "credit_report", "assets_liabilities"],
    "unknown_parentage": ["emirates_id", "bank_statement", "application_form"],
    "health_disability": ["emirates_id", "bank_statement", "credit_report", "medical_report", "resume"],
}


def _generate_gcc_nationality(rng: random.Random) -> str:
    return rng.choice(["Saudi Arabia", "Kuwait", "Qatar", "Oman", "Bahrain"])


def _generate_other_nationality(rng: random.Random) -> str:
    return rng.choice([
        "Egypt", "India", "Pakistan", "Bangladesh", "Philippines",
        "Sri Lanka", "Nepal", "Jordan", "Lebanon", "Syria",
    ])


def _determine_family_size(marital_status: str, rng: random.Random) -> int:
    """Determine family_size based on marital_status with realistic distributions."""
    if marital_status == "married":
        return rng.choice([2, 3, 4, 5, 6, 7])
    elif marital_status == "divorced":
        return rng.choice([1, 2, 3, 4])
    elif marital_status == "widowed":
        return rng.choice([1, 2, 3, 4, 5])
    else:  # single
        return rng.choice([1, 2])


def _generate_dependents(family_size: int, rng: random.Random) -> list[dict]:
    """Generate dependents array correlated with family_size."""
    num_dependents = max(0, family_size - 1)
    dependents = []
    for i in range(num_dependents):
        dep_rng = random.Random(rng.randint(0, 2**32))
        age = dep_rng.choice([
            "0-5", "6-12", "13-18", "19-25", "26-35", "36-50", "51+"
        ])
        relation = dep_rng.choice(["child", "spouse", "parent", "sibling"])
        dependents.append({
            "name": f"Dependent {i + 1}",
            "age_group": age,
            "relation": relation,
        })
    return dependents


def _determine_salary(employment_status: str, rng: random.Random) -> Decimal:
    """Determine monthly salary based on employment status."""
    if employment_status == "employed":
        return random_decimal(rng, 3000, 45000, 2)
    elif employment_status == "self_employed":
        return random_decimal(rng, 5000, 60000, 2)
    elif employment_status == "retired":
        return random_decimal(rng, 2000, 15000, 2)
    else:  # unemployed
        return random_decimal(rng, 0, 1500, 2)


def _generate_other_income(employment_status: str, monthly_salary: Decimal, rng: random.Random) -> Decimal:
    """Generate other_income correlated with employment status and salary."""
    if employment_status == "unemployed":
        return random_decimal(rng, 0, 1000, 2)
    elif monthly_salary > 20000:
        return random_decimal(rng, 500, 8000, 2)
    elif monthly_salary > 10000:
        return random_decimal(rng, 0, 5000, 2)
    else:
        return random_decimal(rng, 0, 2000, 2)


def _generate_rent(housing_status: str, rng: random.Random) -> Decimal:
    """Generate monthly_rent based on housing_status."""
    if housing_status == "rented":
        return random_decimal(rng, 2000, 20000, 2)
    return Decimal("0.00")


def _generate_mortgage(housing_status: str, rng: random.Random) -> Decimal:
    """Generate monthly_mortgage based on housing_status."""
    if housing_status == "owned":
        return random_decimal(rng, 1000, 12000, 2)
    return Decimal("0.00")


def _generate_sponsor(profile: ApplicantProfile, employment_status: str, rng: random.Random) -> tuple[str, str]:
    """Generate sponsor_name and sponsor_type based on employment_status."""
    if employment_status == "employed":
        return profile.employer_name, "employer"
    elif employment_status in ("self_employed", "unemployed"):
        # Family sponsor
        sponsor_rng = random.Random(rng.randint(0, 2**32))
        person = Person(Locale.AR_SA, seed=sponsor_rng.randint(0, 2**32 - 1))
        return person.full_name(Gender.MALE), "family"
    else:  # retired
        return "Self", "self"


def generate_applicant(seed: int) -> ApplicantProfile:
    """Generate a complete ApplicantProfile for cross-document consistency.

    Args:
        seed: Random seed for reproducibility.

    Returns:
        ApplicantProfile with all 28 fields populated.
    """
    rng = random.Random(seed)

    # Generate base identity using Mimesis
    person = Person(Locale.AR_SA, seed=seed)
    address = Address(Locale.AR_SA, seed=seed)
    datetime_gen = Datetime(seed=seed)
    phone = Person(Locale.AR_AE, seed=seed)

    # Gender first (needed for name generation)
    gender_str = rng.choice(["Male", "Female"])
    gender_enum = Gender.MALE if gender_str == "Male" else Gender.FEMALE

    # Names
    full_name_en = person.full_name(gender_enum)
    full_name_ar = person.full_name(gender_enum)

    # Date of birth (18-70 years old)
    today = date.today()
    dob = random_date_between(rng, today - timedelta(days=70 * 365), today - timedelta(days=18 * 365))

    # Emirates ID with Luhn checksum
    identity_number = generate_luhn_id(dob.year, rng)

    # Nationality with weighted distribution
    nationality_choice = weighted_choice(
        [n[0] for n in NATIONALITY_WEIGHTS],
        [n[1] for n in NATIONALITY_WEIGHTS],
        rng,
    )
    if nationality_choice == "UAE":
        nationality = "Emirati"
    elif nationality_choice == "GCC":
        nationality = _generate_gcc_nationality(rng)
    else:
        nationality = _generate_other_nationality(rng)

    # Contact
    contact_phone = phone.telephone()
    contact_email = person.email()

    # Address
    emirate = rng.choice(UAE_EMIRATES)
    city = rng.choice(UAE_CITIES)
    address_dict = {
        "emirate": emirate,
        "city": city,
        "street": address.address(),
        "po_box": f"P.O. Box {rng.randint(1000, 99999)}",
    }

    # Marital status (weighted)
    marital_status = weighted_choice(
        [m["status"] for m in [{"status": "married", "weight": 45}, {"status": "single", "weight": 20},
                               {"status": "divorced", "weight": 20}, {"status": "widowed", "weight": 15}]],
        [45, 20, 20, 15],
        rng,
    )

    # Family size correlated with marital status
    family_size = _determine_family_size(marital_status, rng)

    # Dependents
    dependents = _generate_dependents(family_size, rng)

    # Employment status (weighted)
    employment_status = weighted_choice(
        [e["status"] for e in EMPLOYMENT_STATUSES],
        [e["weight"] for e in EMPLOYMENT_STATUSES],
        rng,
    )

    # Occupation and employer
    occupation = rng.choice(OCCUPATIONS)
    if employment_status == "self_employed":
        employer_name = "Self-Employed"
    elif employment_status == "unemployed":
        employer_name = "N/A"
    elif employment_status == "retired":
        employer_name = "Retired"
    else:
        employer_name = f"{rng.choice(['Al', 'Abu', 'Dubai', 'Emirates'])} {rng.choice(['Group', 'Company', 'Establishment', 'Trading', 'Industries'])}"

    # Salary correlated with employment
    monthly_salary = _determine_salary(employment_status, rng)
    other_income = _generate_other_income(employment_status, monthly_salary, rng)
    total_monthly_income = monthly_salary + other_income

    # Housing status (weighted)
    housing_status = weighted_choice(
        [h["status"] for h in HOUSING_STATUSES],
        [h["weight"] for h in HOUSING_STATUSES],
        rng,
    )

    monthly_rent = _generate_rent(housing_status, rng)
    monthly_mortgage = _generate_mortgage(housing_status, rng)

    # Support category (weighted)
    support_category = weighted_choice(
        [s["name"] for s in SUPPORT_CATEGORIES],
        [s["weight"] for s in SUPPORT_CATEGORIES],
        rng,
    )

    # Supporting documents based on support category
    supporting_documents = SUPPORT_DOCUMENT_MAP.get(support_category, ["emirates_id"])

    # Declaration
    is_declaration_signed = True
    declaration_date = random_date_between(rng, today - timedelta(days=30), today)

    # Mother's name
    mother_seed = rng.randint(0, 2**31 - 1)
    mother_person = Person(Locale.AR_SA, seed=mother_seed)
    mother_name = mother_person.full_name(Gender.FEMALE)

    # Sponsor
    sponsor_name, sponsor_type = _generate_sponsor(
        ApplicantProfile(
            full_name_en=full_name_en,
            full_name_ar=full_name_ar,
            identity_number=identity_number,
            date_of_birth=dob,
            nationality=nationality,
            gender=gender_str,
            contact_phone=contact_phone,
            contact_email=contact_email,
            address=address_dict,
            marital_status=marital_status,
            family_size=family_size,
            dependents=dependents,
            employment_status=employment_status,
            employer_name=employer_name,
            occupation=occupation,
            monthly_salary=monthly_salary,
            other_income=other_income,
            total_monthly_income=total_monthly_income,
            housing_status=housing_status,
            monthly_rent=monthly_rent,
            monthly_mortgage=monthly_mortgage,
            support_category=support_category,
            supporting_documents=supporting_documents,
            is_declaration_signed=is_declaration_signed,
            declaration_date=declaration_date,
            mother_name=mother_name,
            sponsor_name="",
            sponsor_type="",
            residency_type="",
            residency_number="",
        ),
        employment_status,
        rng,
    )

    # Residency
    if nationality == "Emirati":
        residency_type = "Citizen"
        residency_number = ""
    else:
        residency_type = rng.choice(["Employment", "Family", "Investor", "Freelance"])
        residency_number = f"{rng.randint(100000000, 999999999)}-{rng.randint(2024, 2026)}"

    return ApplicantProfile(
        full_name_en=full_name_en,
        full_name_ar=full_name_ar,
        identity_number=identity_number,
        date_of_birth=dob,
        nationality=nationality,
        gender=gender_str,
        contact_phone=contact_phone,
        contact_email=contact_email,
        address=address_dict,
        marital_status=marital_status,
        family_size=family_size,
        dependents=dependents,
        employment_status=employment_status,
        employer_name=employer_name,
        occupation=occupation,
        monthly_salary=monthly_salary,
        other_income=other_income,
        total_monthly_income=total_monthly_income,
        housing_status=housing_status,
        monthly_rent=monthly_rent,
        monthly_mortgage=monthly_mortgage,
        support_category=support_category,
        supporting_documents=supporting_documents,
        is_declaration_signed=is_declaration_signed,
        declaration_date=declaration_date,
        mother_name=mother_name,
        sponsor_name=sponsor_name,
        sponsor_type=sponsor_type,
        residency_type=residency_type,
        residency_number=residency_number,
    )
