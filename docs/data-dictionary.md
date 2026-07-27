# Data Dictionary — PostgreSQL Schema

UAE Social Support Application — document processing and applicant workflow database.

## Overview

The schema consists of **16 tables** organized into four logical groups:

| Group | Tables | Purpose |
|-------|--------|---------|
| Core | `applicants`, `applications`, `documents` | Applicant identity, workflow state, uploaded documents |
| Extraction | `emirates_id_data`, `bank_statement_data`, `bank_statement_transactions`, `credit_report_data`, `credit_facilities`, `resume_data`, `resume_work_experience`, `assets_liabilities_data`, `application_form_data`, `document_extraction_fields` | Per-document-type extracted structured data |
| Validation | `cross_document_validations` | Cross-document consistency checks and discrepancy tracking |
| Infrastructure | `document_audit_log`, `document_processing_queue` | Audit trail and async processing queue |

All tables use `UUID` primary keys (generated via `uuid4`). Timestamps use `TIMESTAMPTZ` with `server_default=now()`. Flexible semi-structured data is stored in `JSONB` columns with GIN indexes where queried.

---

## Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  applicants  │──1:N──│ applications │       │  documents  │
└─────────────┘       └─────────────┘       └──────┬──────┘
                                                   │ 1:N
                     ┌─────────────────────────────┼─────────────────────────────┐
                     │                             │                             │
              ┌──────┴──────┐               ┌──────┴──────┐               ┌──────┴──────┐
              │emirates_id_ │               │bank_statement│              │credit_report │
              │    data     │               │    data      │               │    data      │
              └─────────────┘               └──────┬───────┘               └──────┬───────┘
                                                   │ 1:N                          │ 1:N
                                            ┌──────┴───────┐               ┌──────┴───────┐
                                            │bank_statement│               │  credit_     │
                                            │ transactions │               │  facilities   │
                                            └─────────────┘               └─────────────┘

                     ┌─────────────────────────────┼─────────────────────────────┐
                     │                             │                             │
              ┌──────┴──────┐               ┌──────┴──────┐               ┌──────┴──────┐
              │ resume_data │               │assets_liab_ │               │application_ │
              │             │               │  ilities_data│              │  form_data   │
              └──────┬──────┘               └─────────────┘               └─────────────┘
                     │ 1:N
              ┌──────┴──────────┐
              │resume_work_     │
              │  experience     │
              └─────────────────┘

┌──────────────────────────┐
│ cross_document_validations│◄─── references applicant_id + source_documents[]
└──────────────────────────┘

┌──────────────────────┐   ┌──────────────────────────┐
│  document_audit_log   │   │ document_processing_queue │
└──────────────────────┘   └──────────────────────────┘
         │ 1:N                        │ 1:N
         └─────────────── documents ──┘
                         (FK ondelete CASCADE)

┌──────────────────────────┐
│ document_extraction_fields│◄─── generic key-value extraction results
└──────────────────────────┘
```

---

## Core Tables

### `applicants`

Central identity record for a benefit applicant. One row per person, identified by their Emirates ID number.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `identity_number` | `VARCHAR(20)` | UNIQUE, NOT NULL, indexed | Luhn-valid Emirates ID number; natural key for deduplication |
| `full_name` | `TEXT` | nullable | Full legal name as it appears on Emirates ID |
| `date_of_birth` | `DATE` | nullable | Used for cross-document age consistency checks |
| `nationality` | `TEXT` | nullable | Nationality — relevant for eligibility rules |
| `phone` | `TEXT` | nullable | Contact number |
| `email` | `TEXT` | nullable | Contact email |
| `address` | `JSONB` | nullable, GIN indexed | Structured address: `{emirate, city, area, street}` |
| `marital_status` | `TEXT` | nullable | Values: `single`, `married`, `divorced`, `widowed` |
| `family_size` | `INTEGER` | nullable | Number of dependents including applicant |
| `employment_status` | `TEXT` | nullable | Values: `employed`, `self_employed`, `unemployed`, `retired` |
| `employer_name` | `TEXT` | nullable | Current employer name |
| `occupation` | `TEXT` | nullable | Job title or profession |
| `housing_status` | `TEXT` | nullable | Values: `owned`, `rented`, `family_provided`, `shelter` |
| `support_category` | `TEXT` | nullable | Category of support requested: `housing`, `utility`, `education`, `medical`, `living_expenses` |
| `monthly_salary` | `NUMERIC(15,2)` | nullable | Gross monthly income in AED |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_applicants_identity_number` — B-tree on `identity_number`

**Relationships:**
- One-to-many → `applications` (cascade delete)

---

### `applications`

Tracks a single benefit application through the 7-phase LangGraph workflow. An applicant may have multiple applications over time.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `applicant_id` | `UUID` | FK → `applicants.id` (CASCADE), indexed, NOT NULL | Links to the applicant |
| `status` | `VARCHAR(20)` | NOT NULL, default `'in_progress'` | Values: `in_progress`, `completed`, `manual_review` |
| `current_phase` | `VARCHAR(30)` | NOT NULL, default `'intake'` | Current LangGraph phase: `authentication`, `intake`, `document_collection`, `processing`, `review`, `decision`, `enablement` |
| `langgraph_checkpoint` | `JSONB` | nullable | Serialized LangGraph checkpoint for session resume |
| `eligibility_score` | `FLOAT` | nullable | Composite score from eligibility agent (0.0–1.0) |
| `decision` | `TEXT` | nullable | Final decision: `approved`, `soft_decline`, `manual_review` |
| `decision_explanation` | `TEXT` | nullable | Human-readable explanation generated by decision agent |
| `validation_confidence` | `FLOAT` | nullable | Aggregate confidence from validation agent (added in migration `20260727001`) |
| `phase_completed` | `JSONB` | nullable | Per-phase completion flags: `{intake: true, document_collection: true, ...}` |
| `eligibility_factors` | `JSONB` | nullable | Factor breakdown from eligibility agent: `{income_factor, credit_factor, employment_factor, ...}` |
| `state_snapshot` | `JSONB` | nullable | Full LangGraph state snapshot for recovery (added in migration `20260726001`) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Application creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_applications_applicant_id` — B-tree on `applicant_id`
- `idx_applications_status` — B-tree on `status`

**Relationships:**
- Many-to-one ← `applicants`
- One-to-many → `documents` (conceptual; documents reference `applicant_id` directly for cross-application sharing)

---

### `documents`

Registry of all uploaded documents. One row per uploaded file, with type-specific extracted data in child tables.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `applicant_id` | `UUID` | NOT NULL | References the applicant who uploaded the document |
| `document_type` | `VARCHAR(50)` | NOT NULL, check constraint | Values: `emirates_id`, `bank_statement`, `credit_report`, `resume`, `assets_liabilities`, `application_form` |
| `processing_status` | `VARCHAR(30)` | NOT NULL, default `'uploaded'` | Values: `uploaded`, `classifying`, `extracting`, `validating`, `completed`, `failed`, `archived` |
| `file_path` | `TEXT` | NOT NULL | Storage path (S3-compatible or local filesystem) |
| `file_format` | `TEXT` | nullable | Values: `pdf`, `xlsx`, `jpg`, `png`, `docx` |
| `file_size_bytes` | `BIGINT` | nullable | File size in bytes |
| `file_hash` | `TEXT` | NOT NULL | SHA-256 hash for deduplication and integrity |
| `uploaded_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Upload timestamp |
| `processing_started_at` | `TIMESTAMPTZ` | nullable | Processing pipeline start timestamp |
| `processing_completed_at` | `TIMESTAMPTZ` | nullable | Processing pipeline completion timestamp |
| `extraction_status` | `TEXT` | nullable, default `'pending'` | Values: `pending`, `success`, `partial`, `failed` |
| `validation_status` | `TEXT` | nullable, default `'pending'` | Values: `pending`, `valid`, `invalid`, `warnings` |
| `overall_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Aggregate confidence across all extracted fields |
| `metadata` | `JSONB` | nullable, GIN indexed | Document metadata: page count, dimensions, OCR language, etc. |
| `error_log` | `TEXT` | nullable | Concatenated error messages from failed processing steps |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_documents_applicant_id` — B-tree on `(applicant_id, document_type)`
- `idx_documents_processing_status` — B-tree on `(processing_status, uploaded_at DESC)`
- `idx_documents_extraction_status` — Partial B-tree on `extraction_status` where `extraction_status != 'success'`
- `idx_documents_metadata` — GIN on `metadata`

**Relationships:**
- One-to-one → `emirates_id_data`, `bank_statement_data`, `credit_report_data`, `resume_data`, `assets_liabilities_data`, `application_form_data` (all `uselist=False`, cascade delete)
- One-to-many → `document_audit_log`, `document_processing_queue`, `document_extraction_fields` (cascade delete)

---

## Extraction Tables

### `emirates_id_data`

Extracted data from Emirates ID cards (front and back). One row per Emirates ID document.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), UNIQUE, NOT NULL | Links to parent document |
| `identity_number` | `TEXT` | UNIQUE, NOT NULL, indexed | 15-digit Emirates ID number; Luhn-validated |
| `full_name_en` | `TEXT` | NOT NULL | Name in English as on card |
| `full_name_ar` | `TEXT` | nullable | Name in Arabic as on card |
| `nationality` | `TEXT` | NOT NULL | Nationality |
| `date_of_birth` | `DATE` | NOT NULL | Date of birth |
| `gender` | `TEXT` | NOT NULL, check `IN ('Male', 'Female')` | Gender |
| `card_number` | `TEXT` | nullable | Card serial number |
| `issue_date` | `DATE` | nullable | Card issue date |
| `expiry_date` | `DATE` | NOT NULL, indexed | Card expiry date — used for eligibility validity checks |
| `is_mrz_verified` | `BOOLEAN` | NOT NULL, default `false` | Whether MRZ (machine-readable zone) checksum passed |
| `address` | `JSONB` | nullable, GIN indexed | Structured address from card |
| `occupation` | `TEXT` | nullable | Occupation listed on card |
| `employer_name` | `TEXT` | nullable | Sponsor/employer name |
| `marital_status` | `TEXT` | nullable | Marital status |
| `mother_name` | `TEXT` | nullable | Mother's name — used for cross-document kinship validation |
| `sponsor_name` | `TEXT` | nullable | Sponsor name |
| `sponsor_type` | `TEXT` | nullable | Sponsor type: `father`, `husband`, `employer`, `government` |
| `residency_type` | `TEXT` | nullable | Residency type |
| `residency_number` | `TEXT` | nullable | Residency permit number |
| `extraction_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Per-field aggregate confidence |
| `raw_extracted_data` | `JSONB` | nullable | Raw extraction output before normalization |
| `validation_results` | `JSONB` | nullable | Validation agent findings for this document |
| `source_coordinates` | `JSONB` | nullable | Bounding box coordinates for each extracted field |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_emirates_id_identity_number` — B-tree on `identity_number`
- `idx_emirates_id_expiry_date` — B-tree on `expiry_date`
- `idx_emirates_id_nationality` — B-tree on `nationality`
- `idx_emirates_id_address` — GIN on `address`

---

### `bank_statement_data`

Extracted data from bank statements. One row per bank statement document.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), UNIQUE, NOT NULL | Links to parent document |
| `bank_name` | `TEXT` | NOT NULL | Bank name: `Emirates NBD`, `FAB`, `ADCB`, `Mashreq`, etc. |
| `account_holder_name` | `TEXT` | NOT NULL | Name on account |
| `account_number` | `TEXT` | NOT NULL, indexed | Account number |
| `iban` | `TEXT` | nullable | IBAN — validated format |
| `account_type` | `TEXT` | nullable | Values: `savings`, `current`, `salary` |
| `currency` | `TEXT` | NOT NULL, default `'AED'` | Currency code |
| `statement_period_start` | `DATE` | NOT NULL, indexed | Statement start date |
| `statement_period_end` | `DATE` | NOT NULL, indexed | Statement end date |
| `opening_balance` | `NUMERIC(15,2)` | NOT NULL | Opening balance in AED |
| `closing_balance` | `NUMERIC(15,2)` | NOT NULL | Closing balance in AED |
| `total_debits` | `NUMERIC(15,2)` | NOT NULL | Total debits during period |
| `total_credits` | `NUMERIC(15,2)` | NOT NULL | Total credits during period |
| `is_balance_reconciled` | `BOOLEAN` | NOT NULL, default `false` | Whether opening + credits − debits = closing |
| `transactions` | `JSONB` | NOT NULL, GIN indexed | Denormalized transaction list for quick access |
| `transaction_count` | `INTEGER` | NOT NULL | Number of extracted transactions |
| `extraction_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Per-document aggregate confidence |
| `raw_extracted_data` | `JSONB` | nullable | Raw extraction output |
| `validation_results` | `JSONB` | nullable | Validation findings |
| `source_coordinates` | `JSONB` | nullable | Bounding boxes |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_bank_stmt_document_id` — B-tree on `document_id`
- `idx_bank_stmt_account_number` — B-tree on `account_number`
- `idx_bank_stmt_period` — B-tree on `(statement_period_start, statement_period_end)`
- `idx_bank_stmt_transactions` — GIN on `transactions`

**Relationships:**
- One-to-many → `bank_statement_transactions` (cascade delete)

---

### `bank_statement_transactions`

Individual transactions extracted from bank statements. One row per transaction line item.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `bank_statement_data.id` (CASCADE), NOT NULL, indexed | Links to parent bank statement |
| `transaction_hash` | `TEXT` | UNIQUE, NOT NULL | SHA-256 of `(date, description, amount)` for deduplication |
| `transaction_date` | `DATE` | NOT NULL, indexed | Transaction posting date |
| `description` | `TEXT` | NOT NULL | Transaction description/narration |
| `amount` | `NUMERIC(15,2)` | NOT NULL | Transaction amount in AED |
| `transaction_type` | `TEXT` | NOT NULL, check `IN ('debit', 'credit')` | Debit or credit |
| `running_balance` | `NUMERIC(15,2)` | nullable | Running balance after transaction |
| `category` | `TEXT` | nullable, indexed | Auto-categorized: `salary`, `rent`, `grocery`, `transfer`, `atm`, `fee`, etc. |
| `counterparty` | `TEXT` | nullable | Counterparty name |
| `reference_number` | `TEXT` | nullable | Bank reference number |
| `is_wps_salary` | `BOOLEAN` | NOT NULL, default `false` | Whether this is a WPS (Wage Protection System) salary credit |
| `channel` | `TEXT` | nullable | Channel: `atm`, `online`, `branch`, `pos`, `transfer` |
| `source_page` | `INTEGER` | nullable | PDF page number |
| `source_bounding_box` | `JSONB` | nullable, GIN indexed | Bounding box on source page |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |

**Indexes:**
- `idx_bank_txn_document_id` — B-tree on `document_id`
- `idx_bank_txn_transaction_date` — B-tree on `transaction_date`
- `idx_bank_txn_category` — B-tree on `category`
- `idx_bank_txn_is_wps_salary` — Partial B-tree on `is_wps_salary` where `is_wps_salary = TRUE`
- `idx_bank_txn_source_bounding_box` — GIN on `source_bounding_box`

---

### `credit_report_data`

Extracted data from AECB (Al Etihad Credit Bureau) credit reports. One row per credit report document.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), UNIQUE, NOT NULL | Links to parent document |
| `cb_subject_id` | `TEXT` | NOT NULL | AECB subject identifier |
| `identity_number` | `TEXT` | NOT NULL, indexed | Emirates ID number |
| `full_name` | `TEXT` | NOT NULL | Full name on report |
| `contact_details` | `JSONB` | nullable, GIN indexed | Phone, email, address from report |
| `employment_info` | `JSONB` | nullable, GIN indexed | Employer, position, salary from report |
| `credit_score` | `INTEGER` | NOT NULL, check `[300, 900]`, indexed | AECB credit score |
| `risk_band` | `TEXT` | NOT NULL | Risk band: `low`, `medium`, `high`, `very_high` |
| `score_calculation_date` | `DATE` | nullable | Date when score was calculated |
| `total_active_accounts` | `INTEGER` | NOT NULL | Number of active credit facilities |
| `total_closed_accounts` | `INTEGER` | NOT NULL | Number of closed facilities |
| `total_outstanding_balance` | `NUMERIC(15,2)` | NOT NULL | Total outstanding balance in AED |
| `total_credit_limit` | `NUMERIC(15,2)` | nullable | Total credit limit across all facilities |
| `credit_utilization_ratio` | `NUMERIC(5,2)` | nullable | Utilization ratio as percentage |
| `active_facilities` | `JSONB` | nullable, GIN indexed | Denormalized active facility list |
| `closed_facilities` | `JSONB` | nullable, GIN indexed | Denormalized closed facility list |
| `payment_history` | `JSONB` | nullable, GIN indexed | Payment history summary |
| `late_payment_count` | `INTEGER` | NOT NULL, default `0` | Count of late payments |
| `defaulted_accounts` | `INTEGER` | NOT NULL, default `0` | Count of defaulted accounts |
| `bounced_cheques` | `INTEGER` | NOT NULL, default `0` | Count of bounced cheques |
| `court_judgments` | `INTEGER` | NOT NULL, default `0` | Count of court judgments |
| `has_bankruptcy_records` | `BOOLEAN` | NOT NULL, default `false` | Bankruptcy flag — hard decline if true |
| `inquiry_count` | `INTEGER` | NOT NULL, default `0` | Number of credit inquiries |
| `inquiries` | `JSONB` | nullable | Inquiry details |
| `extraction_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Per-document aggregate confidence |
| `raw_extracted_data` | `JSONB` | nullable | Raw extraction output |
| `validation_results` | `JSONB` | nullable | Validation findings |
| `source_coordinates` | `JSONB` | nullable | Bounding boxes |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_credit_report_document_id` — B-tree on `document_id`
- `idx_credit_report_credit_score` — B-tree on `credit_score`
- `idx_credit_report_identity_number` — B-tree on `identity_number`
- `idx_credit_report_contact_details` — GIN on `contact_details`
- `idx_credit_report_employment_info` — GIN on `employment_info`
- `idx_credit_report_active_facilities` — GIN on `active_facilities`
- `idx_credit_report_payment_history` — GIN on `payment_history`

**Relationships:**
- One-to-many → `credit_facilities` (cascade delete)

---

### `credit_facilities`

Individual credit facilities extracted from credit reports. One row per facility.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `credit_report_data.id` (CASCADE), NOT NULL, indexed | Links to parent credit report |
| `facility_type` | `TEXT` | NOT NULL | Values: `credit_card`, `personal_loan`, `mortgage`, `auto_loan`, `overdraft` |
| `lender_name` | `TEXT` | NOT NULL | Bank or financial institution name |
| `account_number` | `TEXT` | nullable | Account/facility number |
| `status` | `TEXT` | NOT NULL, indexed | Values: `active`, `closed`, `delinquent`, `settled` |
| `opened_date` | `DATE` | nullable | Facility opening date |
| `closed_date` | `DATE` | nullable | Facility closure date |
| `credit_limit` | `NUMERIC(15,2)` | nullable | Credit limit or original loan amount |
| `current_balance` | `NUMERIC(15,2)` | NOT NULL | Current outstanding balance |
| `monthly_payment` | `NUMERIC(15,2)` | nullable | Monthly installment amount |
| `payment_status` | `TEXT` | nullable | Values: `current`, `30dpd`, `60dpd`, `90dpd`, `written_off` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |

**Indexes:**
- `idx_credit_facilities_document_id` — B-tree on `document_id`
- `idx_credit_facilities_status` — B-tree on `status`

---

### `resume_data`

Extracted data from resumes/CVs. One row per resume document.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), UNIQUE, NOT NULL | Links to parent document |
| `full_name` | `TEXT` | NOT NULL, indexed | Name from resume |
| `email` | `TEXT` | nullable, indexed | Email from resume |
| `phone` | `TEXT` | nullable | Phone from resume |
| `location` | `TEXT` | nullable | Location from resume |
| `summary` | `TEXT` | nullable | Professional summary |
| `years_of_experience` | `INTEGER` | nullable | Total years of experience |
| `work_experience` | `JSONB` | NOT NULL, GIN indexed | Denormalized work history |
| `total_positions` | `INTEGER` | NOT NULL | Number of positions extracted |
| `current_employer` | `TEXT` | nullable | Current employer name |
| `current_job_title` | `TEXT` | nullable | Current job title |
| `education` | `JSONB` | nullable, GIN indexed | Education history |
| `highest_degree` | `TEXT` | nullable | Highest degree obtained |
| `skills` | `JSONB` | nullable, GIN indexed | Extracted skills list |
| `skill_count` | `INTEGER` | NOT NULL, default `0` | Number of distinct skills |
| `certifications` | `JSONB` | nullable | Certifications |
| `extraction_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Per-document aggregate confidence |
| `raw_extracted_data` | `JSONB` | nullable | Raw extraction output |
| `validation_results` | `JSONB` | nullable | Validation findings |
| `source_coordinates` | `JSONB` | nullable | Bounding boxes |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_resume_document_id` — B-tree on `document_id`
- `idx_resume_full_name` — B-tree on `full_name`
- `idx_resume_email` — B-tree on `email`
- `idx_resume_work_experience` — GIN on `work_experience`
- `idx_resume_education` — GIN on `education`
- `idx_resume_skills` — GIN on `skills`

**Relationships:**
- One-to-many → `resume_work_experience` (cascade delete)

---

### `resume_work_experience`

Individual work experience entries from resumes. One row per position.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `resume_data.id` (CASCADE), NOT NULL, indexed | Links to parent resume |
| `job_title` | `TEXT` | NOT NULL | Job title |
| `company` | `TEXT` | NOT NULL, indexed (partial: current) | Company name |
| `location` | `TEXT` | nullable | Job location |
| `start_date` | `DATE` | NOT NULL | Start date |
| `end_date` | `DATE` | nullable | End date (null if current) |
| `is_current` | `BOOLEAN` | NOT NULL, default `false` | Whether this is the current position |
| `description` | `TEXT` | nullable | Job description |
| `achievements` | `TEXT[]` (ARRAY) | nullable | List of achievements |
| `duration_months` | `INTEGER` | nullable | Computed duration in months |
| `industry` | `TEXT` | nullable | Industry sector |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |

**Indexes:**
- `idx_resume_work_exp_document_id` — B-tree on `document_id`
- `idx_resume_work_exp_is_current` — Partial B-tree on `company` where `is_current = TRUE`

---

### `assets_liabilities_data`

Extracted data from assets and liabilities statements (XLSX format). One row per statement.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), UNIQUE, NOT NULL | Links to parent document |
| `applicant_name` | `TEXT` | NOT NULL | Name on statement |
| `statement_date` | `DATE` | NOT NULL, indexed | Statement date |
| `cash_and_deposits` | `NUMERIC(15,2)` | NOT NULL, default `0` | Cash and bank deposits in AED |
| `savings_accounts` | `NUMERIC(15,2)` | NOT NULL, default `0` | Savings account balances |
| `investment_accounts` | `NUMERIC(15,2)` | NOT NULL, default `0` | Investment account values |
| `retirement_accounts` | `NUMERIC(15,2)` | NOT NULL, default `0` | Retirement fund values |
| `real_estate_value` | `NUMERIC(15,2)` | NOT NULL, default `0` | Real estate holdings value |
| `vehicle_value` | `NUMERIC(15,2)` | NOT NULL, default `0` | Vehicle values |
| `other_assets` | `NUMERIC(15,2)` | NOT NULL, default `0` | Other assets |
| `total_assets` | `NUMERIC(15,2)` | NOT NULL | Sum of all asset categories |
| `mortgage_balance` | `NUMERIC(15,2)` | NOT NULL, default `0` | Outstanding mortgage |
| `personal_loans` | `NUMERIC(15,2)` | NOT NULL, default `0` | Personal loan balances |
| `credit_card_debt` | `NUMERIC(15,2)` | NOT NULL, default `0` | Credit card debt |
| `student_loans` | `NUMERIC(15,2)` | NOT NULL, default `0` | Student loan balances |
| `other_liabilities` | `NUMERIC(15,2)` | NOT NULL, default `0` | Other liabilities |
| `total_liabilities` | `NUMERIC(15,2)` | NOT NULL | Sum of all liability categories |
| `net_worth` | `NUMERIC(15,2)` | NOT NULL | `total_assets − total_liabilities` |
| `monthly_income` | `NUMERIC(15,2)` | nullable | Total monthly income |
| `income_sources` | `JSONB` | nullable, GIN indexed | Breakdown of income sources |
| `asset_details` | `JSONB` | nullable, GIN indexed | Detailed asset descriptions |
| `liability_details` | `JSONB` | nullable, GIN indexed | Detailed liability descriptions |
| `extraction_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Per-document aggregate confidence |
| `raw_extracted_data` | `JSONB` | nullable | Raw extraction output |
| `validation_results` | `JSONB` | nullable | Validation findings |
| `source_coordinates` | `JSONB` | nullable | Bounding boxes |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_assets_liabilities_document_id` — B-tree on `document_id`
- `idx_assets_liabilities_net_worth` — B-tree on `net_worth`
- `idx_assets_liabilities_statement_date` — B-tree on `statement_date`
- `idx_assets_liabilities_income_sources` — GIN on `income_sources`
- `idx_assets_liabilities_asset_details` — GIN on `asset_details`
- `idx_assets_liabilities_liability_details` — GIN on `liability_details`

---

### `application_form_data`

Extracted data from handwritten/printed application forms. One row per form.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), UNIQUE, NOT NULL | Links to parent document |
| `applicant_name` | `TEXT` | NOT NULL | Name on form |
| `identity_number` | `TEXT` | NOT NULL, indexed | Emirates ID number |
| `date_of_birth` | `DATE` | NOT NULL | Date of birth |
| `nationality` | `TEXT` | NOT NULL | Nationality |
| `contact_phone` | `TEXT` | NOT NULL | Contact phone number |
| `contact_email` | `TEXT` | nullable | Contact email |
| `address` | `JSONB` | NOT NULL, GIN indexed | Structured address |
| `marital_status` | `TEXT` | nullable | Marital status |
| `family_size` | `INTEGER` | nullable | Family size |
| `dependents` | `JSONB` | nullable, GIN indexed | Dependent details |
| `employment_status` | `TEXT` | NOT NULL | Employment status |
| `employer_name` | `TEXT` | nullable | Employer name |
| `occupation` | `TEXT` | nullable | Occupation |
| `monthly_salary` | `NUMERIC(15,2)` | nullable | Monthly salary |
| `other_income` | `NUMERIC(15,2)` | NOT NULL, default `0` | Other monthly income |
| `total_monthly_income` | `NUMERIC(15,2)` | NOT NULL | Total monthly income |
| `housing_status` | `TEXT` | nullable | Housing status |
| `monthly_rent` | `NUMERIC(15,2)` | nullable | Monthly rent payment |
| `monthly_mortgage` | `NUMERIC(15,2)` | nullable | Monthly mortgage payment |
| `support_category` | `TEXT` | nullable, indexed | Requested support category |
| `supporting_documents` | `JSONB` | nullable, GIN indexed | List of attached supporting documents |
| `is_declaration_signed` | `BOOLEAN` | NOT NULL, default `false` | Whether applicant signed declaration |
| `declaration_date` | `DATE` | nullable | Declaration signing date |
| `extraction_confidence` | `FLOAT` | nullable, check `[0.0, 1.0]` | Per-document aggregate confidence |
| `raw_extracted_data` | `JSONB` | nullable | Raw extraction output |
| `validation_results` | `JSONB` | nullable | Validation findings |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_application_form_document_id` — B-tree on `document_id`
- `idx_application_form_identity_number` — B-tree on `identity_number`
- `idx_application_form_total_monthly_income` — B-tree on `total_monthly_income`
- `idx_application_form_support_category` — B-tree on `support_category`
- `idx_application_form_address` — GIN on `address`
- `idx_application_form_dependents` — GIN on `dependents`
- `idx_application_form_supporting_documents` — GIN on `supporting_documents`

---

### `document_extraction_fields`

Generic key-value extraction results for any document type. Used for ad-hoc fields not covered by type-specific tables.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), NOT NULL, indexed | Links to parent document |
| `field_name` | `TEXT` | NOT NULL, indexed | Name of the extracted field |
| `field_value` | `TEXT` | nullable | Extracted value as string |
| `confidence` | `FLOAT` | nullable, check `[0.0, 1.0]`, partial index when `< 0.8` | Per-field confidence score |
| `source_page` | `INTEGER` | nullable | Source PDF page number |
| `source_bounding_box` | `JSONB` | nullable, GIN indexed | Bounding box coordinates |
| `source_text` | `TEXT` | nullable | Raw OCR text for this field |
| `validation_status` | `TEXT` | nullable | Validation result: `valid`, `invalid`, `uncertain` |
| `validation_message` | `TEXT` | nullable | Validation error or warning message |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |

**Indexes:**
- `idx_extraction_fields_document_id` — B-tree on `document_id`
- `idx_extraction_fields_field_name` — B-tree on `field_name`
- `idx_extraction_fields_confidence` — Partial B-tree on `confidence` where `confidence < 0.8`
- `idx_extraction_fields_source_bounding_box` — GIN on `source_bounding_box`

---

## Validation Tables

### `cross_document_validations`

Records results of cross-document consistency checks (identity, name, income, address comparisons).

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `applicant_id` | `UUID` | NOT NULL, indexed | Applicant under validation |
| `validation_type` | `VARCHAR(50)` | NOT NULL, indexed | Values: `identity`, `name`, `income`, `address`, `employment`, `comprehensive` |
| `source_documents` | `UUID[]` (ARRAY) | NOT NULL | Array of document IDs compared |
| `source_document_types` | `TEXT[]` (ARRAY) | nullable | Document types involved |
| `status` | `VARCHAR(30)` | NOT NULL, partial index when `!= 'passed'` | Values: `pending`, `passed`, `warnings`, `discrepancies_found`, `failed` |
| `confidence_score` | `FLOAT` | nullable, check `[0.0, 1.0]` | Overall confidence in cross-document consistency |
| `findings` | `JSONB` | NOT NULL, GIN indexed | Structured findings: `{identity_match: true, name_similarity: 0.95, ...}` |
| `discrepancies` | `JSONB` | nullable, GIN indexed | Detected discrepancies with severity levels |
| `is_resolved` | `BOOLEAN` | NOT NULL, default `false` | Whether discrepancies were resolved |
| `resolution_notes` | `TEXT` | nullable | Notes from resolution process |
| `resolved_by` | `TEXT` | nullable | Who resolved the discrepancy |
| `resolved_at` | `TIMESTAMPTZ` | nullable | Resolution timestamp |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_cross_val_applicant_id` — B-tree on `(applicant_id, validation_type)`
- `idx_cross_val_status` — Partial B-tree on `status` where `status != 'passed'`
- `idx_cross_val_findings` — GIN on `findings`
- `idx_cross_val_discrepancies` — GIN on `discrepancies`

---

## Infrastructure Tables

### `document_audit_log`

Immutable audit trail for all document lifecycle events. Each row is hash-chained to the previous row for tamper evidence.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), NOT NULL, indexed | Document being audited |
| `action` | `TEXT` | NOT NULL, indexed | Action taken: `uploaded`, `classified`, `extracted`, `validated`, `archived`, `deleted`, `reprocessed` |
| `performed_by` | `TEXT` | NOT NULL, indexed | Actor identifier (user email, agent name, or `system`) |
| `performed_by_type` | `TEXT` | NOT NULL, check `IN ('user', 'system', 'agent')` | Actor type |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL, default `now()`, indexed DESC | When the action occurred |
| `changes` | `JSONB` | nullable, GIN indexed | Summary of changes made |
| `previous_values` | `JSONB` | nullable, GIN indexed | Values before change |
| `new_values` | `JSONB` | nullable, GIN indexed | Values after change |
| `ip_address` | `INET` | nullable | IP address of the actor |
| `user_agent` | `TEXT` | nullable | Browser/client user agent string |
| `session_id` | `UUID` | nullable | Session identifier for user actions |
| `hash` | `TEXT` | NOT NULL | SHA-256 of this row's content |
| `previous_hash` | `TEXT` | nullable | Hash of previous audit row (chain linkage) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Row creation timestamp |

**Indexes:**
- `idx_audit_document_id` — B-tree on `(document_id, timestamp DESC)`
- `idx_audit_action` — B-tree on `(action, timestamp DESC)`
- `idx_audit_performed_by` — B-tree on `(performed_by, timestamp DESC)`
- `idx_audit_changes` — GIN on `changes`
- `idx_audit_previous_values` — GIN on `previous_values`
- `idx_audit_new_values` — GIN on `new_values`

---

### `document_processing_queue`

Work queue for asynchronous document processing. Supports retry logic and priority scheduling.

| Column | Type | Constraints | Business Rules |
|--------|------|-------------|----------------|
| `id` | `UUID` | PK, default `uuid4()` | System-generated surrogate key |
| `document_id` | `UUID` | FK → `documents.id` (CASCADE), NOT NULL, indexed | Document to process |
| `stage` | `TEXT` | NOT NULL, indexed | Processing stage: `classify`, `extract`, `validate`, `embed` |
| `status` | `TEXT` | NOT NULL, default `'pending'`, indexed | Values: `pending`, `processing`, `completed`, `failed`, `retry` |
| `priority` | `INTEGER` | NOT NULL, default `0`, indexed DESC | Higher values processed first |
| `retry_count` | `INTEGER` | NOT NULL, default `0` | Number of retry attempts |
| `max_retries` | `INTEGER` | NOT NULL, default `3` | Maximum retry attempts |
| `error_message` | `TEXT` | nullable | Last error message if failed |
| `started_at` | `TIMESTAMPTZ` | nullable | Processing start timestamp |
| `completed_at` | `TIMESTAMPTZ` | nullable | Processing completion timestamp |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, indexed | Queue entry creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update `now()` | Last modification timestamp |

**Indexes:**
- `idx_queue_stage_status` — B-tree on `(stage, status)`
- `idx_queue_priority` — B-tree on `(priority DESC, created_at)`
- `idx_queue_document_id` — B-tree on `document_id`

---

## Cross-Cutting Concerns

### Audit Trail

Every document action is recorded in `document_audit_log` with hash chaining (`hash` / `previous_hash`). This provides tamper-evident logging — modifying any historical row breaks the chain. The `performed_by_type` check constraint ensures only `user`, `system`, or `agent` values.

### Soft Deletes

The schema does not use soft deletes. Instead, documents use a `processing_status` of `archived` to mark logically deleted records. The `documents` table and all child tables use `ON DELETE CASCADE` foreign keys, so archiving a document removes all associated extraction data, audit logs, and queue entries.

### Timestamps

All tables follow a consistent timestamp convention:
- `created_at` — `TIMESTAMPTZ`, NOT NULL, `server_default=now()`, never updated
- `updated_at` — `TIMESTAMPTZ`, NOT NULL, `server_default=now()`, `onupdate=now()`

### Confidence Scores

All confidence fields (`extraction_confidence`, `overall_confidence`, `confidence_score`, `confidence`) are constrained to the range `[0.0, 1.0]` via `CHECK` constraints and are nullable to indicate "not yet computed."

### JSONB Usage

JSONB columns are used for:
- Semi-structured extracted data (`raw_extracted_data`, `validation_results`, `transactions`)
- Flexible metadata (`metadata`, `address`, `contact_details`, `employment_info`)
- Denormalized lists for query performance (`active_facilities`, `work_experience`, `skills`)

All frequently queried JSONB columns have GIN indexes.

---

## Migration History

| Migration ID | Name | Description |
|--------------|------|-------------|
| `20260725001` | `add_document_processing_schema` | Initial schema — creates all 16 tables with indexes, constraints, and relationships |
| `20260726001` | `add_state_snapshot` | Adds `state_snapshot` JSONB column to `applications` for LangGraph state persistence |
| `20260727001` | `add_validation_confidence` | Adds `validation_confidence` FLOAT column to `applications` to track validation agent confidence |
| `20260727002` | `add_checkpoint_created_at` | Adds `created_at` TIMESTAMPTZ column to LangGraph checkpoints table for TTL cleanup support |

Migration files are located in `alembic/versions/`.

---

## ORM Models

SQLAlchemy ORM models are located in `src/infrastructure/db/models/`:

| Model | File | Table |
|-------|------|-------|
| `Applicant` | `applicant.py` | `applicants` |
| `Application` | `application.py` | `applications` |
| `Document` | `document.py` | `documents` |
| `EmiratesIDData` | `extraction.py` | `emirates_id_data` |
| `BankStatementData` | `extraction.py` | `bank_statement_data` |
| `BankStatementTransaction` | `extraction.py` | `bank_statement_transactions` |
| `CreditReportData` | `extraction.py` | `credit_report_data` |
| `CreditFacility` | `extraction.py` | `credit_facilities` |
| `ResumeData` | `extraction.py` | `resume_data` |
| `ResumeWorkExperience` | `extraction.py` | `resume_work_experience` |
| `AssetsLiabilitiesData` | `extraction.py` | `assets_liabilities_data` |
| `ApplicationFormData` | `extraction.py` | `application_form_data` |
| `DocumentExtractionField` | `extraction.py` | `document_extraction_fields` |
| `CrossDocumentValidation` | `validation.py` | `cross_document_validations` |
| `AuditLog` | `audit.py` | `document_audit_log` |
| `ProcessingQueue` | `audit.py` | `document_processing_queue` |

All models are exported from `src/infrastructure/db/models/__init__.py`.
