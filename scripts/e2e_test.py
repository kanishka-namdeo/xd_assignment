"""End-to-end test script for the 7-phase applicant flow."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import structlog

from src.infrastructure.observability.logging import configure_logging

BASE_URL = "http://127.0.0.1:8000/api/v1"
PROFILE_DIR = Path("data/test_applicants/divorced_employed_good_credit")

logger = structlog.get_logger(__name__)


async def main() -> None:
    configure_logging()
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Auth
        logger.info("e2e_test_started", base_url=BASE_URL, profile_dir=str(PROFILE_DIR))

        logger.info("auth_phase_started")
        t0 = time.monotonic()
        profile = json.loads((PROFILE_DIR / "profile.json").read_text(encoding="utf-8"))
        identity_number = profile["applicant"]["identity_number"]

        r = await client.post(f"{BASE_URL}/auth/login", json={"emirates_id": identity_number})
        duration_ms = (time.monotonic() - t0) * 1000
        auth_data = r.json()
        app_id = auth_data.get("application_id")

        logger.info(
            "auth_phase_completed",
            status_code=r.status_code,
            application_id=app_id,
            duration_ms=round(duration_ms, 1),
        )

        if r.status_code != 200:
            logger.error("auth_failed", status_code=r.status_code, response=auth_data)
            return

        logger.info(
            "auth_success",
            application_id=app_id,
            current_phase=auth_data.get("current_phase"),
        )

        # Step 2: Chat - intake
        logger.info("intake_phase_started", application_id=app_id)
        t0 = time.monotonic()

        intake_text = (
            f"My name is {profile['applicant']['full_name_en']}, "
            f"DOB {profile['applicant']['date_of_birth']}, "
            f"nationality {profile['applicant']['nationality']}, "
            f"phone {profile['applicant']['contact_phone']}, "
            f"email {profile['applicant']['contact_email']}, "
            f"marital status {profile['applicant']['marital_status']}, "
            f"family size {profile['applicant']['family_size']}, "
            f"employment {profile['applicant']['employment_status']}, "
            f"employer {profile['applicant']['employer_name']}, "
            f"occupation {profile['applicant']['occupation']}, "
            f"housing {profile['applicant']['housing_status']}, "
            f"support category {profile['applicant']['support_category']}"
        )

        r = await client.post(
            f"{BASE_URL}/applications/{app_id}/chat",
            data={"text": intake_text},
        )
        duration_ms = (time.monotonic() - t0) * 1000

        if r.status_code == 200:
            chat_data = r.json()
            logger.info(
                "intake_phase_completed",
                application_id=app_id,
                status_code=r.status_code,
                phase=chat_data.get("phase"),
                decision=chat_data.get("decision"),
                has_interrupt=chat_data.get("interrupt") is not None,
                duration_ms=round(duration_ms, 1),
            )
        else:
            logger.error(
                "intake_failed",
                application_id=app_id,
                status_code=r.status_code,
                error=r.text[:500],
                duration_ms=round(duration_ms, 1),
            )

        # Step 3: Upload documents
        logger.info("document_upload_phase_started", application_id=app_id)
        t0 = time.monotonic()

        doc_files = {
            "emirates_id_front.png": "image/png",
            "bank_statement.pdf": "application/pdf",
            "credit_report.pdf": "application/pdf",
            "application_form.png": "image/png",
        }
        files = []
        for fname, ftype in doc_files.items():
            fpath = PROFILE_DIR / fname
            if fpath.exists():
                files.append(("files", (fname, fpath.read_bytes(), ftype)))
            else:
                logger.warning("document_missing", application_id=app_id, file_name=fname)

        if files:
            r = await client.post(
                f"{BASE_URL}/applications/{app_id}/chat",
                data={"text": "Here are my supporting documents."},
                files=files,
            )
            duration_ms = (time.monotonic() - t0) * 1000

            if r.status_code == 200:
                chat_data = r.json()
                logger.info(
                    "document_upload_phase_completed",
                    application_id=app_id,
                    status_code=r.status_code,
                    phase=chat_data.get("phase"),
                    documents_count=len(chat_data.get("uploaded_documents", [])),
                    decision=chat_data.get("decision"),
                    duration_ms=round(duration_ms, 1),
                )
            else:
                logger.error(
                    "document_upload_failed",
                    application_id=app_id,
                    status_code=r.status_code,
                    error=r.text[:500],
                    duration_ms=round(duration_ms, 1),
                )

        logger.info("e2e_test_completed", application_id=app_id)


if __name__ == "__main__":
    asyncio.run(main())
