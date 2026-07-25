"""Comprehensive database layer test script.

Tests all 16 models, relationships, constraints, and repository operations
against a real PostgreSQL database.
"""

import asyncio
import hashlib
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.config import Settings
from src.infrastructure.db.models import (
    Applicant,
    Application,
    AuditLog,
    ProcessingQueue,
    Document,
    EmiratesIDData,
    BankStatementData,
    BankStatementTransaction,
    CreditReportData,
    CreditFacility,
    ResumeData,
    ResumeWorkExperience,
    AssetsLiabilitiesData,
    ApplicationFormData,
    DocumentExtractionField,
    CrossDocumentValidation,
)
from src.infrastructure.db.repositories import (
    ApplicantRepository,
    ApplicationRepository,
    DocumentRepository,
    EmiratesIDRepository,
    BankStatementRepository,
    CreditReportRepository,
    ResumeRepository,
    AssetsLiabilitiesRepository,
    ApplicationFormRepository,
    AuditLogRepository,
    ProcessingQueueRepository,
    CrossDocumentValidationRepository,
)


# ═══════════════════════════════════════════════════════════
# Test harness
# ═══════════════════════════════════════════════════════════

passed = 0
failed = 0
errors = []


def ok(name: str):
    global passed
    passed += 1
    print(f"  [PASS] {name}")


def fail(name: str, detail: str):
    global failed
    failed += 1
    errors.append((name, detail))
    print(f"  [FAIL] {name}: {detail}")


# ═══════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════

async def run_tests():
    global passed, failed

    settings = Settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("\n" + "=" * 60)
    print("DATABASE LAYER TESTS")
    print("=" * 60)

    # ───────────────────────────────────────────────────────
    # 1. Model instantiation tests (all 16 models)
    # ───────────────────────────────────────────────────────
    print("\n[1/5] Model Instantiation Tests")

    app_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    ext_id = uuid.uuid4()

    try:
        applicant = Applicant(
            id=app_id,
            identity_number="784-1990-1234567-1",
            full_name="Ahmed Hassan Al-Mansouri",
            date_of_birth=date(1990, 5, 15),
            nationality="Emirati",
            phone="+971501234567",
            email="ahmed.almansouri@example.ae",
            address={"emirate": "Dubai", "area": "Dubai Marina", "building": "Marina Gate"},
            marital_status="Married",
            family_size=4,
            employment_status="Employed",
            employer_name="Emirates NBD",
            occupation="Software Engineer",
            housing_status="Rented",
            support_category="Housing Support",
            monthly_salary=Decimal("18000.00"),
        )
        ok("Applicant model instantiation")
    except Exception as e:
        fail("Applicant model instantiation", str(e))

    try:
        application = Application(applicant_id=app_id, status="in_progress", current_phase="intake")
        ok("Application model instantiation")
    except Exception as e:
        fail("Application model instantiation", str(e))

    try:
        document = Document(
            id=doc_id,
            applicant_id=app_id,
            document_type="emirates_id",
            processing_status="uploaded",
            file_path="/uploads/docs/emirates_id_001.pdf",
            file_format="pdf",
            file_size_bytes=524288,
            file_hash="sha256:" + hashlib.sha256(b"test").hexdigest(),
            extraction_status="pending",
            validation_status="pending",
            overall_confidence=0.95,
            doc_metadata={"source": "web_upload", "ip": "192.168.1.1"},
        )
        ok("Document model instantiation")
    except Exception as e:
        fail("Document model instantiation", str(e))

    try:
        emirates_id = EmiratesIDData(
            document_id=doc_id,
            identity_number="784-1990-1234567-1",
            full_name_en="Ahmed Hassan Al-Mansouri",
            nationality="Emirati",
            date_of_birth=date(1990, 5, 15),
            gender="Male",
            expiry_date=date(2028, 5, 14),
            is_mrz_verified=True,
            extraction_confidence=0.97,
        )
        ok("EmiratesIDData model instantiation")
    except Exception as e:
        fail("EmiratesIDData model instantiation", str(e))

    try:
        bank_stmt = BankStatementData(
            document_id=doc_id,
            bank_name="Emirates NBD",
            account_holder_name="Ahmed Hassan Al-Mansouri",
            account_number="AE070331234567890123456",
            iban="AE070331234567890123456",
            currency="AED",
            statement_period_start=date(2025, 1, 1),
            statement_period_end=date(2025, 1, 31),
            opening_balance=Decimal("25000.00"),
            closing_balance=Decimal("22500.00"),
            total_debits=Decimal("15000.00"),
            total_credits=Decimal("12500.00"),
            is_balance_reconciled=True,
            transactions=[],
            transaction_count=0,
            extraction_confidence=0.92,
        )
        ok("BankStatementData model instantiation")
    except Exception as e:
        fail("BankStatementData model instantiation", str(e))

    try:
        txn = BankStatementTransaction(
            document_id=ext_id,
            transaction_hash=hashlib.sha256(b"txn_001").hexdigest(),
            transaction_date=date(2025, 1, 15),
            description="SALARY CREDIT",
            amount=Decimal("18000.00"),
            transaction_type="credit",
            running_balance=Decimal("40500.00"),
            is_wps_salary=True,
        )
        ok("BankStatementTransaction model instantiation")
    except Exception as e:
        fail("BankStatementTransaction model instantiation", str(e))

    try:
        credit_report = CreditReportData(
            document_id=doc_id,
            cb_subject_id="CB123456",
            identity_number="784-1990-1234567-1",
            full_name="Ahmed Hassan Al-Mansouri",
            credit_score=720,
            risk_band="Low",
            total_active_accounts=3,
            total_closed_accounts=1,
            total_outstanding_balance=Decimal("45000.00"),
            extraction_confidence=0.89,
        )
        ok("CreditReportData model instantiation")
    except Exception as e:
        fail("CreditReportData model instantiation", str(e))

    try:
        facility = CreditFacility(
            document_id=ext_id,
            facility_type="Credit Card",
            lender_name="Emirates NBD",
            status="Active",
            current_balance=Decimal("5000.00"),
        )
        ok("CreditFacility model instantiation")
    except Exception as e:
        fail("CreditFacility model instantiation", str(e))

    try:
        resume = ResumeData(
            document_id=doc_id,
            full_name="Ahmed Hassan Al-Mansouri",
            email="ahmed@example.ae",
            phone="+971501234567",
            location="Dubai, UAE",
            summary="Experienced software engineer",
            years_of_experience=8,
            work_experience={},
            total_positions=3,
            skill_count=12,
            extraction_confidence=0.88,
        )
        ok("ResumeData model instantiation")
    except Exception as e:
        fail("ResumeData model instantiation", str(e))

    try:
        work_exp = ResumeWorkExperience(
            document_id=ext_id,
            job_title="Senior Software Engineer",
            company="Emirates NBD",
            location="Dubai, UAE",
            start_date=date(2020, 3, 1),
            is_current=True,
        )
        ok("ResumeWorkExperience model instantiation")
    except Exception as e:
        fail("ResumeWorkExperience model instantiation", str(e))

    try:
        assets = AssetsLiabilitiesData(
            document_id=doc_id,
            applicant_name="Ahmed Hassan Al-Mansouri",
            statement_date=date(2025, 1, 31),
            total_assets=Decimal("350000.00"),
            total_liabilities=Decimal("120000.00"),
            net_worth=Decimal("230000.00"),
            extraction_confidence=0.91,
        )
        ok("AssetsLiabilitiesData model instantiation")
    except Exception as e:
        fail("AssetsLiabilitiesData model instantiation", str(e))

    try:
        form_data = ApplicationFormData(
            document_id=doc_id,
            applicant_name="Ahmed Hassan Al-Mansouri",
            identity_number="784-1990-1234567-1",
            date_of_birth=date(1990, 5, 15),
            nationality="Emirati",
            contact_phone="+971501234567",
            address={"emirate": "Dubai", "area": "Dubai Marina"},
            employment_status="Employed",
            total_monthly_income=Decimal("18000.00"),
            is_declaration_signed=True,
            declaration_date=date(2025, 7, 20),
            extraction_confidence=0.94,
        )
        ok("ApplicationFormData model instantiation")
    except Exception as e:
        fail("ApplicationFormData model instantiation", str(e))

    try:
        ext_field = DocumentExtractionField(
            document_id=doc_id,
            field_name="identity_number",
            field_value="784-1990-1234567-1",
            confidence=0.98,
            source_page=1,
        )
        ok("DocumentExtractionField model instantiation")
    except Exception as e:
        fail("DocumentExtractionField model instantiation", str(e))

    try:
        cross_val = CrossDocumentValidation(
            applicant_id=app_id,
            validation_type="identity_check",
            source_documents=[doc_id],
            source_document_types=["emirates_id"],
            status="passed",
            confidence_score=0.96,
            findings={"match": True, "source": "emirates_id"},
        )
        ok("CrossDocumentValidation model instantiation")
    except Exception as e:
        fail("CrossDocumentValidation model instantiation", str(e))

    try:
        audit_log = AuditLog(
            document_id=doc_id,
            action="uploaded",
            performed_by="ahmed@example.ae",
            performed_by_type="user",
            hash=hashlib.sha256(b"audit_001").hexdigest(),
        )
        ok("AuditLog model instantiation")
    except Exception as e:
        fail("AuditLog model instantiation", str(e))

    try:
        proc_queue = ProcessingQueue(
            document_id=doc_id,
            stage="extraction",
            status="pending",
            priority=1,
        )
        ok("ProcessingQueue model instantiation")
    except Exception as e:
        fail("ProcessingQueue model instantiation", str(e))

    # ───────────────────────────────────────────────────────
    # 2. Constraint violation tests
    # ───────────────────────────────────────────────────────
    print("\n[2/5] Constraint Violation Tests")

    async with session_factory() as session:
        # Test invalid document_type
        try:
            bad_doc = Document(
                applicant_id=app_id,
                document_type="invalid_type",
                file_path="/tmp/test.pdf",
                file_hash="sha256:abc",
            )
            session.add(bad_doc)
            await session.flush()
            fail("chk_document_type", "Should have raised constraint violation")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("chk_document_type constraint (rejects invalid type)")

        # Test invalid confidence > 1.0
        try:
            bad_doc2 = Document(
                applicant_id=app_id,
                document_type="emirates_id",
                file_path="/tmp/test2.pdf",
                file_hash="sha256:def",
                overall_confidence=1.5,
            )
            session.add(bad_doc2)
            await session.flush()
            fail("chk_overall_confidence", "Should have rejected confidence > 1.0")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("chk_overall_confidence constraint (rejects > 1.0)")

        # Test invalid gender
        try:
            bad_eid = EmiratesIDData(
                document_id=doc_id,
                identity_number="784-1990-1234567-2",
                full_name_en="Test User",
                nationality="Emirati",
                date_of_birth=date(1990, 1, 1),
                gender="Other",
                expiry_date=date(2028, 1, 1),
            )
            session.add(bad_eid)
            await session.flush()
            fail("chk_emirates_id_gender", "Should have rejected invalid gender")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("chk_emirates_id_gender constraint (rejects invalid gender)")

        # Test invalid credit score
        try:
            bad_cr = CreditReportData(
                document_id=doc_id,
                cb_subject_id="CB999",
                identity_number="784-1990-1234567-3",
                full_name="Test User",
                credit_score=999,
                risk_band="High",
                total_active_accounts=1,
                total_closed_accounts=0,
                total_outstanding_balance=Decimal("0.00"),
            )
            session.add(bad_cr)
            await session.flush()
            fail("chk_credit_score_range", "Should have rejected credit_score > 900")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("chk_credit_score_range constraint (rejects > 900)")

        # Test invalid transaction type
        try:
            bad_txn = BankStatementTransaction(
                document_id=ext_id,
                transaction_hash=hashlib.sha256(b"bad_txn").hexdigest(),
                transaction_date=date(2025, 1, 1),
                description="Test",
                amount=Decimal("100.00"),
                transaction_type="transfer",
            )
            session.add(bad_txn)
            await session.flush()
            fail("chk_bank_txn_type", "Should have rejected invalid txn type")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("chk_bank_txn_type constraint (rejects invalid type)")

        # Test invalid audit performed_by_type
        try:
            bad_audit = AuditLog(
                document_id=doc_id,
                action="test",
                performed_by="system",
                performed_by_type="hacker",
                hash=hashlib.sha256(b"bad").hexdigest(),
            )
            session.add(bad_audit)
            await session.flush()
            fail("chk_audit_performed_by_type", "Should have rejected invalid type")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("chk_audit_performed_by_type constraint (rejects invalid type)")

    # ───────────────────────────────────────────────────────
    # 3. Repository CRUD tests
    # ───────────────────────────────────────────────────────
    print("\n[3/5] Repository CRUD Tests")

    async with session_factory() as session:
        # ApplicantRepository
        try:
            app_repo = ApplicantRepository(session)
            new_app = await app_repo.create(identity_number="784-2000-9876543-2")
            assert new_app.id is not None
            ok("ApplicantRepository.create()")

            fetched = await app_repo.get_by_id(new_app.id)
            assert fetched is not None
            ok("ApplicantRepository.get_by_id()")

            by_identity = await app_repo.get_by_identity_number("784-2000-9876543-2")
            assert by_identity is not None
            ok("ApplicantRepository.get_by_identity_number()")

            by_identity.full_name = "Fatima Al-Zaabi"
            updated = await app_repo.update(by_identity)
            assert updated.full_name == "Fatima Al-Zaabi"
            ok("ApplicantRepository.update()")
        except Exception as e:
            fail("ApplicantRepository CRUD", str(e))
            await session.rollback()

        # ApplicationRepository
        try:
            app_repo2 = ApplicantRepository(session)
            app_for_application = await app_repo2.create(identity_number="784-2000-1111111-1")

            appl_repo = ApplicationRepository(session)
            new_appl = await appl_repo.create(applicant_id=app_for_application.id)
            assert new_appl.id is not None
            ok("ApplicationRepository.create()")

            fetched_appl = await appl_repo.get_by_id(new_appl.id)
            assert fetched_appl is not None
            ok("ApplicationRepository.get_by_id()")

            latest = await appl_repo.get_latest_by_applicant(app_for_application.id)
            assert latest is not None
            ok("ApplicationRepository.get_latest_by_applicant()")

            latest.status = "completed"
            updated_appl = await appl_repo.update(latest)
            assert updated_appl.status == "completed"
            ok("ApplicationRepository.update()")
        except Exception as e:
            fail("ApplicationRepository CRUD", str(e))
            await session.rollback()

        # DocumentRepository
        try:
            doc_repo = DocumentRepository(session)
            new_doc = await doc_repo.create(
                applicant_id=app_for_application.id,
                document_type="bank_statement",
                processing_status="uploaded",
                file_path="/uploads/bank_stmt_001.pdf",
                file_format="pdf",
                file_size_bytes=1024000,
                file_hash="sha256:" + hashlib.sha256(b"bank_stmt").hexdigest(),
            )
            assert new_doc.id is not None
            ok("DocumentRepository.create()")

            fetched_doc = await doc_repo.get_by_id(new_doc.id)
            assert fetched_doc is not None
            ok("DocumentRepository.get_by_id()")

            by_applicant = await doc_repo.get_by_applicant(app_for_application.id)
            assert len(by_applicant) > 0
            ok("DocumentRepository.get_by_applicant()")

            by_type = await doc_repo.get_by_applicant_and_type(
                app_for_application.id, "bank_statement"
            )
            assert len(by_type) > 0
            ok("DocumentRepository.get_by_applicant_and_type()")

            updated_doc = await doc_repo.update_status(
                new_doc.id,
                processing_status="extracting",
                extraction_status="success",
            )
            assert updated_doc.processing_status == "extracting"
            ok("DocumentRepository.update_status()")
        except Exception as e:
            fail("DocumentRepository CRUD", str(e))
            await session.rollback()

        # EmiratesIDRepository
        try:
            eid_repo = EmiratesIDRepository(session)
            new_eid = await eid_repo.create(
                document_id=new_doc.id,
                identity_number="784-2000-9876543-2",
                full_name_en="Fatima Al-Zaabi",
                nationality="Emirati",
                date_of_birth=date(2000, 3, 10),
                gender="Female",
                expiry_date=date(2030, 3, 9),
            )
            assert new_eid.id is not None
            ok("EmiratesIDRepository.create()")

            by_doc = await eid_repo.get_by_document_id(new_doc.id)
            assert by_doc is not None
            ok("EmiratesIDRepository.get_by_document_id()")

            upserted = await eid_repo.upsert(new_doc.id, full_name_en="Fatima Updated")
            assert upserted.full_name_en == "Fatima Updated"
            ok("EmiratesIDRepository.upsert() (update path)")
        except Exception as e:
            fail("EmiratesIDRepository CRUD", str(e))
            await session.rollback()

        # BankStatementRepository
        try:
            bs_repo = BankStatementRepository(session)
            new_bs = await bs_repo.create(
                document_id=new_doc.id,
                bank_name="FAB",
                account_holder_name="Fatima Al-Zaabi",
                account_number="AE123456789012345678901",
                currency="AED",
                statement_period_start=date(2025, 1, 1),
                statement_period_end=date(2025, 1, 31),
                opening_balance=Decimal("30000.00"),
                closing_balance=Decimal("28000.00"),
                total_debits=Decimal("10000.00"),
                total_credits=Decimal("8000.00"),
                transactions=[],
                transaction_count=0,
            )
            assert new_bs.id is not None
            ok("BankStatementRepository.create()")

            by_doc = await bs_repo.get_by_document_id(new_doc.id)
            assert by_doc is not None
            ok("BankStatementRepository.get_by_document_id()")
        except Exception as e:
            fail("BankStatementRepository CRUD", str(e))
            await session.rollback()

        # CreditReportRepository
        try:
            cr_repo = CreditReportRepository(session)
            new_cr = await cr_repo.create(
                document_id=new_doc.id,
                cb_subject_id="CB987654",
                identity_number="784-2000-9876543-2",
                full_name="Fatima Al-Zaabi",
                credit_score=750,
                risk_band="Low",
                total_active_accounts=2,
                total_closed_accounts=1,
                total_outstanding_balance=Decimal("30000.00"),
            )
            assert new_cr.id is not None
            ok("CreditReportRepository.create()")

            by_doc = await cr_repo.get_by_document_id(new_doc.id)
            assert by_doc is not None
            ok("CreditReportRepository.get_by_document_id()")
        except Exception as e:
            fail("CreditReportRepository CRUD", str(e))
            await session.rollback()

        # ResumeRepository
        try:
            res_repo = ResumeRepository(session)
            new_res = await res_repo.create(
                document_id=new_doc.id,
                full_name="Fatima Al-Zaabi",
                work_experience={},
                total_positions=2,
            )
            assert new_res.id is not None
            ok("ResumeRepository.create()")

            by_doc = await res_repo.get_by_document_id(new_doc.id)
            assert by_doc is not None
            ok("ResumeRepository.get_by_document_id()")
        except Exception as e:
            fail("ResumeRepository CRUD", str(e))
            await session.rollback()

        # AssetsLiabilitiesRepository
        try:
            al_repo = AssetsLiabilitiesRepository(session)
            new_al = await al_repo.create(
                document_id=new_doc.id,
                applicant_name="Fatima Al-Zaabi",
                statement_date=date(2025, 1, 31),
                total_assets=Decimal("500000.00"),
                total_liabilities=Decimal("200000.00"),
                net_worth=Decimal("300000.00"),
            )
            assert new_al.id is not None
            ok("AssetsLiabilitiesRepository.create()")

            by_doc = await al_repo.get_by_document_id(new_doc.id)
            assert by_doc is not None
            ok("AssetsLiabilitiesRepository.get_by_document_id()")
        except Exception as e:
            fail("AssetsLiabilitiesRepository CRUD", str(e))
            await session.rollback()

        # ApplicationFormRepository
        try:
            af_repo = ApplicationFormRepository(session)
            new_af = await af_repo.create(
                document_id=new_doc.id,
                applicant_name="Fatima Al-Zaabi",
                identity_number="784-2000-9876543-2",
                date_of_birth=date(2000, 3, 10),
                nationality="Emirati",
                contact_phone="+971509876543",
                address={"emirate": "Abu Dhabi"},
                employment_status="Employed",
                total_monthly_income=Decimal("15000.00"),
            )
            assert new_af.id is not None
            ok("ApplicationFormRepository.create()")

            by_doc = await af_repo.get_by_document_id(new_doc.id)
            assert by_doc is not None
            ok("ApplicationFormRepository.get_by_document_id()")
        except Exception as e:
            fail("ApplicationFormRepository CRUD", str(e))
            await session.rollback()

        # AuditLogRepository
        try:
            audit_repo = AuditLogRepository(session)
            new_audit = await audit_repo.create(
                document_id=new_doc.id,
                action="uploaded",
                performed_by="fatima@example.ae",
                performed_by_type="user",
                hash=hashlib.sha256(b"audit_test").hexdigest(),
            )
            assert new_audit.id is not None
            ok("AuditLogRepository.create()")

            by_doc = await audit_repo.get_by_document(new_doc.id)
            assert len(by_doc) > 0
            ok("AuditLogRepository.get_by_document()")

            chain_valid = await audit_repo.verify_chain(new_doc.id)
            assert chain_valid is True
            ok("AuditLogRepository.verify_chain()")
        except Exception as e:
            fail("AuditLogRepository CRUD", str(e))
            await session.rollback()

        # ProcessingQueueRepository
        try:
            pq_repo = ProcessingQueueRepository(session)
            new_pq = await pq_repo.create(
                document_id=new_doc.id,
                stage="extraction",
                status="pending",
                priority=5,
            )
            assert new_pq.id is not None
            ok("ProcessingQueueRepository.create()")

            by_doc = await pq_repo.get_by_document(new_doc.id)
            assert len(by_doc) > 0
            ok("ProcessingQueueRepository.get_by_document()")

            pending = await pq_repo.get_pending_queue_items()
            assert len(pending) > 0
            ok("ProcessingQueueRepository.get_pending_queue_items()")

            new_pq.status = "processing"
            updated_pq = await pq_repo.update(new_pq)
            assert updated_pq.status == "processing"
            ok("ProcessingQueueRepository.update()")
        except Exception as e:
            fail("ProcessingQueueRepository CRUD", str(e))
            await session.rollback()

        # CrossDocumentValidationRepository
        try:
            cv_repo = CrossDocumentValidationRepository(session)
            new_cv = await cv_repo.create(
                applicant_id=app_for_application.id,
                validation_type="income_verification",
                source_documents=[new_doc.id],
                source_document_types=["bank_statement"],
                status="passed",
                confidence_score=0.92,
                findings={"income_verified": True, "amount": "15000"},
            )
            assert new_cv.id is not None
            ok("CrossDocumentValidationRepository.create()")

            by_id = await cv_repo.get_by_id(new_cv.id)
            assert by_id is not None
            ok("CrossDocumentValidationRepository.get_by_id()")

            by_app = await cv_repo.get_by_applicant(app_for_application.id)
            assert len(by_app) > 0
            ok("CrossDocumentValidationRepository.get_by_applicant()")

            resolved = await cv_repo.resolve(new_cv.id, "admin", "Verified manually")
            assert resolved.is_resolved is True
            ok("CrossDocumentValidationRepository.resolve()")

            unresolved = await cv_repo.get_unresolved()
            ok("CrossDocumentValidationRepository.get_unresolved()")
        except Exception as e:
            fail("CrossDocumentValidationRepository CRUD", str(e))
            await session.rollback()

        # Commit all CRUD operations so they're visible to subsequent tests
        await session.commit()

    # ───────────────────────────────────────────────────────
    # 4. Relationship tests
    # ───────────────────────────────────────────────────────
    print("\n[4/5] Relationship Tests")

    async with session_factory() as session:
        try:
            result = await session.execute(
                select(Applicant).where(Applicant.identity_number == "784-2000-1111111-1")
            )
            app_entity = result.scalar_one_or_none()
            if app_entity is None:
                # Check what applicants exist
                all_apps = await session.execute(select(Applicant))
                existing = all_apps.scalars().all()
                fail("Relationship tests", f"Applicant not found. Existing applicants: {[(a.id, a.identity_number) for a in existing]}")
            else:
                ok("Applicant lookup by identity_number")

                result = await session.execute(
                    select(Application).where(Application.applicant_id == app_entity.id).limit(1)
                )
                appl_entity = result.scalar_one_or_none()
                if appl_entity is None:
                    fail("Relationship tests", "Application not found for applicant")
                else:
                    ok("Application.applicant relationship")
        except Exception as e:
            fail("Relationship tests", f"{type(e).__name__}: {e}")

    # ───────────────────────────────────────────────────────
    # 5. Unique constraint tests
    # ───────────────────────────────────────────────────────
    print("\n[5/5] Unique Constraint Tests")

    async with session_factory() as session:
        try:
            dup_app = Applicant(identity_number="784-2000-1111111-1")
            session.add(dup_app)
            await session.flush()
            await session.rollback()
            fail("Applicant.identity_number unique", "Should have raised unique violation")
        except Exception as e:
            await session.rollback()
            ok("Applicant.identity_number unique constraint")

        try:
            dup_eid = EmiratesIDData(
                document_id=new_doc.id,
                identity_number="784-2000-9876543-2",
                full_name_en="Duplicate",
                nationality="Emirati",
                date_of_birth=date(2000, 1, 1),
                gender="Male",
                expiry_date=date(2030, 1, 1),
            )
            session.add(dup_eid)
            await session.flush()
            fail("EmiratesIDData.identity_number unique", "Should have raised unique violation")
            await session.rollback()
        except Exception:
            await session.rollback()
            ok("EmiratesIDData.identity_number unique constraint")

    await engine.dispose()

    # ───────────────────────────────────────────────────────
    # Summary
    # ───────────────────────────────────────────────────────
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
    print("=" * 60)

    if errors:
        print("\nFailures:")
        for name, detail in errors:
            print(f"  - {name}: {detail}")

    return failed == 0


if __name__ == "__main__":
    result = asyncio.run(run_tests())
    sys.exit(0 if result else 1)
