"""Capture UI screenshots of the 7-phase applicant flow."""

import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright

SCREENSHOT_DIR = Path("docs/images")
FRONTEND_URL = "http://localhost:8501"
BACKEND_URL = "http://localhost:8000"

# Test applicant data (fresh account)
TEST_EMIRATES_ID = "784-1996-7430124-9"
TEST_APPLICANT_INFO = {
    "name": "خليل الصالح",
    "dob": "1996-03-14",
    "marital_status": "married",
    "children": "2",
    "residency": "30",
    "employment": "unemployed",
    "employer": "N/A",
    "salary": "990",
    "support_category": "abandoned",
}


async def wait_for_element(page, selector, timeout=10000):
    """Wait for element to be visible."""
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except Exception:
        return False


async def capture_screenshot(page, name, description):
    """Capture and save a screenshot."""
    screenshot_path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"[OK] Captured {description}: {screenshot_path}")
    return screenshot_path


async def main():
    """Capture screenshots of the full 7-phase flow."""
    print("Starting UI screenshot capture...")
    print(f"Frontend: {FRONTEND_URL}")
    print(f"Backend: {BACKEND_URL}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            # Phase 0: Landing Page
            print("Phase 0: Capturing landing page...")
            await page.goto(FRONTEND_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            await capture_screenshot(page, "01-landing", "Landing page")

            # Phase 1: Authentication
            print("\nPhase 1: Capturing authentication...")
            emirates_id_input = page.locator('input[placeholder*="Emirates ID"]')
            if await emirates_id_input.is_visible():
                await emirates_id_input.fill(TEST_EMIRATES_ID)
                await page.wait_for_timeout(500)

                # Click Continue button
                continue_button = page.locator('button:has-text("Continue")')
                if await continue_button.is_visible():
                    await continue_button.click()
                    await page.wait_for_timeout(3000)
                    await capture_screenshot(page, "02-authentication", "Authentication phase")

            # Phase 2: Intake
            print("\nPhase 2: Capturing intake phase...")
            await page.wait_for_timeout(2000)
            await capture_screenshot(page, "03-intake", "Intake phase")

            # Send intake information via chat
            chat_input = page.locator('textarea[placeholder*="Type your message"]')
            if await chat_input.is_visible():
                intake_message = (
                    f"My name is {TEST_APPLICANT_INFO['name']}. "
                    f"I was born on {TEST_APPLICANT_INFO['dob']}. "
                    f"I am {TEST_APPLICANT_INFO['marital_status']} with {TEST_APPLICANT_INFO['children']} children. "
                    f"I have been a UAE resident for {TEST_APPLICANT_INFO['residency']} years. "
                    f"I am currently {TEST_APPLICANT_INFO['employment']} at {TEST_APPLICANT_INFO['employer']} "
                    f"with a monthly salary of AED {TEST_APPLICANT_INFO['salary']}. "
                    f"I am applying for {TEST_APPLICANT_INFO['support_category']} support."
                )
                await chat_input.fill(intake_message)
                await page.wait_for_timeout(500)

                # Send message
                send_button = page.locator('button[aria-label="Send"]')
                if await send_button.is_visible():
                    await send_button.click()
                    await page.wait_for_timeout(5000)
                    await capture_screenshot(page, "04-intake-complete", "Intake complete")

            # Phase 3: Document Collection
            print("\nPhase 3: Capturing document collection...")
            await page.wait_for_timeout(2000)
            await capture_screenshot(page, "05-document-collection", "Document collection phase")

            # Upload documents
            test_docs_dir = Path("data/fresh_accounts/applicant_550353")
            if test_docs_dir.exists():
                file_input = page.locator('input[type="file"]')
                if await file_input.is_visible():
                    documents = [
                        "emirates_id_front.png",
                        "emirates_id_back.png",
                        "bank_statement.pdf",
                        "credit_report.pdf",
                        "application_form.png",
                    ]
                    for doc in documents:
                        doc_path = test_docs_dir / doc
                        if doc_path.exists():
                            await file_input.set_input_files(str(doc_path))
                            await page.wait_for_timeout(3000)
                    await capture_screenshot(page, "06-documents-uploaded", "Documents uploaded")

            # Phase 4: Processing
            print("\nPhase 4: Capturing processing phase...")
            await page.wait_for_timeout(5000)
            await capture_screenshot(page, "07-processing", "Processing phase")

            # Phase 5: Review
            print("\nPhase 5: Capturing review phase...")
            await page.wait_for_timeout(3000)
            await capture_screenshot(page, "08-review", "Review phase")

            # Phase 6: Decision
            print("\nPhase 6: Capturing decision phase...")
            await page.wait_for_timeout(3000)
            await capture_screenshot(page, "09-decision", "Decision phase")

            # Phase 7: Enablement
            print("\nPhase 7: Capturing enablement phase...")
            await page.wait_for_timeout(2000)
            await capture_screenshot(page, "10-enablement", "Enablement phase")

            print("\n[OK] Screenshot capture complete!")
            print(f"Screenshots saved to: {SCREENSHOT_DIR.absolute()}")

        except Exception as e:
            print(f"\n[ERROR] Error during screenshot capture: {e}")
            # Capture error state
            await capture_screenshot(page, "error-state", "Error state")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
