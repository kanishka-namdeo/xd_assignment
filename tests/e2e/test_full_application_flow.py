"""End-to-end test for full application flow."""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.session import Base
from src.main import app


def check_db_available():
    """Check if database is available."""
    import asyncio
    from src.config import settings
    try:
        async def _check():
            engine = create_async_engine(settings.DATABASE_URL)
            async with engine.begin() as conn:
                await conn.execute("SELECT 1")
            await engine.dispose()
        asyncio.run(_check())
        return True
    except Exception:
        return False


db_available = check_db_available()
pytestmark = pytest.mark.skipif(not db_available, reason="Database not available")


@pytest_asyncio.fixture
async def db_session():
    """Create test database session."""
    from src.config import settings
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_full_application_flow(db_session: AsyncSession):
    """Test complete application flow from creation to decision."""
    from src.infrastructure.db.models.applicant import Applicant

    applicant_id = uuid.uuid4()
    applicant = Applicant(
        id=applicant_id,
        identity_number="784-1990-1234567-8",
        full_name="Ahmed Hassan",
        date_of_birth=date(1990, 1, 15),
        nationality="UAE",
        phone="+971501234567",
        email="ahmed.hassan@email.com",
    )
    db_session.add(applicant)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create application
        response = await client.post(
            "/api/v1/applications",
            json={"applicant_id": str(applicant_id), "support_category": "divorced"},
        )
        assert response.status_code == 201, response.text
        app_data = response.json()
        app_id = app_data["id"]

        # 2. Upload documents
        for doc_type, filename, content_type in [
            ("emirates_id", "emirates_id.png", "image/png"),
            ("bank_statement", "bank_statement.pdf", "application/pdf"),
            ("credit_report", "credit_report.pdf", "application/pdf"),
        ]:
            response = await client.post(
                f"/api/v1/applications/{app_id}/documents",
                files={"file": (filename, b"fake content", content_type)},
                data={"document_type": doc_type},
            )
            assert response.status_code == 201, f"Failed for {doc_type}: {response.text}"

        # 3. List documents
        response = await client.get(f"/api/v1/applications/{app_id}/documents")
        assert response.status_code == 200
        docs_data = response.json()
        assert docs_data["total"] >= 3

        # 4. Get application
        response = await client.get(f"/api/v1/applications/{app_id}")
        assert response.status_code == 200

        # 5. Update status
        response = await client.patch(
            f"/api/v1/applications/{app_id}/status",
            json={"status": "in_progress", "phase": "processing"},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_application_not_found():
    """Test 404 for non-existent application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/applications/{fake_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_eligibility_not_computed():
    """Test 404 for eligibility not yet computed."""
    from src.infrastructure.db.models.applicant import Applicant

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create applicant + application
        applicant_id = uuid.uuid4()
        applicant = Applicant(
            id=applicant_id,
            identity_number="784-1990-1234567-8",
            full_name="Test User",
            date_of_birth=date(1990, 1, 1),
            nationality="UAE",
            phone="+971501234567",
            email="test.user@email.com",
        )
        # Use a separate session for this test
        from src.config import settings
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(applicant)
            await session.commit()

            response = await client.post(
                "/api/v1/applications",
                json={"applicant_id": str(applicant_id), "support_category": "divorced"},
            )
            assert response.status_code == 201
            app_id = response.json()["id"]

        await engine.dispose()

        # Try to get eligibility (not computed yet)
        response = await client.get(f"/api/v1/eligibility/{app_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_application_status_transitions():
    """Test application status transitions through phases."""
    from src.infrastructure.db.models.applicant import Applicant
    from src.config import settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        applicant_id = uuid.uuid4()
        applicant = Applicant(
            id=applicant_id,
            identity_number="784-1990-1234567-8",
            full_name="Test User",
            date_of_birth=date(1990, 1, 1),
            nationality="UAE",
            phone="+971501234567",
            email="test.user@email.com",
        )
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(applicant)
            await session.commit()

            response = await client.post(
                "/api/v1/applications",
                json={"applicant_id": str(applicant_id), "support_category": "divorced"},
            )
            assert response.status_code == 201
            app_id = response.json()["id"]

        await engine.dispose()

        # Transition through phases
        for status_val, phase in [
            ("in_progress", "document_collection"),
            ("in_progress", "processing"),
            ("in_progress", "review"),
            ("approved", "decision"),
        ]:
            response = await client.patch(
                f"/api/v1/applications/{app_id}/status",
                json={"status": status_val, "phase": phase},
            )
            assert response.status_code == 200, f"Failed at {phase}: {response.text}"
            app_data = response.json()
            assert app_data["status"] == status_val
            assert app_data["current_phase"] == phase
