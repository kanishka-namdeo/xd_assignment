# Document Processing Schema Specification

**Date:** 2026-07-25  
**Version:** 1.1  
**Status:** Draft

## Overview

This document specifies the PostgreSQL database schemas for processing six document types in the UAE Social Support Application system. The schemas integrate with the tech stack defined in `2026-07-25-tech-stack-design.md`:

- **PostgreSQL 17** with SQLAlchemy 2.0 + asyncpg for relational data
- **Neo4j 2026.06.0** for document lineage and family relationships
- **Qdrant v1.18.3** for document embeddings
- **LangGraph 1.2.9** for agent orchestration
- **Langfuse v4** for observability

Schema design follows PostgreSQL best practices: snake_case naming, plural table names, singular columns, TEXT over VARCHAR, TIMESTAMPTZ for timestamps, and UUIDv7 for primary keys.

## Base Documents Schema

### Table: `documents`

Stores common metadata for all document types. This is the central table that links to specialized extraction tables.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique document identifier (UUIDv7 for time-ordering) |
| applicant_id | UUID | NOT NULL | Reference to applicant (stored in Neo4j for relationship modeling) |
| document_type | TEXT | NOT NULL, CHECK (document_type IN ('emirates_id', 'bank_statement', 'credit_report', 'resume', 'assets_liabilities', 'application_form')) | Document type classification |
| processing_status | TEXT | NOT NULL, DEFAULT 'uploaded' | Pipeline status: uploaded, classifying, extracting, validating, completed, failed, archived |
| file_path | TEXT | NOT NULL | Object storage path (S3/MinIO) |
| file_format | TEXT | | File format: pdf, xlsx, jpg, png, docx |
| file_size_bytes | BIGINT | | File size in bytes |
| file_hash | TEXT | NOT NULL | SHA-256 hash for integrity verification |
| uploaded_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Upload timestamp |
| processing_started_at | TIMESTAMPTZ | | Processing start time |
| processing_completed_at | TIMESTAMPTZ | | Processing completion time |
| extraction_status | TEXT | DEFAULT 'pending' | Extraction status: pending, success, partial, failed |
| validation_status | TEXT | DEFAULT 'pending' | Validation status: pending, valid, invalid, warnings |
| overall_confidence | FLOAT | CHECK (overall_confidence >= 0.0 AND overall_confidence <= 1.0) | Overall extraction confidence score |
| metadata | JSONB | | Document-type-specific metadata |
| error_log | TEXT | | Error messages if processing failed |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_documents_applicant_id` ON documents(applicant_id, document_type)
- `idx_documents_processing_status` ON documents(processing_status, uploaded_at DESC)
- `idx_documents_extraction_status` ON documents(extraction_status) WHERE extraction_status != 'success'
- `idx_documents_metadata` ON documents USING GIN (metadata)

**Notes:**
- Uses UUIDv7 for time-ordered primary keys (PostgreSQL 17+ native support)
- TEXT preferred over VARCHAR (PostgreSQL stores identically, no performance difference)
- applicant_id references Neo4j node (document lineage and relationship modeling)
- GIN index on JSONB metadata for flexible querying

---

## Document Type Schemas

### Schema: `emirates_id_data`

Extracted fields from UAE Emirates ID (ICP V2 chip specification).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique record identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to base document |
| identity_number | TEXT | NOT NULL, UNIQUE | 15-digit ID: 784-YYYY-XXXXXXX-X |
| full_name_en | TEXT | NOT NULL | Full name in English |
| full_name_ar | TEXT | | Full name in Arabic |
| nationality | TEXT | NOT NULL | Country of citizenship |
| date_of_birth | DATE | NOT NULL | Date of birth |
| gender | TEXT | NOT NULL, CHECK (gender IN ('Male', 'Female')) | Gender |
| card_number | TEXT | | Physical card serial number |
| issue_date | DATE | | Card issue date |
| expiry_date | DATE | NOT NULL | Card expiry date |
| is_mrz_verified | BOOLEAN | DEFAULT FALSE | MRZ zone checksum verification |
| address | JSONB | | Address: {emirate, city, po_box, phone, email} |
| occupation | TEXT | | Occupation (post-2022 cards) |
| employer_name | TEXT | | Employer name (post-2022 cards) |
| marital_status | TEXT | | Marital status code |
| mother_name | TEXT | | Mother's full name |
| sponsor_name | TEXT | | Sponsor name |
| sponsor_type | TEXT | | Sponsor type code |
| residency_type | TEXT | | Residency visa type |
| residency_number | TEXT | | Residency number |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_emirates_id_identity_number` ON emirates_id_data(identity_number)
- `idx_emirates_id_expiry_date` ON emirates_id_data(expiry_date)
- `idx_emirates_id_nationality` ON emirates_id_data(nationality)
- `idx_emirates_id_address` ON emirates_id_data USING GIN (address)

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
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique record identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to base document |
| bank_name | TEXT | NOT NULL | Bank name (Emirates NBD, FAB, ADCB, etc.) |
| account_holder_name | TEXT | NOT NULL | Account holder name |
| account_number | TEXT | NOT NULL | Account number (masked for security) |
| iban | TEXT | | International Bank Account Number |
| account_type | TEXT | | Account type: Checking, Savings, Credit Card |
| currency | TEXT | NOT NULL, DEFAULT 'AED' | ISO 4217 currency code |
| statement_period_start | DATE | NOT NULL | Statement start date |
| statement_period_end | DATE | NOT NULL | Statement end date |
| opening_balance | DECIMAL(15,2) | NOT NULL | Opening balance |
| closing_balance | DECIMAL(15,2) | NOT NULL | Closing balance |
| total_debits | DECIMAL(15,2) | NOT NULL | Total debits for period |
| total_credits | DECIMAL(15,2) | NOT NULL | Total credits for period |
| is_balance_reconciled | BOOLEAN | DEFAULT FALSE | opening + credits - debits = closing |
| transactions | JSONB | NOT NULL | Array of transaction objects |
| transaction_count | INTEGER | NOT NULL | Number of transactions |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_bank_stmt_document_id` ON bank_statement_data(document_id)
- `idx_bank_stmt_account_number` ON bank_statement_data(account_number)
- `idx_bank_stmt_period` ON bank_statement_data(statement_period_start, statement_period_end)
- `idx_bank_stmt_transactions` ON bank_statement_data USING GIN (transactions)

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
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique transaction identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → bank_statement_data(id) ON DELETE CASCADE | Reference to bank statement |
| transaction_hash | TEXT | NOT NULL, UNIQUE | MD5(date + amount + description + currency) for dedup |
| transaction_date | DATE | NOT NULL | Transaction date |
| description | TEXT | NOT NULL | Transaction description/narration |
| amount | DECIMAL(15,2) | NOT NULL | Signed amount: negative=debit, positive=credit |
| transaction_type | TEXT | NOT NULL, CHECK (transaction_type IN ('debit', 'credit')) | Transaction type |
| running_balance | DECIMAL(15,2) | | Running balance after transaction |
| category | TEXT | | Category: salary, utility, transfer, etc. |
| counterparty | TEXT | | Debtor or creditor name |
| reference_number | TEXT | | Transaction reference number |
| is_wps_salary | BOOLEAN | DEFAULT FALSE | Wage Protection System salary flag |
| channel | TEXT | | Channel: POS, ATM, IB, TRF, SWIFT |
| source_page | INTEGER | | Page number in source document |
| source_bounding_box | JSONB | | Bounding box coordinates |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_bank_txn_document_id` ON bank_statement_transactions(document_id)
- `idx_bank_txn_transaction_date` ON bank_statement_transactions(transaction_date)
- `idx_bank_txn_category` ON bank_statement_transactions(category)
- `idx_bank_txn_is_wps_salary` ON bank_statement_transactions(is_wps_salary) WHERE is_wps_salary = TRUE
- `idx_bank_txn_source_bounding_box` ON bank_statement_transactions USING GIN (source_bounding_box)

---

### Schema: `credit_report_data`

Extracted data from AECB credit reports.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique record identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to base document |
| cb_subject_id | TEXT | NOT NULL | AECB subject ID |
| identity_number | TEXT | NOT NULL | Emirates ID number |
| full_name | TEXT | NOT NULL | Full name |
| contact_details | JSONB | | {phone, email, address} |
| employment_info | JSONB | | {employer, occupation, salary} |
| credit_score | INTEGER | NOT NULL, CHECK (credit_score >= 300 AND credit_score <= 900) | Credit score (300-900) |
| risk_band | TEXT | NOT NULL | Risk band: Excellent, Very Good, Good, Fair, Poor |
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
| has_bankruptcy_records | BOOLEAN | DEFAULT FALSE | Bankruptcy flag |
| inquiry_count | INTEGER | DEFAULT 0 | Number of credit inquiries |
| inquiries | JSONB | | Array of inquiry records |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| source_coordinates | JSONB | | {page, bounding_box} for each field |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_credit_report_document_id` ON credit_report_data(document_id)
- `idx_credit_report_credit_score` ON credit_report_data(credit_score)
- `idx_credit_report_identity_number` ON credit_report_data(identity_number)
- `idx_credit_report_contact_details` ON credit_report_data USING GIN (contact_details)
- `idx_credit_report_employment_info` ON credit_report_data USING GIN (employment_info)
- `idx_credit_report_active_facilities` ON credit_report_data USING GIN (active_facilities)
- `idx_credit_report_payment_history` ON credit_report_data USING GIN (payment_history)

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
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique facility identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → credit_report_data(id) ON DELETE CASCADE | Reference to credit report |
| facility_type | TEXT | NOT NULL | Type: credit_card, personal_loan, mortgage, auto_loan, overdraft |
| lender_name | TEXT | NOT NULL | Lender/bank name |
| account_number | TEXT | | Account number |
| status | TEXT | NOT NULL | Status: active, closed, defaulted |
| opened_date | DATE | | Account opening date |
| closed_date | DATE | | Account closing date |
| credit_limit | DECIMAL(15,2) | | Credit limit |
| current_balance | DECIMAL(15,2) | NOT NULL | Current outstanding balance |
| monthly_payment | DECIMAL(15,2) | | Monthly payment amount |
| payment_status | TEXT | | Payment status: current, 30_days_late, 60_days_late, 90_days_late, defaulted |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_credit_facilities_document_id` ON credit_facilities(document_id)
- `idx_credit_facilities_status` ON credit_facilities(status)

---

### Schema: `resume_data`

Extracted data from resumes/CVs.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique record identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to base document |
| full_name | TEXT | NOT NULL | Full name |
| email | TEXT | | Email address |
| phone | TEXT | | Phone number |
| location | TEXT | | Location/city |
| summary | TEXT | | Professional summary |
| years_of_experience | INTEGER | | Total years of experience |
| work_experience | JSONB | NOT NULL | Array of work experience objects |
| total_positions | INTEGER | NOT NULL | Total number of positions |
| current_employer | TEXT | | Current employer name |
| current_job_title | TEXT | | Current job title |
| education | JSONB | | Array of education records |
| highest_degree | TEXT | | Highest degree obtained |
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
- `idx_resume_document_id` ON resume_data(document_id)
- `idx_resume_full_name` ON resume_data(full_name)
- `idx_resume_email` ON resume_data(email)
- `idx_resume_work_experience` ON resume_data USING GIN (work_experience)
- `idx_resume_education` ON resume_data USING GIN (education)
- `idx_resume_skills` ON resume_data USING GIN (skills)

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
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique experience identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → resume_data(id) ON DELETE CASCADE | Reference to resume |
| job_title | TEXT | NOT NULL | Job title |
| company | TEXT | NOT NULL | Company name |
| location | TEXT | | Job location |
| start_date | DATE | NOT NULL | Start date |
| end_date | DATE | | End date (null = current) |
| is_current | BOOLEAN | DEFAULT FALSE | Current employment flag |
| description | TEXT | | Job description |
| achievements | TEXT[] | | Array of achievement bullets |
| duration_months | INTEGER | | Calculated duration in months |
| industry | TEXT | | Industry sector |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_resume_work_exp_document_id` ON resume_work_experience(document_id)
- `idx_resume_work_exp_is_current` ON resume_work_experience(company) WHERE is_current = TRUE

---

### Schema: `assets_liabilities_data`

Extracted data from assets and liabilities statements.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique record identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to base document |
| applicant_name | TEXT | NOT NULL | Applicant name |
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
- `idx_assets_liabilities_document_id` ON assets_liabilities_data(document_id)
- `idx_assets_liabilities_net_worth` ON assets_liabilities_data(net_worth)
- `idx_assets_liabilities_statement_date` ON assets_liabilities_data(statement_date)
- `idx_assets_liabilities_income_sources` ON assets_liabilities_data USING GIN (income_sources)
- `idx_assets_liabilities_asset_details` ON assets_liabilities_data USING GIN (asset_details)
- `idx_assets_liabilities_liability_details` ON assets_liabilities_data USING GIN (liability_details)

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
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique record identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to base document |
| applicant_name | TEXT | NOT NULL | Applicant name |
| identity_number | TEXT | NOT NULL | Emirates ID number |
| date_of_birth | DATE | NOT NULL | Date of birth |
| nationality | TEXT | NOT NULL | Nationality |
| contact_phone | TEXT | NOT NULL | Contact phone number |
| contact_email | TEXT | | Contact email |
| address | JSONB | NOT NULL | Address: {emirate, city, street, po_box} |
| marital_status | TEXT | | Marital status |
| family_size | INTEGER | | Family size |
| dependents | JSONB | | Array of dependent records |
| employment_status | TEXT | NOT NULL | Status: employed, self_employed, unemployed, retired |
| employer_name | TEXT | | Employer name |
| occupation | TEXT | | Occupation |
| monthly_salary | DECIMAL(15,2) | | Monthly salary |
| other_income | DECIMAL(15,2) | DEFAULT 0 | Other income sources |
| total_monthly_income | DECIMAL(15,2) | NOT NULL | Total monthly income |
| housing_status | TEXT | | Status: owned, rented, family_provided |
| monthly_rent | DECIMAL(15,2) | | Monthly rent |
| monthly_mortgage | DECIMAL(15,2) | | Monthly mortgage |
| support_category | TEXT | | Category: divorced, abandoned, unknown_parentage, health_disability |
| supporting_documents | JSONB | | Array of supporting document references |
| is_declaration_signed | BOOLEAN | DEFAULT FALSE | Declaration signed flag |
| declaration_date | DATE | | Declaration date |
| extraction_confidence | FLOAT | CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0) | Extraction confidence score |
| raw_extracted_data | JSONB | | Additional fields not in schema |
| validation_results | JSONB | | Validation rule results |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_application_form_document_id` ON application_form_data(document_id)
- `idx_application_form_identity_number` ON application_form_data(identity_number)
- `idx_application_form_total_monthly_income` ON application_form_data(total_monthly_income)
- `idx_application_form_support_category` ON application_form_data(support_category)
- `idx_application_form_address` ON application_form_data USING GIN (address)
- `idx_application_form_dependents` ON application_form_data USING GIN (dependents)
- `idx_application_form_supporting_documents` ON application_form_data USING GIN (supporting_documents)

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
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique validation identifier |
| applicant_id | UUID | NOT NULL | Reference to applicant (Neo4j node) |
| validation_type | TEXT | NOT NULL | Type: income_consistency, identity_match, address_match |
| source_documents | UUID[] | NOT NULL | Array of document_ids involved |
| source_document_types | TEXT[] | | Array of document types |
| status | TEXT | NOT NULL | Status: passed, failed, warning, manual_review |
| confidence_score | FLOAT | CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0) | Validation confidence |
| findings | JSONB | NOT NULL | Detailed validation findings |
| discrepancies | JSONB | | Array of discrepancies found |
| is_resolved | BOOLEAN | DEFAULT FALSE | Resolution status |
| resolution_notes | TEXT | | Resolution notes |
| resolved_by | TEXT | | User who resolved |
| resolved_at | TIMESTAMPTZ | | Resolution timestamp |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_cross_val_applicant_id` ON cross_document_validations(applicant_id, validation_type)
- `idx_cross_val_status` ON cross_document_validations(status) WHERE status != 'passed'
- `idx_cross_val_findings` ON cross_document_validations USING GIN (findings)
- `idx_cross_val_discrepancies` ON cross_document_validations USING GIN (discrepancies)

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

Tamper-evident audit trail for all document lifecycle events. Compliant with ISO/TS 24574:2025 and UAE government requirements.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique audit identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to document |
| action | TEXT | NOT NULL | Action: uploaded, extracted, validated, modified, deleted, accessed |
| performed_by | TEXT | NOT NULL | User ID or system identifier |
| performed_by_type | TEXT | NOT NULL, CHECK (performed_by_type IN ('user', 'system', 'agent')) | Actor type |
| timestamp | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Action timestamp |
| changes | JSONB | | Field-level diffs |
| previous_values | JSONB | | Previous field values |
| new_values | JSONB | | New field values |
| ip_address | INET | | Client IP address |
| user_agent | TEXT | | Client user agent |
| session_id | UUID | | Session identifier |
| hash | TEXT | NOT NULL | SHA-256 hash of this record + previous hash |
| previous_hash | TEXT | | Hash of previous audit record (chain) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_audit_document_id` ON document_audit_log(document_id, timestamp DESC)
- `idx_audit_action` ON document_audit_log(action, timestamp DESC)
- `idx_audit_performed_by` ON document_audit_log(performed_by, timestamp DESC)
- `idx_audit_changes` ON document_audit_log USING GIN (changes)
- `idx_audit_previous_values` ON document_audit_log USING GIN (previous_values)
- `idx_audit_new_values` ON document_audit_log USING GIN (new_values)

**Hash Chain Logic:**
```
hash = SHA256(id || document_id || action || performed_by || timestamp || changes || previous_hash)
```

---

## Supporting Schemas

### Schema: `document_processing_queue`

Tracks documents in the processing pipeline. Integrates with LangGraph agent orchestration.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique queue entry identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to document |
| stage | TEXT | NOT NULL | Pipeline stage: ingestion, classification, extraction, validation, integration |
| status | TEXT | NOT NULL, DEFAULT 'pending' | Status: pending, processing, completed, failed |
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
- `idx_queue_document_id` ON document_processing_queue(document_id)

---

### Schema: `document_extraction_fields`

Stores individual extracted fields with provenance. Enables field-level confidence tracking and human review.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuidv7() | Unique field identifier |
| document_id | UUID | NOT NULL, FOREIGN KEY → documents(id) ON DELETE CASCADE | Reference to document |
| field_name | TEXT | NOT NULL | Field name (e.g., identity_number, opening_balance) |
| field_value | TEXT | | Extracted value |
| confidence | FLOAT | CHECK (confidence >= 0.0 AND confidence <= 1.0) | Field-level confidence |
| source_page | INTEGER | | Page number in source document |
| source_bounding_box | JSONB | | Bounding box: {x, y, width, height} |
| source_text | TEXT | | Raw text from source |
| validation_status | TEXT | | Status: valid, invalid, warning, unchecked |
| validation_message | TEXT | | Validation message |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |

**Indexes:**
- `idx_extraction_fields_document_id` ON document_extraction_fields(document_id)
- `idx_extraction_fields_field_name` ON document_extraction_fields(field_name)
- `idx_extraction_fields_confidence` ON document_extraction_fields(confidence) WHERE confidence < 0.8
- `idx_extraction_fields_source_bounding_box` ON document_extraction_fields USING GIN (source_bounding_box)

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
applicant (Neo4j) (1) ←→ (0..*) documents
applicant (Neo4j) (1) ←→ (0..*) cross_document_validations
```

**Integration with Tech Stack:**
- **PostgreSQL**: Stores structured document metadata, extraction results, and audit trails
- **Neo4j**: Models applicant relationships, family structures, and document lineage
- **Qdrant**: Stores document embeddings for semantic search and similarity matching
- **LangGraph**: Orchestrates document processing pipeline with checkpointed state
- **Langfuse**: Traces all document processing steps for observability

---

## Data Types Reference

| Type | Usage |
|------|-------|
| UUID | Universally unique identifier (UUIDv7 for time-ordering) |
| TEXT | Variable-length string, unlimited (preferred over VARCHAR in PostgreSQL) |
| INTEGER | 32-bit integer |
| BIGINT | 64-bit integer |
| DECIMAL(p,s) | Fixed-point number with precision p and scale s |
| FLOAT | Double-precision floating-point |
| BOOLEAN | True/false |
| DATE | Calendar date |
| TIMESTAMPTZ | Timestamp with time zone (always use over TIMESTAMP) |
| JSONB | Binary JSON, indexed and queryable |
| TEXT[] | Array of text |
| UUID[] | Array of UUIDs |
| TEXT[] | Array of variable-length strings |
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

### processing_status
- `uploaded` - Document uploaded, not yet processed
- `classifying` - Document type classification in progress
- `extracting` - Data extraction in progress
- `validating` - Validation in progress
- `completed` - Processing complete
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

---

## Naming Conventions

Following PostgreSQL best practices:

- **Tables**: Plural nouns, snake_case (e.g., `documents`, `bank_statement_transactions`)
- **Columns**: Singular, snake_case (e.g., `document_id`, `created_at`)
- **Primary keys**: Always `id`
- **Foreign keys**: `{referenced_table_singular}_id` (e.g., `document_id`, `applicant_id`)
- **Indexes**: `idx_{table}_{columns}` (e.g., `idx_documents_applicant_id`)
- **Booleans**: Prefixed with `is_` or `has_` (e.g., `is_mrz_verified`, `is_balance_reconciled`)
- **Timestamps**: `{verb}_at` (e.g., `created_at`, `updated_at`, `uploaded_at`)
- **Constraints**: Descriptive names (e.g., `chk_document_type`, `chk_credit_score_range`)

---

## Performance Considerations

### Indexing Strategy
- **B-tree indexes**: Primary keys, foreign keys, frequently queried columns
- **GIN indexes**: JSONB columns for flexible querying
- **Partial indexes**: Filtered indexes for common queries (e.g., `WHERE status != 'passed'`)
- **Composite indexes**: Multi-column indexes for common query patterns

### Query Optimization
- Use `selectinload` for relationships to prevent N+1 queries
- Set `statement_timeout` via `SET LOCAL` for long-running queries
- Use connection pooling: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`
- Partition large tables by date (e.g., `documents` by `uploaded_at`)

### JSONB Best Practices
- Use JSONB for flexible, schema-less data (metadata, validation results)
- Add GIN indexes on JSONB columns for query performance
- Avoid querying JSONB in every WHERE clause (consider extracting to columns)
- Use JSONB for data that varies by row or changes shape over time

---

## Compliance and Security

### Audit Trail
- All document lifecycle events logged with cryptographic hash chain
- Compliant with ISO/TS 24574:2025 (Digital Safe Spec)
- UAE government electronic document management requirements
- 7-year data retention policy

### Data Protection
- Sensitive fields (identity numbers, account numbers) masked in logs
- Field-level encryption for PII (future enhancement)
- Row-level security for multi-tenancy (future enhancement)
- GDPR compliance: right to erasure, data portability

---

## Appendix: SQL Examples

### Create base documents table
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    applicant_id UUID NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN ('emirates_id', 'bank_statement', 'credit_report', 'resume', 'assets_liabilities', 'application_form')),
    processing_status TEXT NOT NULL DEFAULT 'uploaded',
    file_path TEXT NOT NULL,
    file_format TEXT,
    file_size_bytes BIGINT,
    file_hash TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    extraction_status TEXT DEFAULT 'pending',
    validation_status TEXT DEFAULT 'pending',
    overall_confidence FLOAT CHECK (overall_confidence >= 0.0 AND overall_confidence <= 1.0),
    metadata JSONB,
    error_log TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_applicant_id ON documents(applicant_id, document_type);
CREATE INDEX idx_documents_processing_status ON documents(processing_status, uploaded_at DESC);
CREATE INDEX idx_documents_extraction_status ON documents(extraction_status) WHERE extraction_status != 'success';
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);
```

### Create Emirates ID extraction table
```sql
CREATE TABLE emirates_id_data (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    identity_number TEXT NOT NULL UNIQUE,
    full_name_en TEXT NOT NULL,
    full_name_ar TEXT,
    nationality TEXT NOT NULL,
    date_of_birth DATE NOT NULL,
    gender TEXT NOT NULL CHECK (gender IN ('Male', 'Female')),
    card_number TEXT,
    issue_date DATE,
    expiry_date DATE NOT NULL,
    is_mrz_verified BOOLEAN DEFAULT FALSE,
    address JSONB,
    occupation TEXT,
    employer_name TEXT,
    marital_status TEXT,
    mother_name TEXT,
    sponsor_name TEXT,
    sponsor_type TEXT,
    residency_type TEXT,
    residency_number TEXT,
    extraction_confidence FLOAT CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0),
    raw_extracted_data JSONB,
    validation_results JSONB,
    source_coordinates JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_emirates_id_identity_number ON emirates_id_data(identity_number);
CREATE INDEX idx_emirates_id_expiry_date ON emirates_id_data(expiry_date);
CREATE INDEX idx_emirates_id_nationality ON emirates_id_data(nationality);
CREATE INDEX idx_emirates_id_address ON emirates_id_data USING GIN (address);
```
