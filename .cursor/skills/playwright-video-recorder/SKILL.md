---
name: playwright-video-recorder
description: Generate programmatic app usage videos using Playwright's video recording and Screencast API. Use when the user wants to create demo videos, tutorial walkthroughs, bug reproduction clips, or documentation videos of the Streamlit or FastAPI application.
---

# Playwright Video Recorder

Generate app usage videos programmatically using Playwright. Two modes: full-session recording (context-level) and targeted annotated clips (Screencast API, v1.59+).

## Prerequisites

Install Playwright and browser binaries:

```bash
.\.venv\Scripts\pip.exe install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Two Recording Modes

### Mode 1: Context-Level Recording (Full Session)

Records the entire browser session. Best for CI forensics or complete flow capture.

```python
import asyncio
from playwright.async_api import async_playwright

async def record_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            record_video_dir="videos/",
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        await page.goto("http://localhost:8501")

        # ... interact with the app ...

        await context.close()
        browser.close()
```

**Key detail**: The video file is only written when the context closes. Always call `context.close()` before accessing the video path.

### Mode 2: Screencast API (Targeted Annotated Clips)

Start/stop recording mid-session with chapter markers and action annotations. Best for demos, tutorials, and focused clips.

```python
async def record_clip():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("http://localhost:8501")

        # Start recording at the exact moment you want
        await page.screencast.start(path="videos/login-flow.webm")

        # Add chapter marker
        await page.screencast.show_chapter("Login Flow")

        # Interactions are annotated automatically
        await page.screencast.show_actions()

        await page.get_by_label("Identity Number").fill("123456789")
        await page.get_by_role("button", name="Login").click()

        # Stop recording
        await page.screencast.stop()

        await browser.close()
```

## Screencast API Reference

| Method | Purpose |
|--------|---------|
| `page.screencast.start(path="file.webm")` | Begin recording |
| `page.screencast.stop()` | Stop and flush to disk |
| `page.screencast.show_chapter("Title")` | Insert chapter marker overlay |
| `page.screencast.show_actions()` | Highlight clicks/fills with visual annotations |
| `page.screencast.hide_actions()` | Remove action annotations |
| `page.screencast.show_overlay(html)` | Custom HTML overlay |
| `page.screencast.hide_overlays()` | Remove all overlays |

## Project-Specific Workflows

### Recording the Streamlit UI (Port 8501)

```python
async def record_streamlit_demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # visible for demos
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="videos/",
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        await page.goto("http://localhost:8501")

        # Phase 0: Authentication
        await page.screencast.start(path="videos/phase0-auth.webm")
        await page.screencast.show_chapter("Phase 0: Authentication")
        await page.get_by_label("Identity Number").fill("784-1990-1234567-8")
        await page.get_by_role("button", name="Login").click()
        await page.screencast.stop()

        # Phase 1: Intake
        await page.screencast.start(path="videos/phase1-intake.webm")
        await page.screencast.show_chapter("Phase 1: Intake Questions")
        await page.get_by_label("Message").fill("I need social support")
        await page.get_by_role("button", name="Send").click()
        await page.screencast.stop()

        await context.close()
        browser.close()
```

### Recording the FastAPI Docs (Port 8000)

```python
async def record_api_demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="videos/",
        )
        page = await context.new_page()
        await page.goto("http://localhost:8000/docs")

        await page.screencast.start(path="videos/api-docs.webm")
        await page.screencast.show_chapter("API Documentation")
        await page.screencast.show_actions()

        # Expand an endpoint
        await page.get_by_text("/api/v1/auth/login").click()
        await page.get_by_text("POST").click()

        await page.screencast.stop()
        await context.close()
        browser.close()
```

## Output Format

- Videos are saved as **WebM** format by default.
- To convert to MP4: `ffmpeg -i input.webm -c:v libx264 -preset medium -crf 23 output.mp4`
- Video path accessible via `page.video.path()` after context close (context-level mode only).

## Performance Notes

- Recording adds 15-30% overhead to execution time.
- Keep resolution at 720p for best balance.
- Use `headless=False` for demo videos where you want to show the browser.
- Use `headless=True` for CI/background generation.

## Workflow Checklist

- [ ] Ensure target app is running (Streamlit on 8501, FastAPI on 8000)
- [ ] Create `videos/` directory
- [ ] Choose recording mode (context-level vs Screencast)
- [ ] Write script with interactions
- [ ] Close context/browser to flush video
- [ ] Convert WebM to MP4 if needed
