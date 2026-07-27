"""Browser-based E2E test using Playwright - v7 with document extraction debugging."""
import asyncio
import sys
import time
import traceback
from pathlib import Path

import structlog

sys.path.insert(0, ".")
from src.infrastructure.observability.logging import configure_logging
from src.utils.emirates_id import luhn_check_digit
import random

configure_logging()
logger = structlog.get_logger(__name__)

random.seed(776655)
year = random.randint(1970, 2000)
seq = random.randint(1000000, 9999999)
digits = f"784{year}{seq}"
check = luhn_check_digit(digits)
eid_raw = f"{digits}{check}"
eid_formatted = f"{eid_raw[:3]}-{eid_raw[3:7]}-{eid_raw[7:14]}-{eid_raw[14]}"
logger.info("browser_e2e_test_started")


async def test_browser_flow():
    from playwright.async_api import async_playwright

    t0 = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        logger.info("browser_navigating_to_streamlit")
        await page.goto("http://localhost:8501")
        await asyncio.sleep(5)

        await page.screenshot(path="screenshots/01_landing.png")
        logger.info("browser_screenshot_taken", path="screenshots/01_landing.png")

        # Fill Emirates ID
        eid_input = page.locator('input[placeholder*="784"]')
        await eid_input.wait_for(state="visible", timeout=10000)
        await eid_input.fill(eid_formatted)
        logger.info("browser_emirates_id_filled")
        await asyncio.sleep(1)

        # Click Continue
        continue_btn = page.get_by_role("button", name="Continue")
        await continue_btn.click()
        logger.info("browser_continue_clicked")
        await asyncio.sleep(5)

        logger.info("browser_url_after_click", url=page.url)

        # Check for sidebar nav
        app_link = page.locator('a[href="/application"]')
        if await app_link.count() > 0:
            logger.info("browser_application_nav_found")
            await app_link.first.click()
            await asyncio.sleep(5)
            await page.screenshot(path="screenshots/02_after_nav.png", full_page=True)
            logger.info("browser_screenshot_taken", path="screenshots/02_after_nav.png", url=page.url)

        content = await page.content()
        if "chat" in content.lower() or "message" in content.lower():
            logger.info("browser_chat_interface_detected")
        else:
            logger.warning("browser_chat_interface_not_detected")

        # API-based testing
        logger.info("browser_api_pipeline_test_started")
        import requests

        t1 = time.time()
        resp = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            json={"emirates_id": eid_formatted},
        )
        duration_ms = (time.time() - t1) * 1000
        logger.info("browser_api_auth", status_code=resp.status_code, duration_ms=round(duration_ms, 1))
        if resp.status_code != 200:
            logger.error("browser_api_auth_failed", error=resp.text[:500])
            await browser.close()
            return

        data = resp.json()
        app_id = data["application_id"]
        logger.info("browser_api_auth_ok", application_id=app_id, phase=data["current_phase"])

        # Navigate to application page
        await page.goto(f"http://localhost:8501/application")
        await asyncio.sleep(5)
        await page.screenshot(path="screenshots/03_app_page.png", full_page=True)
        logger.info("browser_screenshot_taken", path="screenshots/03_app_page.png", url=page.url)

        # Phase 1: Intake
        logger.info("browser_phase1_intake_sending")
        t2 = time.time()
        resp = requests.post(
            f"http://localhost:8000/api/v1/applications/{app_id}/chat",
            data={
                "text": "I am applying for financial support. I am divorced, have 2 children, employed, monthly salary 15000 AED, renting in Abu Dhabi."
            },
            timeout=60,
        )
        duration_ms = (time.time() - t2) * 1000
        logger.info("browser_phase1_intake_completed", status_code=resp.status_code, duration_ms=round(duration_ms, 1))
        if resp.status_code == 200:
            r = resp.json()
            logger.info("browser_phase1_intake_response", phase=r.get("phase"))

        # Phase 2: Upload documents
        logger.info("browser_phase2_uploading")
        profile_dir = Path("data/test_applicants/divorced_employed_good_credit")
        files = []
        for fname in [
            "emirates_id_front.png",
            "emirates_id_back.png",
            "bank_statement.pdf",
            "credit_report.pdf",
            "application_form.png",
        ]:
            fpath = profile_dir / fname
            if fpath.exists():
                mime = "image/png" if fname.endswith(".png") else "application/pdf"
                files.append(("files", (fname, open(fpath, "rb"), mime)))

        t3 = time.time()
        resp = requests.post(
            f"http://localhost:8000/api/v1/applications/{app_id}/chat",
            data={"text": "Here are my documents"},
            files=files,
            timeout=120,
        )
        duration_ms = (time.time() - t3) * 1000
        for _, (_, fh, _) in files:
            fh.close()
        logger.info("browser_phase2_upload_completed", status_code=resp.status_code, duration_ms=round(duration_ms, 1))
        if resp.status_code == 200:
            r = resp.json()
            docs = r.get("uploaded_documents", [])
            logger.info("browser_phase2_response", phase=r.get("phase"), document_types=[d.get("doc_type") for d in docs])
            if r.get("decision"):
                logger.info("browser_phase2_decision", decision=r["decision"])
            if r.get("extracted_data"):
                for doc_type, edata in r.get("extracted_data", {}).items():
                    logger.info("browser_phase2_extraction", doc_type=doc_type, confidence=edata.get("extraction_confidence", "N/A"))

        # Phase 3-5: Poll for decision
        logger.info("browser_phase3_4_5_polling")
        for i in range(30):
            await asyncio.sleep(2)
            resp = requests.get(f"http://localhost:8000/api/v1/applications/{app_id}")
            if resp.status_code == 200:
                app = resp.json()
                decision = app.get("decision")
                score = app.get("eligibility_score")
                phase = app.get("current_phase")
                if i % 5 == 0 or decision:
                    logger.info("browser_phase3_4_5_poll", poll=i + 1, phase=phase, decision=decision, score=score)
                if decision:
                    logger.info("browser_decision_reached", decision=decision, score=score)
                    break

        await page.screenshot(path="screenshots/04_final.png", full_page=True)
        logger.info("browser_screenshot_taken", path="screenshots/04_final.png")

        logger.info("browser_test_complete")
        await asyncio.sleep(3)
        await browser.close()
    total_duration_ms = (time.time() - t0) * 1000
    logger.info("browser_e2e_test_completed", total_duration_ms=round(total_duration_ms, 1))


if __name__ == "__main__":
    Path("screenshots").mkdir(exist_ok=True)
    try:
        asyncio.run(test_browser_flow())
    except Exception as e:
        logger.exception("browser_e2e_test_failed", error=str(e))
