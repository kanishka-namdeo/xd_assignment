# Document Processing Schema Specification

**Date:** 2026-07-25  
**Version:** 1.0  
**Status:** Draft

## Overview

This document specifies the database schemas for processing six document types in the UAE Social Support Application system. Each schema includes field definitions, data types, constraints, and validation rules.

## Base Documents Schema

### Table: `documents`

Stores common metadata for all document types.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique document identifier |
| applicant_id | UUID | NOT NULL | Reference to applicant |
| document_type | VARCHAR(50) | NOT NULL, CHECK IN ('emirates_id', 'bank_statement', 'credit_report', 'resume', 'assets_liabilities', 'application_form') | Document type classification |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'uploaded' | Processing status: uploaded, processing, extracted, validated, failed, archived |
| file_path | TEXT | NOT NULL | Object storage path (S3) |
| file_format | VARCHAR(10) | | File format: pdf, xlsx, jpg, png, docx |
| file_size_bytes | BIGINT | | File size in bytes |
| file_hash | VARCHAR(64) | NOT NULL | SHA-256 hash for integrity verification |
| upload_timestamp | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Upload timestamp |
| processing_started_at | TIMESTAMPTZ | | Processing start time |
| processing_completed_at | TIMESTAMPTZ | | Processing completion time |
| extraction_status | VARCHAR(20) | DEFAULT 'pending' | Extraction status: pending, success, partial, failed |
| validation_status | VARCHAR(20) | DEFAULT 'pending' | Validation status: pending, valid, invalid, warnings |
| confidence_score | FLOAT | CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0) | Overall extraction confidence |
| metadata | JSONB | | Document-type-specific metadata |
| error_log | TEXT | | Error messages if processing failed |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_documents_applicant` ON documents(applicant_id, document_type)
- `idx_documents_status` ON documents(status, upload_timestamp DESC)
- `idx_documents_extraction` ON documents(extraction_status) WHERE extraction_status != 'success'

---

## Document Type Schemas

### Schema: `emirates_id_data`

Extracted fields from UAE Emirates ID (ICP V2 chip specification).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to base document |
| identity_number | VARCHAR(15) | NOT NULL, UNIQUE | 15-digit ID: 784-YYYY-XXXXXXX-X |
| full_name_en | VARCHAR(200) | NOT NULL | Full name in English |
| full_name_ar | VARCHAR(200) | | Full name in Arabic |
| nationality | VARCHAR(100) | NOT NULL | Country of citizenship |
| date_of_birth | DATE | NOT NULL | Date of birth |
| gender | VARCHAR(10) | NOT NULL, CHECK IN ('Male', 'Female') | Gender |
| card_number | VARCHAR(50) | | Physical card serial number |
| issue_date | DATE | | Card issue date |
| expiry_date | DATE | NOT NULL | Card expiry date |
| mrz_verified | BOOLEAN | DEFAULT FALSE | MRZ zone checksum verification |
| address | JSONB | | Address: {emirate, city, po_box, phone, email} |
| occupation | VARCHAR(200) | | Occupation (post-2022 cards) |
| employer_name | VARCHAR(200) | | Employer name (post-2022 cards) |
| marital_status | VARCHAR(20) | | Marital status code |
| mother_name | VARCHAR(200) | | Mother's full name |
| sponsor_name | VARCHAR(200) | | Sponsor name |
| sponsor_type | VARCHAR(50) | | Sponsor type code |
| residency_type | VARCHAR(50) | | Residency visa type |
| residency_number | VARCHAR(50) | | Residency number |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_emirates_id_number` ON emirates_id_data(identity_number)
- `idx_emirates_id_expiry` ON emirates_id_data(expiry_date)
- `idx_emirates_id_nationality` ON emirates_id_data(nationality)

**Validation Rules:**
- Identity number checksum verification (format: 784-YYYY-XXXXXXX-X)
- Expiry date must be >= current date
- MRZ zone must be present and verified
- Name consistency with other documents

---

### Schema: `bank_statement_data`

Extracted summary from bank statements.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to base document |
| bank_name | VARCHAR(100) | NOT NULL | Bank name (Emirates NBD, FAB, ADCB, etc.) |
| account_holder_name | VARCHAR(200) | NOT NULL | Account holder name |
| account_number | VARCHAR(50) | NOT NULL | Account number (masked for security) |
| iban | VARCHAR(50) | | International Bank Account Number |
| account_type | VARCHAR(50) | | Account type: Checking, Savings, Credit Card |
| currency | VARCHAR(3) | NOT NULL, DEFAULT 'AED' | ISO 4217 currency code |
| statement_period_start | DATE | NOT NULL | Statement start date |
| statement_period_end | DATE | NOT NULL | Statement end date |
| opening_balance | DECIMAL(15,2) | NOT NULL | Opening balance |
| closing_balance | DECIMAL(15,2) | NOT NULL | Closing balance |
| total_debits | DECIMAL(15,2) | NOT NULL | Total debits for period |
| total_credits | DECIMAL(15,2) | NOT NULL | Total credits for period |
| balance_reconciled | BOOLEAN | DEFAULT FALSE | opening + credits - debits = closing |
| transactions | JSONB | NOT NULL | Array of transaction objects |
| transaction_count | INTEGER | NOT NULL | Number of transactions |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_bank_stmt_account` ON bank_statement_data(account_number)
- `idx_bank_stmt_period` ON bank_statement_data(statement_period_start, statement_period_end)

**Validation Rules:**
- Balance reconciliation: opening_balance + total_credits - total_debits = closing_balance
- Statement period: start < end
- No future transaction dates
- Currency consistency (AED primary)

---

### Schema: `bank_statement_transactions`

Normalized transaction records from bank statements.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| transaction_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique transaction identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → bank_statement_data(document_id) ON DELETE CASCADE | Reference to bank statement |
| transaction_hash | VARCHAR(64) | NOT NULL, UNIQUE | MD5(date + amount + description + currency) for dedup |
| transaction_date | DATE | NOT NULL | Transaction date |
| description | TEXT | NOT NULL | Transaction description/narration |
| amount | DECIMAL(15,2) | NOT NULL | Signed amount: negative=debit, positive=credit |
| transaction_type | VARCHAR(20) | NOT NULL, CHECK IN ('debit', 'credit') | Transaction type |
| running_balance | DECIMAL(15,2) | | Running balance after transaction |
| category | VARCHAR(50) | | Category: salary, utility, transfer, etc. |
| counterparty | VARCHAR(200) | | Debtor or creditor name |
| reference_number | VARCHAR(100) | | Transaction reference number |
| is_wps_salary | BOOLEAN | DEFAULT FALSE | Wage Protection System salary flag |
| channel | VARCHAR(20) | | Channel: POS, ATM, IB, TRF, SWIFT |
| source_page | INTEGER | | Page number in source document |
| source_bounding_box | JSONB | | Bounding box coordinates |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_bank_txn_document` ON bank_statement_transactions(document_id)
- `idx_bank_txn_date` ON bank_statement_transactions(transaction_date)
- `idx_bank_txn_category` ON bank_statement_transactions(category)
- `idx_bank_txn_wps` ON bank_statement_transactions(is_wps_salary) WHERE is_wps_salary = TRUE

---

### Schema: `credit_report_data`

Extracted data from AECB credit reports.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to base document |
| cb_subject_id | VARCHAR(50) | NOT NULL | AECB subject ID |
| identity_number | VARCHAR(15) | NOT NULL | Emirates ID number |
| full_name | VARCHAR(200) | NOT NULL | Full name |
| contact_details | JSONB | | {phone, email, address} |
| employment_info | JSONB | | {employer, occupation, salary} |
| credit_score | INTEGER | NOT NULL, CHECK (credit_score >= 300 AND credit_score <= 900) | Credit score (300-900) |
| risk_band | VARCHAR(20) | NOT NULL | Risk band: Excellent, Very Good, Good, Fair, Poor |
| score_calculation_date | DATE | | Score calculation date |
| total_active_accounts | INTEGER | NOT NULL | Number of active credit accounts |
| total_closed_accounts | INTEGER | NOT NULL | Number of closed credit accounts |
| total_outstanding_balance | DECIMAL(15,2) | NOT NULL | Total outstanding balance |
| total_credit_limit | DECIMAL(15,2) | | Total credit limit |
| credit_utilization_ratio | DECIMAL(5,2) | | Credit utilization percentage |
| active_facilities | JSONB | | Array of active credit facilities |
| closed_facilities | JSONB | | Array of closed credit facilities |
| payment_history | JSONB | | 24-36 months of payment data |
| late_payment_count | INTEGER | DEFAULT 0 | Number of late payments |
| defaulted_accounts | INTEGER | DEFAULT 0 | Number of defaulted accounts |
| bounced_cheques | INTEGER | DEFAULT 0 | Number of bounced cheques |
| court_judgments | INTEGER | DEFAULT 0 | Number of court judgments |
| bankruptcy_records | BOOLEAN | DEFAULT FALSE | Bankruptcy flag |
| inquiry_count | INTEGER | DEFAULT 0 | Number of credit inquiries |
| inquiries | JSONB | | Array of inquiry records |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_credit_report_score` ON credit_report_data(credit_score)
- `idx_credit_report_identity` ON credit_report_data(identity_number)

**Validation Rules:**
- Credit score range: 300-900
- Identity number must match Emirates ID document
- Total outstanding must equal sum of facility balances
- Payment history timeline consistency

---

### Schema: `credit_facilities`

Detailed credit facility records from credit reports.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| facility_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique facility identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → credit_report_data(document_id) ON DELETE CASCADE | Reference to credit report |
| facility_type | VARCHAR(50) | NOT NULL | Type: credit_card, personal_loan, mortgage, auto_loan, overdraft |
| lender_name | VARCHAR(200) | NOT NULL | Lender/bank name |
| account_number | VARCHAR(50) | | Account number |
| status | VARCHAR(20) | NOT NULL | Status: active, closed, defaulted |
| opened_date | DATE | | Account opening date |
| closed_date | DATE | | Account closing date |
| credit_limit | DECIMAL(15,2) | | Credit limit |
| current_balance | DECIMAL(15,2) | NOT NULL | Current outstanding balance |
| monthly_payment | DECIMAL(15,2) | | Monthly payment amount |
| payment_status | VARCHAR(20) | | Payment status: current, 30_days_late, 60_days_late, 90_days_late, defaulted |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_credit_facilities_document` ON credit_facilities(document_id)
- `idx_credit_facilities_status` ON credit_facilities(status)

---

### Schema: `resume_data`

Extracted data from resumes/CVs.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to base document |
| full_name | VARCHAR(200) | NOT NULL | Full name |
| email | VARCHAR(200) | | Email address |
| phone | VARCHAR(50) | | Phone number |
| location | VARCHAR(200) | | Location/city |
| summary | TEXT | | Professional summary |
| years_of_experience | INTEGER | | Total years of experience |
| work_experience | JSONB | NOT NULL | Array of work experience objects |
| total_positions | INTEGER | NOT NULL | Total number of positions |
| current_employer | VARCHAR(200) | | Current employer name |
| current_job_title | VARCHAR(200) | | Current job title |
| education | JSONB | | Array of education records |
| highest_degree | VARCHAR(100) | | Highest degree obtained |
| skills | JSONB | | Array of skills |
| skill_count | INTEGER | DEFAULT 0 | Number of skills |
| certifications | JSONB | | Array of certifications |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_resume_name` ON resume_data(full_name)
- `idx_resume_email` ON resume_data(email)

**Validation Rules:**
- Date consistency: start_date < end_date
- No future dates
- Current employment: end_date = null or "Present"
- Contact information format validation

---

### Schema: `resume_work_experience`

Detailed work experience records from resumes.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| experience_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique experience identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → resume_data(document_id) ON DELETE CASCADE | Reference to resume |
| job_title | VARCHAR(200) | NOT NULL | Job title |
| company | VARCHAR(200) | NOT NULL | Company name |
| location | VARCHAR(200) | | Job location |
| start_date | DATE | NOT NULL | Start date |
| end_date | DATE | | End date (null = current) |
| is_current | BOOLEAN | DEFAULT FALSE | Current employment flag |
| description | TEXT | | Job description |
| achievements | TEXT[] | | Array of achievement bullets |
| duration_months | INTEGER | | Calculated duration in months |
| industry | VARCHAR(100) | | Industry sector |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_resume_work_exp` ON resume_work_experience(document_id)
- `idx_resume_current_employer` ON resume_work_experience(company) WHERE is_current = TRUE

---

### Schema: `assets_liabilities_data`

Extracted data from assets and liabilities statements.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to base document |
| applicant_name | VARCHAR(200) | NOT NULL | Applicant name |
| statement_date | DATE | NOT NULL | Statement date |
| cash_and_deposits | DECIMAL(15,2) | DEFAULT 0 | Cash and bank deposits |
| savings_accounts | DECIMAL(15,2) | DEFAULT 0 | Savings account balances |
| investment_accounts | DECIMAL(15,2) | DEFAULT 0 | Investment account values |
| retirement_accounts | DECIMAL(15,2) | DEFAULT 0 | Retirement account values |
| real_estate_value | DECIMAL(15,2) | DEFAULT 0 | Real estate market value |
| vehicle_value | DECIMAL(15,2) | DEFAULT 0 | Vehicle market value |
| other_assets | DECIMAL(15,2) | DEFAULT 0 | Other asset values |
| total_assets | DECIMAL(15,2) | NOT NULL | Sum of all assets |
| mortgage_balance | DECIMAL(15,2) | DEFAULT 0 | Mortgage outstanding balance |
| personal_loans | DECIMAL(15,2) | DEFAULT 0 | Personal loan balances |
| credit_card_debt | DECIMAL(15,2) | DEFAULT 0 | Credit card balances |
| student_loans | DECIMAL(15,2) | DEFAULT 0 | Student loan balances |
| other_liabilities | DECIMAL(15,2) | DEFAULT 0 | Other liability balances |
| total_liabilities | DECIMAL(15,2) | NOT NULL | Sum of all liabilities |
| net_worth | DECIMAL(15,2) | NOT NULL | total_assets - total_liabilities |
| monthly_income | DECIMAL(15,2) | | Monthly income (if included) |
| income_sources | JSONB | | Array of income sources |
| asset_details | JSONB | | Detailed asset records |
| liability_details | JSONB | | Detailed liability records |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_assets_liabilities_net_worth` ON assets_liabilities_data(net_worth)
- `idx_assets_liabilities_date` ON assets_liabilities_data(statement_date)

**Validation Rules:**
- net_worth = total_assets - total_liabilities
- All values >= 0
- Statement date within last 6 months
- Asset categories sum to total_assets

---

### Schema: `application_form_data`

Structured data from application forms.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| document_id | UUID | PRIMARY KEY, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to base document |
| applicant_name | VARCHAR(200) | NOT NULL | Applicant name |
| identity_number | VARCHAR(15) | NOT NULL | Emirates ID number |
| date_of_birth | DATE | NOT NULL | Date of birth |
| nationality | VARCHAR(100) | NOT NULL | Nationality |
| contact_phone | VARCHAR(50) | NOT NULL | Contact phone number |
| contact_email | VARCHAR(200) | | Contact email |
| address | JSONB | NOT NULL | Address: {emirate, city, street, po_box} |
| marital_status | VARCHAR(20) | | Marital status |
| family_size | INTEGER | | Family size |
| dependents | JSONB | | Array of dependent records |
| employment_status | VARCHAR(50) | NOT NULL | Status: employed, self_employed, unemployed, retired |
| employer_name | VARCHAR(200) | | Employer name |
| occupation | VARCHAR(200) | | Occupation |
| monthly_salary | DECIMAL(15,2) | | Monthly salary |
| other_income | DECIMAL(15,2) | DEFAULT 0 | Other income sources |
| total_monthly_income | DECIMAL(15,2) | NOT NULL | Total monthly income |
| housing_status | VARCHAR(50) | | Status: owned, rented, family_provided |
| monthly_rent | DECIMAL(15,2) | | Monthly rent |
| monthly_mortgage | DECIMAL(15,2) | | Monthly mortgage |
| support_category | VARCHAR(100) | | Category: divorced, abandoned, unknown_parentage, health_disability |
| supporting_documents | JSONB | | Array of supporting document references |
| declaration_signed | BOOLEAN | DEFAULT FALSE | Declaration signed flag |
| declaration_date | DATE | | Declaration date |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_application_identity` ON application_form_data(identity_number)
- `idx_application_income` ON application_form_data(total_monthly_income)
- `idx_application_category` ON application_form_data(support_category)

**Validation Rules:**
- Emirates ID must match uploaded Emirates ID document
- Income consistency with bank statements
- Support category must have corresponding documents
- All required fields present

## Cross-Document Validation Schema

### Schema: `cross_document_validations`

Stores results of consistency checks across multiple documents.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| validation_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique validation identifier |
| applicant_id | UUID | NOT NULL | Reference to applicant |
| validation_type | VARCHAR(100) | NOT NULL | Type: income_consistency, identity_match, address_match |
| source_documents | UUID[] | NOT NULL | Array of document_ids involved |
| source_document_types | VARCHAR(50)[] | | Array of document types |
| status | VARCHAR(20) | NOT NULL | Status: passed, failed, warning, manual_review |
| confidence_score | FLOAT | CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0) | Validation confidence |
| findings | JSONB | NOT NULL | Detailed validation findings |
| discrepancies | JSONB | | Array of discrepancies found |
| resolved | BOOLEAN | DEFAULT FALSE | Resolution status |
| resolution_notes | TEXT | | Resolution notes |
| resolved_by | VARCHAR(100) | | User who resolved |
| resolved_at | TIMESTAMPTZ | | Resolution timestamp |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_cross_val_applicant` ON cross_document_validations(applicant_id, validation_type)
- `idx_cross_val_status` ON cross_document_validations(status) WHERE status != 'passed'

**Validation Types:**
- `identity_match`: Emirates ID number matches across all documents
- `name_match`: Name variations are reconcilable
- `dob_match`: Date of birth is consistent
- `income_consistency`: Bank statement salary aligns with application form income
- `debt_consistency`: Credit report balances align with assets/liabilities
- `employment_match`: Resume employment aligns with application form
- `address_match`: Addresses are consistent across documents

---

## Audit Trail Schema

### Schema: `document_audit_log`

Tamper-evident audit trail for all document lifecycle events.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| audit_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique audit identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to document |
| action | VARCHAR(50) | NOT NULL | Action: uploaded, extracted, validated, modified, deleted, accessed |
| performed_by | VARCHAR(100) | NOT NULL | User ID or system identifier |
| performed_by_type | VARCHAR(20) | NOT NULL, CHECK IN ('user', 'system', 'agent') | Actor type |
| timestamp | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Action timestamp |
| changes | JSONB | | Field-level diffs |
| previous_values | JSONB | | Previous field values |
| new_values | JSONB | | New field values |
| ip_address | INET | | Client IP address |
| user_agent | TEXT | | Client user agent |
| session_id | UUID | | Session identifier |
| hash | VARCHAR(64) | NOT NULL | SHA-256 hash of this record + previous hash |
| previous_hash | VARCHAR(64) | | Hash of previous audit record (chain) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_audit_document` ON document_audit_log(document_id, timestamp DESC)
- `idx_audit_action` ON document_audit_log(action, timestamp DESC)
- `idx_audit_performed_by` ON document_audit_log(performed_by, timestamp DESC)

**Hash Chain Logic:**
```
hash = SHA256(audit_id || document_id || action || performed_by || timestamp || changes || previous_hash)
```

---

## Supporting Schemas

### Schema: `document_processing_queue`

Tracks documents in the processing pipeline.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| queue_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique queue entry identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to document |
| stage | VARCHAR(50) | NOT NULL | Pipeline stage: ingestion, classification, extraction, validation, integration |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | Status: pending, processing, completed, failed |
| priority | INTEGER | DEFAULT 0 | Processing priority (higher = more urgent) |
| retry_count | INTEGER | DEFAULT 0 | Number of retry attempts |
| max_retries | INTEGER | DEFAULT 3 | Maximum retry attempts |
| error_message | TEXT | | Error message if failed |
| started_at | TIMESTAMPTZ | | Processing start time |
| completed_at | TIMESTAMPTZ | | Processing completion time |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_queue_stage_status` ON document_processing_queue(stage, status)
- `idx_queue_priority` ON document_processing_queue(priority DESC, created_at)

---

### Schema: `document_extraction_fields`

Stores individual extracted fields with provenance.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| field_id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique field identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(document_id) ON DELETE CASCADE | Reference to document |
| field_name | VARCHAR(100) | NOT NULL | Field name (e.g., identity_number, opening_balance) |
| field_value | TEXT | | Extracted value |
| confidence | FLOAT | CHECK (confidence >= 0.0 AND confidence <= 1.0) | Field-level confidence |
| source_page | INTEGER | | Page number in source document |
| source_bounding_box | JSONB | | Bounding box: {x, y, width, height} |
| source_text | TEXT | | Raw text from source |
| validation_status | VARCHAR(20) | | Status: valid, invalid, warning, unchecked |
| validation_message | TEXT | | Validation message |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_extraction_fields_document` ON document_extraction_fields(document_id)
- `idx_extraction_fields_confidence` ON document_extraction_fields(confidence) WHERE confidence < 0.8

---

## Schema Relationships

```
documents (1) ←→ (1) emirates_id_data
documents (1) ←→ (1) bank_statement_data
documents (1) ←→ (0..*) bank_statement_transactions
documents (1) ←→ (1) credit_report_data
documents (1) ←→ (0..*) credit_facilities
documents (1) ←→ (1) resume_data
documents (1) ←→ (0..*) resume_work_experience
documents (1) ←→ (1) assets_liabilities_data
documents (1) ←→ (1) application_form_data
documents (1) ←→ (0..*) document_audit_log
documents (1) ←→ (0..*) document_extraction_fields
documents (1) ←→ (0..*) document_processing_queue
applicant (1) ←→ (0..*) documents
applicant (1) ←→ (0..*) cross_document_validations
```

---

## Data Types Reference

| Type | Usage |
|------|-------|
| UUID | Universally unique identifier |
| VARCHAR(n) | Variable-length string with max length n |
| TEXT | Variable-length string, unlimited |
| INTEGER | 32-bit integer |
| BIGINT | 64-bit integer |
| DECIMAL(p,s) | Fixed-point number with precision p and scale s |
| FLOAT | Double-precision floating-point |
| BOOLEAN | True/false |
| DATE | Calendar date |
| TIMESTAMPTZ | Timestamp with time zone |
| JSONB | Binary JSON, indexed and queryable |
| TEXT[] | Array of text |
| UUID[] | Array of UUIDs |
| VARCHAR(n)[] | Array of variable-length strings |
| INET | IP address |

---

## Enumerations

### document_type
- `emirates_id`
- `bank_statement`
- `credit_report`
- `resume`
- `assets_liabilities`
- `application_form`

### status (documents)
- `uploaded` - Document uploaded, not yet processed
- `processing` - Currently being processed
- `extracted` - Extraction complete, pending validation
- `validated` - Validation complete
- `failed` - Processing or validation failed
- `archived` - Document archived

### extraction_status
- `pending` - Extraction not started
- `success` - Extraction successful
- `partial` - Some fields extracted, others failed
- `failed` - Extraction failed

### validation_status
- `pending` - Validation not started
- `valid` - All validations passed
- `invalid` - Validation failed
- `warnings` - Validation passed with warnings

### confidence routing
- `> 0.95` - Auto-approve
- `0.80 - 0.95` - Spot-check review
- `< 0.80` - Human review required
