# Fake Data Generation Specification

**Date**: 2026-07-25
**Status**: Finalized
**Python Version**: 3.11.12 (venv at `.venv/`)
**Related**: `2026-07-25-document-processing-schema-design.md`

---

## Overview

This specification defines how synthetic test data is generated for the six document types in the UAE Social Support Application system. Each document type has a dedicated generator that produces output conforming to the PostgreSQL schemas defined in `2026-07-25-document-processing-schema-design.md`.

The generators ensure:
- **Schema compliance**: Generated data maps 1:1 to database table fields
- **Cross-document consistency**: Same applicant identity across all documents
- **Validation rule satisfaction**: Generated data passes all validation rules in the schema spec
- **Deterministic reproducibility**: Fixed seed produces identical output

---

## Library Decisions and Rationale

### 1. Mimesis 19.1.0 (replaces Faker)

**Decision**: Use Mimesis instead of Faker for tabular applicant data generation.

**Rationale**:
- **Performance**: 2-15x faster than Faker (0.137s vs 1.758s for 10K records)
- **Uniqueness**: 99.88% unique names vs 93.63% for Faker at 10K iterations
- **Schema-based generators**: Native support for structured data generation with relational references
- **Multilingual**: 46 locales including Arabic (`ar_SA`) for UAE-specific names and addresses

**Why not Faker**: Faker's `ar_AE` locale only provides phone numbers. No Emirates ID, no Arabic names, no UAE-specific data. Mimesis provides better Arabic locale coverage.

### 2. Custom Emirates ID Generator

**Decision**: Build a custom generator for Emirates ID numbers and card images.

**Rationale**: No mature free Python library generates valid UAE Emirates IDs. SynthIDGenerator only supports Italian ID cards. The Emirates ID format requires:
- 15-digit structure: `784-YYYY-NNNNNNN-C`
- Luhn (Mod 10) checksum validation
- MRZ zone with proper formatting
- Bilingual Arabic/English name rendering

**Implementation**: Custom Python module using Luhn algorithm for ID generation + Pillow/reportlab for card image rendering.

### 3. synthetic-statement (git main)

**Decision**: Use synthetic-statement for bank statement generation, extended with UAE bank templates.

**Rationale**: Purpose-built for bank statements with deterministic seed-based generation. The base library targets Indian banks (PhonePe, Paytm, GPay) but the architecture supports adding UAE bank templates (Emirates NBD, FAB, ADCB, Mashreq).

**Extension required**: Add UAE bank layout templates with AED currency, UAE bank names, IBAN formatting, and WPS salary transaction patterns.

### 4. faker-credit-score 1.0.0 + reportlab

**Decision**: Use faker-credit-score for credit score generation + custom reportlab template for AECB credit report PDFs.

**Rationale**:
- `faker-credit-score` generates realistic scores across 10 models (FICO 8/9/10, VantageScore 3.0/4.0) with tier-based generation
- No library generates AECB-format credit report PDFs
- Custom reportlab template renders the score, facilities, payment history, and inquiries into AECB-style PDF

**Schema alignment**: Credit score range 300-900 matches `credit_report_data.credit_score` CHECK constraint.

### 5. ResumeCraft 0.6.0

**Decision**: Use ResumeCraft for structured resume generation from JSON.

**Rationale**:
- Pydantic-validated JSON schema ensures data integrity
- ATS-friendly DOCX/PDF output
- Structured fields (`experience`, `education`, `skills`, `certifications`) map directly to `resume_data` and `resume_work_experience` tables
- CLI and library interfaces for batch generation

**Why not faker-file**: faker-file generates files with random content, not schema-compliant structured documents. ResumeCraft produces resumes with proper section structure that OCR extraction can reliably parse.

### 6. OCRSmith (replaces TRDG)

**Decision**: Use OCRSmith instead of TRDG for handwritten application form images.

**Rationale**: TRDG is incompatible with Python 3.11.12 — last release v1.8.0 (Aug 2022), Pillow 10+ breaks `FreeTypeFont.getsize()`, handwritten mode requires TensorFlow 1.x (no Python 3.11 support). OCRSmith provides native Arabic + Latin text rendering, modular augmentation pipeline (noise, blur, brightness, rotation), and active maintenance.

### 7. openpyxl + pandas

**Decision**: Use openpyxl + pandas for assets/liabilities XLSX generation.

**Rationale**: Direct control over cell formatting, formulas, and structured financial data. Generates XLSX files with proper asset categories, liability breakdowns, and net worth calculations.

---

## Generator Specifications

### Generator 1: Applicant Profile (Mimesis + pandas)

**Output**: DataFrame with correlated applicant fields
**Schema target**: `application_form_data`, `emirates_id_data`

**Fields generated**:
- `full_name` (English + Arabic) — Mimesis `Person.full_name()` with `ar_SA` locale
- `identity_number` — Custom Luhn generator (see Section: Emirates ID Algorithm)
- `date_of_birth` — Mimesis `Datetime.date()` constrained to 1950-2005
- `nationality` — Weighted: 60% UAE, 20% GCC, 20% other
- `contact_phone` — Mimesis `PhoneNumber()` with `ar_AE` locale (+971 format)
- `contact_email` — Derived from name
- `address` — JSONB: `{emirate, city, street, po_box}` using Mimesis `Address()` with UAE emirates
- `marital_status` — Weighted distribution
- `family_size` — Correlated with marital_status (1-8 range)
- `dependents` — JSONB array: `[{name, relationship, dob}]` correlated with family_size
- `employment_status` — Weighted: 60% employed, 15% self_employed, 15% unemployed, 10% retired
- `monthly_salary` — Correlated with employment_status and years_of_experience
- `other_income` — Random 0-20,000 AED for secondary income sources
- `total_monthly_income` — Sum of monthly_salary + other_income (enforced)
- `housing_status` — Weighted: 40% rented, 35% owned, 25% family_provided
- `monthly_rent` — Correlated with housing_status (rented = 3,000-15,000 AED)
- `monthly_mortgage` — Correlated with housing_status (owned = 5,000-25,000 AED)
- `support_category` — Weighted: divorced, abandoned, unknown_parentage, health_disability
- `supporting_documents` — JSONB array of document references for support category
- `is_declaration_signed` — Always TRUE (we generate signed forms)
- `declaration_date` — Within last 30 days

**Cross-document consistency**: The same applicant profile seeds all other generators. Name, DOB, identity_number, and address are shared across Emirates ID, bank statement, credit report, resume, and application form.

### Generator 2: Emirates ID (Custom)

**Output**: Image (PNG/JPG) + structured data
**Schema target**: `emirates_id_data`

**Emirates ID Algorithm**:
```
Format: 784-YYYY-NNNNNNN-C (15 digits)
- 784: UAE country code (ISO 3166)
- YYYY: Birth year (4 digits)
- NNNNNNN: 7-digit sequence number
- C: Luhn check digit

Luhn calculation:
1. Take first 14 digits
2. From right to left, double every second digit
3. If doubled value > 9, subtract 9
4. Sum all digits
5. Check digit = (10 - (sum % 10)) % 10
```

**Card image rendering**:
- Front: Photo, full_name_en, full_name_ar, identity_number, nationality, DOB, gender, expiry_date
- Back: MRZ zone (3-line format per ICAO 9303), card_number, barcode
- Dimensions: 85.6mm x 53.98mm (ISO/IEC 7810 ID-1)
- Resolution: 300 DPI for OCR testing

**Fields generated**:
- `identity_number` — Luhn-valid 15-digit ID
- `full_name_en` — From applicant profile
- `full_name_ar` — Arabic transliteration
- `nationality`, `date_of_birth`, `gender` — From applicant profile
- `card_number` — Random 10-digit serial
- `issue_date`, `expiry_date` — Issue date = 2-5 years ago, expiry = issue + 5/10 years
- `is_mrz_verified` — Always TRUE (we generate valid MRZ)
- `address` — JSONB from applicant profile
- `occupation`, `employer_name` — From applicant profile (post-2022 card fields)
- `marital_status` — From applicant profile
- `mother_name` — Mimesis female name generation
- `sponsor_name` — Employer name for employed, family member for dependents
- `sponsor_type` — `employer`, `family`, `government` based on employment_status
- `residency_type` — `employment`, `family`, `investor` based on employment_status
- `residency_number` — Random 13-digit residency file number

### Generator 3: Bank Statement (synthetic-statement + UAE templates)

**Output**: PDF + structured transaction data
**Schema target**: `bank_statement_data`, `bank_statement_transactions`

**UAE bank templates to add**:
- Emirates NBD
- First Abu Dhabi Bank (FAB)
- Abu Dhabi Commercial Bank (ADCB)
- Mashreq Bank
- Dubai Islamic Bank

**Fields generated**:
- `bank_name` — Random from UAE bank list
- `account_holder_name` — From applicant profile
- `account_number` — Random 10-15 digit account number
- `iban` — UAE IBAN format: `AE` + 2 check digits + 3-digit bank code + 16-digit account (Mod-97 checksum)
- `account_type` — Weighted: 70% Checking, 20% Savings, 10% Credit Card
- `currency` — Always `AED`
- `statement_period_start`, `statement_period_end` — Last 3-6 months
- `opening_balance` — Random 5,000-100,000 AED
- `closing_balance` — Calculated from transactions
- `total_debits`, `total_credits` — Sum of transactions
- `is_balance_reconciled` — Always TRUE (opening + credits - debits = closing)
- `transactions` — JSONB array of all transaction records
- `transaction_count` — Count of transactions in array

**Transaction generation**:
- `transaction_date` — Within statement period
- `description` — Realistic UAE transactions: salary (WPS), rent, DEWA, Etisalat, Carrefour, etc.
- `amount` — Signed DECIMAL(15,2), negative for debits, positive for credits
- `transaction_type` — debit/credit
- `running_balance` — Cumulative balance after each transaction
- `category` — salary, utility, rent, transfer, pos, atm
- `counterparty` — Debtor/creditor name derived from description
- `reference_number` — Random alphanumeric reference
- `is_wps_salary` — TRUE for salary credit transactions (Wage Protection System)
- `channel` — POS, ATM, IB, TRF, SWIFT
- `source_page` — Page number in generated PDF (for provenance tracking)
- `source_bounding_box` — JSONB coordinates of transaction row (for field-level tracking)

**Validation rule compliance**:
- Balance reconciliation: opening + credits - debits = closing (enforced)
- Statement period: start < end (enforced)
- No future transaction dates (enforced)
- Currency consistency: AED primary (enforced)

### Generator 4: Credit Report (faker-credit-score + reportlab)

**Output**: PDF + structured data
**Schema target**: `credit_report_data`, `credit_facilities`

**Credit score generation**:
- Use `faker-credit-score` with tier-based generation
- Map to AECB range: 300-900 (schema CHECK constraint)
- Generate correlated risk_band: Excellent (750-900), Very Good (650-749), Good (550-649), Fair (450-549), Poor (300-449)

**Fields generated**:
- `cb_subject_id` — Random AECB subject ID
- `identity_number` — From applicant profile (must match Emirates ID)
- `full_name` — From applicant profile
- `contact_details` — JSONB: {phone, email, address}
- `employment_info` — JSONB: {employer, occupation, salary}
- `credit_score` — 300-900, correlated with payment history
- `risk_band` — Derived from score
- `score_calculation_date` — Within last 90 days
- `total_active_accounts` — 1-8
- `total_closed_accounts` — 0-5
- `total_outstanding_balance` — Sum of facility balances
- `total_credit_limit` — Sum of facility limits
- `credit_utilization_ratio` — outstanding / limit * 100
- `active_facilities` — JSONB array of active credit facilities
- `closed_facilities` — JSONB array of closed credit facilities
- `payment_history` — JSONB array of 24-36 months payment data
- `late_payment_count` — Derived from payment history analysis
- `defaulted_accounts` — Count from facility status
- `bounced_cheques` — Random 0-2 (correlated with risk_band)
- `court_judgments` — Random 0-1 (correlated with risk_band)
- `has_bankruptcy_records` — Boolean (TRUE only for Poor risk_band)
- `inquiry_count` — Random 0-10 inquiries in last 12 months
- `inquiries` — JSONB array of inquiry records

**Facility generation** (for `credit_facilities` table):
- `facility_type` — credit_card, personal_loan, mortgage, auto_loan, overdraft
- `lender_name` — UAE bank names
- `status` — active/closed/defaulted
- `opened_date` — Random date within last 10 years
- `closed_date` — NULL for active, random date for closed/defaulted
- `credit_limit`, `current_balance`, `monthly_payment`
- `payment_status` — current, 30_days_late, 60_days_late, 90_days_late, defaulted

**Cross-document validation**:
- `identity_number` matches Emirates ID document
- `total_outstanding_balance` equals sum of facility balances
- Payment history timeline consistency (no future dates)

### Generator 5: Resume (ResumeCraft)

**Output**: DOCX/PDF + structured data
**Schema target**: `resume_data`, `resume_work_experience`

**JSON schema mapping**:
```json
{
  "name": "Ahmed Hassan",
  "contact": {
    "email": "ahmed.hassan@email.com",
    "phone": "+971501234567",
    "location": "Dubai, UAE"
  },
  "summary": "Senior software engineer with 8 years...",
  "experience": [
    {
      "company": "Emirates NBD",
      "title": "Senior Developer",
      "location": "Dubai, UAE",
      "start_date": "2020-01",
      "end_date": "Present",
      "bullets": ["Led migration of core banking..."]
    }
  ],
  "education": [
    {
      "institution": "UAE University",
      "degree": "B.Sc. Computer Science",
      "duration": "2012 - 2016"
    }
  ],
  "skills": [
    {"category": "Languages", "items": "Python, Java, SQL"}
  ],
  "certifications": [
    {"name": "AWS Solutions Architect", "issuer": "Amazon", "date": "2024"}
  ]
}
```

**Fields mapped to schema**:
- `full_name` — From JSON `name`
- `email`, `phone`, `location` — From JSON `contact`
- `years_of_experience` — Calculated from earliest start_date
- `work_experience` — JSONB array from JSON `experience`
- `total_positions` — Count of experience entries
- `current_employer` — Last entry where end_date is null/Present
- `current_job_title` — Title of current position
- `education` — JSONB array from JSON `education`
- `highest_degree` — From education array
- `skills` — JSONB array from JSON `skills`
- `skill_count` — Total skills across categories
- `certifications` — JSONB array from JSON `certifications`

**Validation rule compliance**:
- Date consistency: start_date < end_date (enforced by Pydantic validation)
- No future dates (enforced)
- Current employment: end_date = null or "Present" (enforced)

### Generator 6b: Resume Work Experience (ResumeCraft)

**Output**: Individual work experience records
**Schema target**: `resume_work_experience`

**Fields generated**:
- `job_title` — From JSON experience entry
- `company` — From JSON experience entry
- `location` — From JSON experience entry
- `start_date` — From JSON experience entry
- `end_date` — NULL for current position, otherwise end date
- `is_current` — TRUE if end_date is null/Present
- `description` — From JSON bullets array
- `achievements` — Array of achievement bullets
- `duration_months` — Calculated from start_date to end_date (or now if current)
- `industry` — Derived from company name (banking, technology, retail, etc.)

**Cross-reference validation**:
- Each work experience record links to parent `resume_data` via document_id
- `is_current = TRUE` matches `current_employer` and `current_job_title` in parent record
- Duration calculations are deterministic and reproducible

### Generator 7: Assets/Liabilities (openpyxl + pandas)

**Output**: XLSX + structured data
**Schema target**: `assets_liabilities_data`

**Fields generated**:
- `applicant_name` — From applicant profile
- `statement_date` — Within last 6 months
- `cash_and_deposits` — Random 1,000-50,000 AED
- `savings_accounts` — Random 5,000-200,000 AED
- `investment_accounts` — Random 0-500,000 AED
- `retirement_accounts` — Random 0-300,000 AED
- `real_estate_value` — Correlated with housing_status (owned = high value)
- `vehicle_value` — Random 20,000-200,000 AED
- `other_assets` — Random 0-50,000 AED
- `total_assets` — Sum of all asset categories (enforced)
- `mortgage_balance` — Correlated with real_estate_value
- `personal_loans` — Random 0-100,000 AED
- `credit_card_debt` — Correlated with credit report facilities
- `student_loans` — Random 0-50,000 AED
- `other_liabilities` — Random 0-20,000 AED
- `total_liabilities` — Sum of all liability categories (enforced)
- `net_worth` — total_assets - total_liabilities (enforced)
- `monthly_income` — From applicant profile

**Validation rule compliance**:
- net_worth = total_assets - total_liabilities (enforced by calculation)
- All values >= 0 (enforced)
- Statement date within last 6 months (enforced)
- Asset categories sum to total_assets (enforced by calculation)

### Generator 8: Application Form (OCRSmith)

**Output**: Image (PNG/JPG) of handwritten form
**Schema target**: `application_form_data`

**Form layout**:
- Pre-printed form template with blank fields
- Handwritten text rendered using OCRSmith with Arabic font support
- Fields: name, identity_number, DOB, nationality, phone, email, address, marital_status, family_size, employment_status, employer_name, occupation, monthly_salary, housing_status, support_category, declaration signature

**Arabic support**: OCRSmith provides native Arabic + Latin text rendering for bilingual form fields.

**Image augmentation**: OCRSmith's modular pipeline applies blur, noise, brightness, and rotation to simulate scanned documents for OCR pipeline testing.

---

## Cross-Document Consistency Engine

All generators share a single `ApplicantProfile` seed object that ensures consistency across documents:

```python
class ApplicantProfile:
    full_name_en: str
    full_name_ar: str
    identity_number: str  # Luhn-valid Emirates ID
    date_of_birth: date
    nationality: str
    gender: str
    contact_phone: str
    contact_email: str
    address: dict  # {emirate, city, street, po_box}
    employment_status: str
    employer_name: str
    occupation: str
    monthly_salary: Decimal
    other_income: Decimal
    total_monthly_income: Decimal
    marital_status: str
    family_size: int
    dependents: list  # [{name, relationship, dob}]
    housing_status: str
    monthly_rent: Decimal
    monthly_mortgage: Decimal
    support_category: str
    supporting_documents: list
    mother_name: str
    sponsor_name: str
    sponsor_type: str
    residency_type: str
    residency_number: str
```

**Consistency rules**:
1. `identity_number` is identical across Emirates ID, credit report, and application form
2. `full_name` variations are reconcilable (same person, minor spelling differences allowed)
3. `date_of_birth` is identical across Emirates ID, application form, and resume
4. `monthly_salary` in application form matches WPS salary transactions in bank statement
5. `employer_name` in application form matches resume current_employer
6. Credit report `identity_number` matches Emirates ID `identity_number`
7. Address fields are consistent (same emirate, compatible city/street)
8. `total_monthly_income` in application form equals `monthly_salary` + `other_income`
9. Credit report `total_outstanding_balance` matches assets/liabilities `credit_card_debt` + `personal_loans`
10. `dependents` count in application form is consistent with `family_size`
11. Resume `is_current` work experience matches application form `employer_name` and `occupation`

---

## Seed and Reproducibility

All generators accept a `seed` parameter for deterministic output:

```python
from mimesis import Person, Address
from mimesis.locales import Locale

def generate_applicant(seed: int) -> ApplicantProfile:
    person = Person(Locale.AR_SA, seed=seed)
    address = Address(Locale.AR_SA, seed=seed)
    # ... generate profile
```

**Benefits**:
- Fixed seed produces byte-identical documents
- Enables regression testing of extraction pipeline
- Commit seed + expected extraction results as test fixtures

---

## Installation Commands

```bash
# Core data generation
.\.venv\Scripts\pip.exe install mimesis==19.1.0
.\.venv\Scripts\pip.exe install pandas>=2.0.0

# Document-specific generators
.\.venv\Scripts\pip.exe install resumecraft==0.6.0
.\.venv\Scripts\pip.exe install "synthetic-statement[pdf] @ git+https://github.com/RohitSSolanki/synthetic-statement@main"
.\.venv\Scripts\pip.exe install faker-credit-score==1.0.0

# Image/PDF rendering
.\.venv\Scripts\pip.exe install reportlab>=4.0.0
.\.venv\Scripts\pip.exe install Pillow>=10.0.0
.\.venv\Scripts\pip.exe install ocrsmith>=0.1.0

# XLSX generation
.\.venv\Scripts\pip.exe install openpyxl>=3.1.0
```

---

## Future Improvements

1. **UAE bank template library**: Contribute UAE bank templates back to synthetic-statement project
2. **Emirates ID open-source library**: Publish custom Emirates ID generator as standalone PyPI package
3. **AECB credit report template**: Open-source the AECB PDF template for community use
4. **GAN-based document generation**: Explore GAN-generated document images for more realistic OCR testing (requires GPU)
5. **Mimesis UAE locale pack**: Contribute UAE-specific providers (Emirates ID, IBAN, bank names) to Mimesis
