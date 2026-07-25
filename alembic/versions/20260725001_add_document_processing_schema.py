"""add document processing schema

Revision ID: 2026-07-25-001
Revises: 
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260725001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create applicants table
    op.create_table(
        'applicants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('identity_number', sa.String(20), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('nationality', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('marital_status', sa.Text(), nullable=True),
        sa.Column('family_size', sa.Integer(), nullable=True),
        sa.Column('employment_status', sa.Text(), nullable=True),
        sa.Column('employer_name', sa.Text(), nullable=True),
        sa.Column('occupation', sa.Text(), nullable=True),
        sa.Column('housing_status', sa.Text(), nullable=True),
        sa.Column('support_category', sa.Text(), nullable=True),
        sa.Column('monthly_salary', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('identity_number'),
    )
    op.create_index('idx_applicants_identity_number', 'applicants', ['identity_number'])

    # Create applications table
    op.create_table(
        'applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('applicant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='in_progress'),
        sa.Column('current_phase', sa.String(30), nullable=False, default='intake'),
        sa.Column('langgraph_checkpoint', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('eligibility_score', sa.Float(), nullable=True),
        sa.Column('decision', sa.Text(), nullable=True),
        sa.Column('decision_explanation', sa.Text(), nullable=True),
        sa.Column('phase_completed', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('eligibility_factors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_applications_applicant_id', 'applications', ['applicant_id'])
    op.create_index('idx_applications_status', 'applications', ['status'])

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('applicant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('processing_status', sa.String(30), nullable=False, default='uploaded'),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_format', sa.Text(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('file_hash', sa.Text(), nullable=False),
        sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('processing_started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('extraction_status', sa.Text(), nullable=True, default='pending'),
        sa.Column('validation_status', sa.Text(), nullable=True, default='pending'),
        sa.Column('overall_confidence', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("document_type IN ('emirates_id', 'bank_statement', 'credit_report', 'resume', 'assets_liabilities', 'application_form')", name='chk_document_type'),
        sa.CheckConstraint('overall_confidence >= 0.0 AND overall_confidence <= 1.0', name='chk_overall_confidence'),
    )
    op.create_index('idx_documents_applicant_id', 'documents', ['applicant_id', 'document_type'])
    op.create_index('idx_documents_processing_status', 'documents', ['processing_status', sa.text('uploaded_at DESC')])
    op.create_index('idx_documents_extraction_status', 'documents', ['extraction_status'], postgresql_where=sa.text("extraction_status != 'success'"))
    op.create_index('idx_documents_metadata', 'documents', ['metadata'], postgresql_using='gin')

    # Create emirates_id_data table
    op.create_table(
        'emirates_id_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('identity_number', sa.Text(), nullable=False),
        sa.Column('full_name_en', sa.Text(), nullable=False),
        sa.Column('full_name_ar', sa.Text(), nullable=True),
        sa.Column('nationality', sa.Text(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', sa.Text(), nullable=False),
        sa.Column('card_number', sa.Text(), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('is_mrz_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('occupation', sa.Text(), nullable=True),
        sa.Column('employer_name', sa.Text(), nullable=True),
        sa.Column('marital_status', sa.Text(), nullable=True),
        sa.Column('mother_name', sa.Text(), nullable=True),
        sa.Column('sponsor_name', sa.Text(), nullable=True),
        sa.Column('sponsor_type', sa.Text(), nullable=True),
        sa.Column('residency_type', sa.Text(), nullable=True),
        sa.Column('residency_number', sa.Text(), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('raw_extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_coordinates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.UniqueConstraint('identity_number'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint("gender IN ('Male', 'Female')", name='chk_emirates_id_gender'),
        sa.CheckConstraint('extraction_confidence >= 0.0 AND extraction_confidence <= 1.0', name='chk_emirates_id_confidence'),
    )
    op.create_index('idx_emirates_id_identity_number', 'emirates_id_data', ['identity_number'])
    op.create_index('idx_emirates_id_expiry_date', 'emirates_id_data', ['expiry_date'])
    op.create_index('idx_emirates_id_nationality', 'emirates_id_data', ['nationality'])
    op.create_index('idx_emirates_id_address', 'emirates_id_data', ['address'], postgresql_using='gin')

    # Create bank_statement_data table
    op.create_table(
        'bank_statement_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bank_name', sa.Text(), nullable=False),
        sa.Column('account_holder_name', sa.Text(), nullable=False),
        sa.Column('account_number', sa.Text(), nullable=False),
        sa.Column('iban', sa.Text(), nullable=True),
        sa.Column('account_type', sa.Text(), nullable=True),
        sa.Column('currency', sa.Text(), nullable=False, default='AED'),
        sa.Column('statement_period_start', sa.Date(), nullable=False),
        sa.Column('statement_period_end', sa.Date(), nullable=False),
        sa.Column('opening_balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('closing_balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_debits', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_credits', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('is_balance_reconciled', sa.Boolean(), nullable=False, default=False),
        sa.Column('transactions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('transaction_count', sa.Integer(), nullable=False),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('raw_extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_coordinates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint('extraction_confidence >= 0.0 AND extraction_confidence <= 1.0', name='chk_bank_stmt_confidence'),
    )
    op.create_index('idx_bank_stmt_document_id', 'bank_statement_data', ['document_id'])
    op.create_index('idx_bank_stmt_account_number', 'bank_statement_data', ['account_number'])
    op.create_index('idx_bank_stmt_period', 'bank_statement_data', ['statement_period_start', 'statement_period_end'])
    op.create_index('idx_bank_stmt_transactions', 'bank_statement_data', ['transactions'], postgresql_using='gin')

    # Create bank_statement_transactions table
    op.create_table(
        'bank_statement_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_hash', sa.Text(), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('transaction_type', sa.Text(), nullable=False),
        sa.Column('running_balance', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('counterparty', sa.Text(), nullable=True),
        sa.Column('reference_number', sa.Text(), nullable=True),
        sa.Column('is_wps_salary', sa.Boolean(), nullable=False, default=False),
        sa.Column('channel', sa.Text(), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),
        sa.Column('source_bounding_box', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_hash'),
        sa.ForeignKeyConstraint(['document_id'], ['bank_statement_data.id'], ondelete='CASCADE'),
        sa.CheckConstraint("transaction_type IN ('debit', 'credit')", name='chk_bank_txn_type'),
    )
    op.create_index('idx_bank_txn_document_id', 'bank_statement_transactions', ['document_id'])
    op.create_index('idx_bank_txn_transaction_date', 'bank_statement_transactions', ['transaction_date'])
    op.create_index('idx_bank_txn_category', 'bank_statement_transactions', ['category'])
    op.create_index('idx_bank_txn_is_wps_salary', 'bank_statement_transactions', ['is_wps_salary'], postgresql_where=sa.text('is_wps_salary = TRUE'))
    op.create_index('idx_bank_txn_source_bounding_box', 'bank_statement_transactions', ['source_bounding_box'], postgresql_using='gin')

    # Create credit_report_data table
    op.create_table(
        'credit_report_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cb_subject_id', sa.Text(), nullable=False),
        sa.Column('identity_number', sa.Text(), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=False),
        sa.Column('contact_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('employment_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('credit_score', sa.Integer(), nullable=False),
        sa.Column('risk_band', sa.Text(), nullable=False),
        sa.Column('score_calculation_date', sa.Date(), nullable=True),
        sa.Column('total_active_accounts', sa.Integer(), nullable=False),
        sa.Column('total_closed_accounts', sa.Integer(), nullable=False),
        sa.Column('total_outstanding_balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_credit_limit', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('credit_utilization_ratio', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('active_facilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('closed_facilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('payment_history', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('late_payment_count', sa.Integer(), nullable=False, default=0),
        sa.Column('defaulted_accounts', sa.Integer(), nullable=False, default=0),
        sa.Column('bounced_cheques', sa.Integer(), nullable=False, default=0),
        sa.Column('court_judgments', sa.Integer(), nullable=False, default=0),
        sa.Column('has_bankruptcy_records', sa.Boolean(), nullable=False, default=False),
        sa.Column('inquiry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('inquiries', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('raw_extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_coordinates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint('credit_score >= 300 AND credit_score <= 900', name='chk_credit_score_range'),
        sa.CheckConstraint('extraction_confidence >= 0.0 AND extraction_confidence <= 1.0', name='chk_credit_report_confidence'),
    )
    op.create_index('idx_credit_report_document_id', 'credit_report_data', ['document_id'])
    op.create_index('idx_credit_report_credit_score', 'credit_report_data', ['credit_score'])
    op.create_index('idx_credit_report_identity_number', 'credit_report_data', ['identity_number'])
    op.create_index('idx_credit_report_contact_details', 'credit_report_data', ['contact_details'], postgresql_using='gin')
    op.create_index('idx_credit_report_employment_info', 'credit_report_data', ['employment_info'], postgresql_using='gin')
    op.create_index('idx_credit_report_active_facilities', 'credit_report_data', ['active_facilities'], postgresql_using='gin')
    op.create_index('idx_credit_report_payment_history', 'credit_report_data', ['payment_history'], postgresql_using='gin')

    # Create credit_facilities table
    op.create_table(
        'credit_facilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('facility_type', sa.Text(), nullable=False),
        sa.Column('lender_name', sa.Text(), nullable=False),
        sa.Column('account_number', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('opened_date', sa.Date(), nullable=True),
        sa.Column('closed_date', sa.Date(), nullable=True),
        sa.Column('credit_limit', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('current_balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_payment', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('payment_status', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['credit_report_data.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_credit_facilities_document_id', 'credit_facilities', ['document_id'])
    op.create_index('idx_credit_facilities_status', 'credit_facilities', ['status'])

    # Create resume_data table
    op.create_table(
        'resume_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('years_of_experience', sa.Integer(), nullable=True),
        sa.Column('work_experience', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('total_positions', sa.Integer(), nullable=False),
        sa.Column('current_employer', sa.Text(), nullable=True),
        sa.Column('current_job_title', sa.Text(), nullable=True),
        sa.Column('education', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('highest_degree', sa.Text(), nullable=True),
        sa.Column('skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('skill_count', sa.Integer(), nullable=False, default=0),
        sa.Column('certifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('raw_extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_coordinates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint('extraction_confidence >= 0.0 AND extraction_confidence <= 1.0', name='chk_resume_confidence'),
    )
    op.create_index('idx_resume_document_id', 'resume_data', ['document_id'])
    op.create_index('idx_resume_full_name', 'resume_data', ['full_name'])
    op.create_index('idx_resume_email', 'resume_data', ['email'])
    op.create_index('idx_resume_work_experience', 'resume_data', ['work_experience'], postgresql_using='gin')
    op.create_index('idx_resume_education', 'resume_data', ['education'], postgresql_using='gin')
    op.create_index('idx_resume_skills', 'resume_data', ['skills'], postgresql_using='gin')

    # Create resume_work_experience table
    op.create_table(
        'resume_work_experience',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_title', sa.Text(), nullable=False),
        sa.Column('company', sa.Text(), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, default=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('achievements', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('duration_months', sa.Integer(), nullable=True),
        sa.Column('industry', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['resume_data.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_resume_work_exp_document_id', 'resume_work_experience', ['document_id'])
    op.create_index('idx_resume_work_exp_is_current', 'resume_work_experience', ['company'], postgresql_where=sa.text('is_current = TRUE'))

    # Create assets_liabilities_data table
    op.create_table(
        'assets_liabilities_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('applicant_name', sa.Text(), nullable=False),
        sa.Column('statement_date', sa.Date(), nullable=False),
        sa.Column('cash_and_deposits', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('savings_accounts', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('investment_accounts', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('retirement_accounts', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('real_estate_value', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('vehicle_value', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('other_assets', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('total_assets', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('mortgage_balance', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('personal_loans', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('credit_card_debt', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('student_loans', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('other_liabilities', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('total_liabilities', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('net_worth', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_income', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('income_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('asset_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('liability_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('raw_extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_coordinates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint('extraction_confidence >= 0.0 AND extraction_confidence <= 1.0', name='chk_assets_liabilities_confidence'),
    )
    op.create_index('idx_assets_liabilities_document_id', 'assets_liabilities_data', ['document_id'])
    op.create_index('idx_assets_liabilities_net_worth', 'assets_liabilities_data', ['net_worth'])
    op.create_index('idx_assets_liabilities_statement_date', 'assets_liabilities_data', ['statement_date'])
    op.create_index('idx_assets_liabilities_income_sources', 'assets_liabilities_data', ['income_sources'], postgresql_using='gin')
    op.create_index('idx_assets_liabilities_asset_details', 'assets_liabilities_data', ['asset_details'], postgresql_using='gin')
    op.create_index('idx_assets_liabilities_liability_details', 'assets_liabilities_data', ['liability_details'], postgresql_using='gin')

    # Create application_form_data table
    op.create_table(
        'application_form_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('applicant_name', sa.Text(), nullable=False),
        sa.Column('identity_number', sa.Text(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('nationality', sa.Text(), nullable=False),
        sa.Column('contact_phone', sa.Text(), nullable=False),
        sa.Column('contact_email', sa.Text(), nullable=True),
        sa.Column('address', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('marital_status', sa.Text(), nullable=True),
        sa.Column('family_size', sa.Integer(), nullable=True),
        sa.Column('dependents', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('employment_status', sa.Text(), nullable=False),
        sa.Column('employer_name', sa.Text(), nullable=True),
        sa.Column('occupation', sa.Text(), nullable=True),
        sa.Column('monthly_salary', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('other_income', sa.Numeric(precision=15, scale=2), nullable=False, default=0),
        sa.Column('total_monthly_income', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('housing_status', sa.Text(), nullable=True),
        sa.Column('monthly_rent', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('monthly_mortgage', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('support_category', sa.Text(), nullable=True),
        sa.Column('supporting_documents', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_declaration_signed', sa.Boolean(), nullable=False, default=False),
        sa.Column('declaration_date', sa.Date(), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('raw_extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint('extraction_confidence >= 0.0 AND extraction_confidence <= 1.0', name='chk_application_form_confidence'),
    )
    op.create_index('idx_application_form_document_id', 'application_form_data', ['document_id'])
    op.create_index('idx_application_form_identity_number', 'application_form_data', ['identity_number'])
    op.create_index('idx_application_form_total_monthly_income', 'application_form_data', ['total_monthly_income'])
    op.create_index('idx_application_form_support_category', 'application_form_data', ['support_category'])
    op.create_index('idx_application_form_address', 'application_form_data', ['address'], postgresql_using='gin')
    op.create_index('idx_application_form_dependents', 'application_form_data', ['dependents'], postgresql_using='gin')
    op.create_index('idx_application_form_supporting_documents', 'application_form_data', ['supporting_documents'], postgresql_using='gin')

    # Create cross_document_validations table
    op.create_table(
        'cross_document_validations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('applicant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('validation_type', sa.String(50), nullable=False),
        sa.Column('source_documents', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('source_document_types', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('findings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('discrepancies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, default=False),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('confidence_score >= 0.0 AND confidence_score <= 1.0', name='chk_cross_val_confidence'),
    )
    op.create_index('idx_cross_val_applicant_id', 'cross_document_validations', ['applicant_id', 'validation_type'])
    op.create_index('idx_cross_val_status', 'cross_document_validations', ['status'], postgresql_where=sa.text("status != 'passed'"))
    op.create_index('idx_cross_val_findings', 'cross_document_validations', ['findings'], postgresql_using='gin')
    op.create_index('idx_cross_val_discrepancies', 'cross_document_validations', ['discrepancies'], postgresql_using='gin')

    # Create document_audit_log table
    op.create_table(
        'document_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('performed_by', sa.Text(), nullable=False),
        sa.Column('performed_by_type', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('previous_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('hash', sa.Text(), nullable=False),
        sa.Column('previous_hash', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint("performed_by_type IN ('user', 'system', 'agent')", name='chk_audit_performed_by_type'),
    )
    op.create_index('idx_audit_document_id', 'document_audit_log', ['document_id', sa.text('timestamp DESC')])
    op.create_index('idx_audit_action', 'document_audit_log', ['action', sa.text('timestamp DESC')])
    op.create_index('idx_audit_performed_by', 'document_audit_log', ['performed_by', sa.text('timestamp DESC')])
    op.create_index('idx_audit_changes', 'document_audit_log', ['changes'], postgresql_using='gin')
    op.create_index('idx_audit_previous_values', 'document_audit_log', ['previous_values'], postgresql_using='gin')
    op.create_index('idx_audit_new_values', 'document_audit_log', ['new_values'], postgresql_using='gin')

    # Create document_processing_queue table
    op.create_table(
        'document_processing_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stage', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, default='pending'),
        sa.Column('priority', sa.Integer(), nullable=False, default=0),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_queue_stage_status', 'document_processing_queue', ['stage', 'status'])
    op.create_index('idx_queue_priority', 'document_processing_queue', [sa.text('priority DESC'), 'created_at'])
    op.create_index('idx_queue_document_id', 'document_processing_queue', ['document_id'])

    # Create document_extraction_fields table
    op.create_table(
        'document_extraction_fields',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_name', sa.Text(), nullable=False),
        sa.Column('field_value', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),
        sa.Column('source_bounding_box', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('validation_status', sa.Text(), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='chk_extraction_field_confidence'),
    )
    op.create_index('idx_extraction_fields_document_id', 'document_extraction_fields', ['document_id'])
    op.create_index('idx_extraction_fields_field_name', 'document_extraction_fields', ['field_name'])
    op.create_index('idx_extraction_fields_confidence', 'document_extraction_fields', ['confidence'], postgresql_where=sa.text('confidence < 0.8'))
    op.create_index('idx_extraction_fields_source_bounding_box', 'document_extraction_fields', ['source_bounding_box'], postgresql_using='gin')


def downgrade() -> None:
    op.drop_table('applications')
    op.drop_table('applicants')
    op.drop_table('document_extraction_fields')
    op.drop_table('document_processing_queue')
    op.drop_table('document_audit_log')
    op.drop_table('cross_document_validations')
    op.drop_table('application_form_data')
    op.drop_table('assets_liabilities_data')
    op.drop_table('resume_work_experience')
    op.drop_table('resume_data')
    op.drop_table('credit_facilities')
    op.drop_table('credit_report_data')
    op.drop_table('bank_statement_transactions')
    op.drop_table('bank_statement_data')
    op.drop_table('emirates_id_data')
    op.drop_table('documents')
