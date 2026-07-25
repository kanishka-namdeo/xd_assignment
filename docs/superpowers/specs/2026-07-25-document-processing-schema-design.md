# Document Processing Schema Design Specification

**Date:** 2026-07-25  
**Version:** 1.0  
**Status:** Draft

## Executive Summary

This specification defines a scalable, hybrid document processing schema for the UAE Social Support Application Workflow Automation system. The architecture processes six document types (Emirates ID, bank statements, credit reports, resumes, assets/liabilities statements, and application forms) using a PostgreSQL-based storage layer with event-driven processing pipelines.

The design follows 2025-2026 industry best practices for document processing systems, including confidence-based routing, tamper-evident audit trails, extraction provenance tracking, and balance reconciliation for financial documents.

## Design Principles

### 1. Event-Driven Multi-Stage Pipeline
Documents flow through independent processing stages (ingestion → classification → extraction → validation → integration) that scale separately based on compute requirements.

### 2. Golden Record Pattern
Deduplicated, normalized data with deterministic hashing ensures consistency across overlapping statement periods and multiple document uploads.

### 3. Confidence-Based Routing
- Auto-approve extractions with >95% confidence
- Flag mid-confidence (80-95%) for spot-check review
- Route low-confidence (<80%) to human review queues

### 4. Tamper-Evident Audit Trails
Cryptographic hashing on all document lifecycle events per ISO/TS 24574:2025 and government compliance requirements.

### 5. Extraction Provenance
Preserve page numbers, bounding boxes, and source coordinates for every extracted field to enable verifiable human review.

### 6. Balance Reconciliation
Financial documents must pass mathematical validation: opening balance + credits - debits = closing balance. Non-reconciling documents are rejected.

## Architecture Overview

### Hybrid Schema Structure
- **Base documents table:** Common metadata for all document types
- **Specialized data tables:** One table per document type with optimized schema
- **Audit trail table:** Tamper-evident logging of all document lifecycle events
- **Cross-document validation table:** Consistency checks across multiple documents

### Database Technology
- **Primary:** PostgreSQL 15+ with JSONB for flexible metadata
- **File storage:** Object storage (S3-compatible) for binary files
- **Search:** PostgreSQL full-text search with GIN indexes (Elasticsearch for future scale)

## Document Types and Schemas

### 1. Emirates ID (Identity Verification)

**Purpose:** Extract demographic data and verify identity

**Source Formats:** PDF scans, images (JPG/PNG), smart card chip data

**Key Fields:**
- Identity number (15-digit format: 784-YYYY-XXXXXXX-X)
- Full name (English and Arabic)
- Nationality, date of birth, gender
- Card expiry date, MRZ verification status
- Address, occupation, employer (post-2022 cards)
- Marital status, mother's name, sponsor details

**Validation Rules:**
- Identity number checksum verification
- Expiry date must be in the future
- MRZ zone must be present and verified
- Name consistency across documents

**Schema:** `emirates_id_data`

### 2. Bank Statements (Income & Transaction Analysis)

**Purpose:** Verify income, analyze spending patterns, detect salary consistency

**Source Formats:** PDF (digital and scanned), CSV, OFX/QFX

**Key Fields:**
- Account information (bank name, account number, IBAN)
- Statement period (start/end dates)
- Opening/closing balances, total debits/credits
- Transaction array (date, description, amount, running balance)
- Transaction categorization (salary, utilities, transfers)
- WPS (Wage Protection System) salary identification

**Validation Rules:**
- Balance reconciliation: opening + credits - debits = closing
- Transaction deduplication via content hashing
- Date range validation (no future dates)
- Currency consistency (AED primary)

**Schemas:**
- `bank_statement_data` (summary)
- `bank_statement_transactions` (normalized transactions)

### 3. Credit Reports (AECB - Creditworthiness Assessment)

**Purpose:** Assess creditworthiness, debt burden, payment history

**Source Formats:** PDF (AECB official reports)

**Key Fields:**
- CB subject ID, Emirates ID
- Credit score (300-900 range), risk band
- Active/closed credit facilities
- Outstanding balances, credit limits
- Payment history (24-36 months)
- Late payments, defaults, bounced cheques
- Court judgments, bankruptcy records

**Validation Rules:**
- Credit score range validation (300-900)
- Identity number must match Emirates ID
- Total outstanding must equal sum of facility balances
- Payment history timeline consistency

**Schemas:**
- `credit_report_data` (summary)
- `credit_facilities` (detailed credit accounts)

### 4. Resume/CV (Employment History)

**Purpose:** Extract employment history, skills, education for economic enablement

**Source Formats:** PDF, DOCX, DOC

**Key Fields:**
- Personal information (name, email, phone, location)
- Work experience (job title, company, dates, achievements)
- Education (degrees, institutions, graduation dates)
- Skills (technical and soft skills)
- Certifications

**Validation Rules:**
- Date consistency (start < end, no future dates)
- Current employment detection (end_date = null or "Present")
- Duration calculation validation
- Contact information format validation

**Schemas:**
- `resume_data` (summary)
- `resume_work_experience` (detailed work history)

### 5. Assets & Liabilities (Wealth Assessment)

**Purpose:** Calculate net worth, assess financial stability

**Source Formats:** Excel (XLSX), PDF

**Key Fields:**
- Assets: cash, savings, investments, real estate, vehicles
- Liabilities: mortgages, loans, credit card debt
- Net worth calculation (assets - liabilities)
- Income sources (if included)
- Statement date

**Validation Rules:**
- Net worth = total assets - total liabilities
- All values must be non-negative
- Statement date must be recent (within 6 months)
- Asset categories must sum to total assets

**Schema:** `assets_liabilities_data`

### 6. Application Forms (Structured Data Collection)

**Purpose:** Collect structured applicant data via interactive forms

**Source Formats:** Digital form submission (JSON)

**Key Fields:**
- Applicant information (name, Emirates ID, contact details)
- Family information (marital status, dependents)
- Employment and income details
- Housing status (rent, mortgage)
- Support category (divorced, abandoned, disability, etc.)
- Declaration and signature

**Validation Rules:**
- Emirates ID must match uploaded Emirates ID document
- Income must be consistent with bank statements
- Support category must have corresponding supporting documents
- All required fields must be present

**Schema:** `application_form_data`

## Cross-Document Validation

### Consistency Checks

**Identity Consistency:**
- Emirates ID number must match across all documents
- Name variations must be reconcilable (e.g., full name vs. short name)
- Date of birth must be consistent

**Income Consistency:**
- Bank statement salary credits must align with application form income
- Credit report outstanding balances must align with assets/liabilities
- Employment history in resume must align with application form

**Address Consistency:**
- Address in Emirates ID should match application form
- Address in bank statements should be consistent

**Schema:** `cross_document_validations`

## Audit Trail and Compliance

### Tamper-Evident Logging

Every document lifecycle event is logged with:
- Action type (uploaded, extracted, validated, modified, deleted, accessed)
- Performed by (user ID or system)
- Timestamp
- Change details (field-level diffs)
- Cryptographic hash chain (each record hashes previous record)

**Compliance Standards:**
- ISO/TS 24574:2025 (Digital Safe Spec)
- UAE government electronic document management requirements
- Data retention policies (7 years minimum)

**Schema:** `document_audit_log`

## Scalability Features

### Partitioning Strategy

**Documents Table:** Partitioned by upload_timestamp (monthly partitions)
- Improves query performance for recent documents
- Enables efficient archival of old data
- Simplifies backup and maintenance

### Indexing Strategy

**B-tree Indexes:**
- Primary keys and foreign keys
- Frequently queried fields (applicant_id, document_type, status)
- Composite indexes for common query patterns

**GIN Indexes:**
- JSONB columns for flexible metadata querying
- Full-text search on document descriptions

**Partial Indexes:**
- Failed extractions (WHERE extraction_status != 'success')
- Active documents (WHERE status != 'archived')

### Performance Optimizations

**Connection Pooling:** PgBouncer for efficient connection management

**Read Replicas:** Separate replicas for reporting queries to avoid load on primary

**Materialized Views:** Pre-computed aggregations for dashboards and reports

**Async Processing:** Message queue (Redis/RabbitMQ) for document processing pipeline

### Multi-Tenancy Support

**Row-Level Security (RLS):** Tenant isolation at database level

**Session Variables:** Set tenant context per connection

**Composite Indexes:** tenant_id as first column in all indexes

## Data Flow and Processing Pipeline

### Stage 1: Ingestion
- Accept documents from upload API
- Store binary files in object storage (S3)
- Create document record with metadata
- Calculate file hash for integrity verification
- Emit event to message queue

### Stage 2: Classification
- Detect document type (Emirates ID, bank statement, etc.)
- Route to appropriate extraction pipeline
- Handle image preprocessing (deskew, denoise)
- Determine if OCR is needed (scanned vs. digital PDF)

### Stage 3: Extraction
- Run document-specific extraction model
- Extract fields with confidence scores
- Preserve source coordinates (page, bounding box)
- Store raw extracted data for auditability

### Stage 4: Validation
- Field-level validation (data types, ranges, formats)
- Cross-field validation (balance reconciliation, date consistency)
- Cross-document validation (identity match, income consistency)
- Calculate overall confidence score

### Stage 5: Routing
- High confidence (>95%): Auto-approve, proceed to integration
- Mid confidence (80-95%): Flag for spot-check review
- Low confidence (<80%): Route to human review queue
- Validation failures: Route to exception queue

### Stage 6: Integration
- Update document status
- Emit events for downstream processing
- Trigger eligibility assessment workflow
- Update applicant profile

## Error Handling and Retry Logic

### Error Categories

**Transient Errors:** Network timeouts, temporary service unavailability
- Retry with exponential backoff (max 3 retries)
- Use jitter to prevent thundering herd

**Permanent Errors:** Invalid file format, corrupted data, schema validation failures
- Log error, mark document as failed
- Route to exception queue for manual review
- Do not retry automatically

**Partial Success:** Some fields extracted, others failed
- Store partial results with confidence scores
- Flag for human review of failed fields
- Allow manual correction and re-validation

### Dead Letter Queue

Documents that fail after max retries are moved to dead letter queue:
- Preserved for manual investigation
- Alert operations team
- Provide retry mechanism after issue resolution

## Security and Access Control

### Data Encryption

**At Rest:** AES-256 encryption for all stored data

**In Transit:** TLS 1.3 for all API communications

**Field-Level Encryption:** Sensitive fields (identity numbers, account numbers) encrypted separately

### Access Control

**Role-Based Access Control (RBAC):**
- Applicant: Can only view own documents
- Case Worker: Can view assigned applicant documents
- Reviewer: Can view and approve/reject documents
- Admin: Full system access

**Row-Level Security:** PostgreSQL RLS policies enforce tenant isolation

### Audit and Compliance

**Immutable Audit Trail:** All document access and modifications logged

**Data Retention:** Configurable retention policies per document type

**GDPR Compliance:** Right to erasure, data portability, consent management

## Monitoring and Observability

### Metrics

**Pipeline Health:**
- Documents processed per hour
- Average processing time per stage
- Error rates by document type
- Queue depths and processing lag

**Extraction Quality:**
- Average confidence scores by document type
- Straight-through processing rate (% auto-approved)
- Human review queue length
- Validation failure rates

**System Performance:**
- Database query latency
- API response times
- Error rates by endpoint
- Resource utilization (CPU, memory, disk)

### Alerting

**Critical Alerts:**
- Pipeline processing failures
- Database connection pool exhaustion
- Queue depth exceeding threshold
- Error rate spike (>5% in 5 minutes)

**Warning Alerts:**
- Processing time degradation
- Confidence score drop
- Queue depth increasing
- Disk space running low

### Logging

**Structured Logging:** JSON format with correlation IDs

**Log Levels:**
- ERROR: Processing failures, validation errors
- WARN: Low confidence extractions, retries
- INFO: Document lifecycle events
- DEBUG: Detailed processing steps (development only)

**Log Retention:** 90 days in hot storage, 7 years in cold storage

## Future Enhancements

### Phase 2 Features

**Advanced Analytics:**
- Spending pattern analysis from bank statements
- Income trend detection
- Risk scoring models
- Fraud detection algorithms

**Enhanced Validation:**
- Machine learning for anomaly detection
- Pattern recognition for document tampering
- Automated consistency scoring

**Integration Enhancements:**
- Real-time bank statement verification via Open Banking APIs
- Automated credit report retrieval from AECB
- Government database integration for identity verification

### Phase 3 Features

**Multi-Language Support:**
- Arabic language processing
- Bilingual document handling
- Translation services

**Advanced OCR:**
- Handwriting recognition for handwritten forms
- Multi-column layout handling
- Complex table extraction

**Workflow Automation:**
- Automated document requests for missing information
- Intelligent routing based on document quality
- Predictive processing time estimates

## Implementation Considerations

### Migration Strategy

**Phase 1:** Core schemas and basic processing
- Base documents table
- Emirates ID and application form processing
- Basic audit trail

**Phase 2:** Financial document processing
- Bank statement and credit report schemas
- Balance reconciliation
- Cross-document validation

**Phase 3:** Advanced features
- Resume and assets/liabilities processing
- Confidence-based routing
- Advanced analytics

### Testing Strategy

**Unit Tests:** Schema validation, business logic, validation rules

**Integration Tests:** End-to-end document processing pipeline

**Performance Tests:** Load testing, query optimization, partitioning validation

**Security Tests:** Access control validation, audit trail integrity

## Conclusion

This design specification provides a scalable, compliant, and performant foundation for document processing in the UAE Social Support Application system. The hybrid schema approach balances query performance with schema flexibility, while the event-driven pipeline enables independent scaling of processing stages.

The design is grounded in 2025-2026 industry best practices for document processing, government compliance, and financial data handling. The modular architecture supports incremental implementation and future enhancements without requiring schema redesign.

## Appendix A: Schema Reference

See individual schema definitions in the main document for detailed field specifications.

## Appendix B: Validation Rules Reference

See validation rules documented under each document type.

## Appendix C: Compliance Standards

- ISO/TS 24574:2025 - Digital Safe Spec for Secure Document Management
- UAE Federal Decree Law No. 23 of 2024 - Social Support and Empowerment
- Cabinet Resolution No. 57 of 2025 - Executive Regulations
- AECB Credit Report Standards
- UAE Data Protection Law

## Appendix D: Glossary

**AECB:** Al Etihad Credit Bureau  
**IBAN:** International Bank Account Number  
**MRZ:** Machine Readable Zone  
**WPS:** Wage Protection System  
**RLS:** Row-Level Security  
**JSONB:** Binary JSON data type in PostgreSQL  
**GIN:** Generalized Inverted Index
