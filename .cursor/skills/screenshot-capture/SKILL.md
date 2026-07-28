---
name: screenshot-capture
description: Capture app screenshots instantly via Cursor's browser MCP without writing scripts. Use when you need quick visual verification, bug state capture, documentation screenshots, or phase-by-phase UI capture.
---

# Screenshot Capture

Capture application screenshots instantly using Cursor's built-in browser MCP. No installation, no scripts — just navigate and capture.

## Why MCP Screenshots?

| Aspect | MCP Screenshot | Video Recorder (Python) |
|--------|----------------|-------------------------|
| Setup | Zero - Cursor's browser | pip install + browser binary |
| Execution | Tool call in chat | Write + run Python script |
| Output | PNG/JPEG inline | WebM file on disk |
| Speed | Instant | Context flush required |
| Use Case | Verification, docs, bugs | Demos, tutorials, CI forensics |

## MCP Tool Reference

### `browser_take_screenshot`

| Parameter | Type | Description |
|-----------|------|-------------|
| `fullPage` | boolean | Full scrollable page vs. viewport |
| `filename` | string | Custom filename (default: `page-{timestamp}.png`) |
| `ref` | string | CSS selector for element screenshot |
| `element` | string | Description of element (for context) |
| `type` | string | Image format: `png` (default), `jpeg`, `webp` |
| `viewId` | string | Target browser tab ID |

### Related Tools

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Open/create browser tab with URL |
| `browser_snapshot` | Get accessibility tree + element refs |
| `browser_click` | Interact before capture |
| `browser_type` | Fill inputs before capture |
| `browser_tabs` | List open tabs |
| `browser_lock` | Lock tab for multi-step automation |

## Core Workflow Pattern

```
browser_navigate → browser_snapshot → browser_take_screenshot
```

### Basic Example

1. Navigate to the app:
```
browser_navigate({ url: "http://localhost:8501" })
```

2. Get page structure (optional but recommended):
```
browser_snapshot()
```

3. Capture screenshot:
```
browser_take_screenshot({ filename: "phase0-landing.png" })
```

## Project-Specific Workflows

### Streamlit UI (Port 8501)

#### Phase 0: Authentication Landing

```
browser_navigate({ url: "http://localhost:8501" })
browser_snapshot()
browser_take_screenshot({ filename: "phase0-landing.png" })
```

#### After Login

```
browser_navigate({ url: "http://localhost:8501" })
browser_type({ ref: "input[aria-label='Identity Number']", text: "784-1990-1234567-8" })
browser_click({ ref: "button:has-text('Login')" })
browser_snapshot()
browser_take_screenshot({ filename: "phase0-authenticated.png" })
```

#### Phase Progress Tracker Element

```
browser_navigate({ url: "http://localhost:8501" })
browser_snapshot()
browser_take_screenshot({
  ref: "[data-testid='stSidebar']",
  element: "Phase Progress Tracker",
  filename: "phase-tracker.png"
})
```

### FastAPI Docs (Port 8000)

#### API Documentation Overview

```
browser_navigate({ url: "http://localhost:8000/docs" })
browser_take_screenshot({ fullPage: true, filename: "api-docs-full.png" })
```

#### Specific Endpoint Section

```
browser_navigate({ url: "http://localhost:8000/docs" })
browser_click({ ref: "button:has-text('/api/v1/auth/login')" })
browser_snapshot()
browser_take_screenshot({
  ref: ".opblock-tag-section:has-text('auth')",
  element: "Auth Endpoints",
  filename: "api-auth-endpoints.png"
})
```

## Batch Capture: 7-Phase Flow

Use `browser_lock` for multi-step automation that captures all phases:

```
browser_navigate({ url: "http://localhost:8501" })
browser_lock({ action: "lock" })

# Phase 0: Landing
browser_take_screenshot({ filename: "phase0-landing.png" })

# Phase 0: Login
browser_type({ ref: "input[aria-label='Identity Number']", text: "784-1990-1234567-8" })
browser_click({ ref: "button:has-text('Login')" })
browser_take_screenshot({ filename: "phase0-authenticated.png" })

# Phase 1: Intake
browser_type({ ref: "textarea[aria-label='Message']", text: "I need social support" })
browser_click({ ref: "button:has-text('Send')" })
browser_take_screenshot({ filename: "phase1-intake-response.png" })

# ... continue through phases ...

browser_lock({ action: "unlock" })
```

## Use Cases

### 1. Quick Verification

"Does the phase tracker render correctly?"

```
browser_navigate({ url: "http://localhost:8501" })
browser_snapshot()
browser_take_screenshot()
```

Result: Screenshot appears inline in chat immediately.

### 2. Bug State Capture

"The decision card is showing wrong data."

```
browser_navigate({ url: "http://localhost:8501" })
# Navigate to bug state
browser_snapshot()
browser_take_screenshot({
  ref: "[data-testid='decision-card']",
  element: "Decision Card with Bug",
  filename: "bug-decision-card.png"
})
```

### 3. Documentation Screenshots

"Capture screenshots for the README."

```
browser_navigate({ url: "http://localhost:8501" })
browser_take_screenshot({ fullPage: true, filename: "ui-full-page.png" })
```

### 4. Before/After Comparison

"Show the difference before and after the fix."

```
# Before fix
browser_navigate({ url: "http://localhost:8501?version=before" })
browser_take_screenshot({ filename: "before-fix.png" })

# After fix (in new session)
browser_navigate({ url: "http://localhost:8501?version=after" })
browser_take_screenshot({ filename: "after-fix.png" })
```

### 5. Element-Level Debugging

"The document upload button is misaligned."

```
browser_navigate({ url: "http:localhost:8501" })
browser_snapshot()
browser_take_screenshot({
  ref: "button:has-text('Upload')",
  element: "Upload Button",
  filename: "upload-button-alignment.png"
})
```

## Output Formats

| Format | Use Case | File Size |
|--------|----------|-----------|
| `png` | Documentation, bug reports | 50-200KB |
| `jpeg` | Email, quick sharing | 30-100KB |
| `webp` | Web embedding | 20-80KB |

Use `quality` parameter for JPEG/WebP (0-100, higher = better quality):

```
browser_take_screenshot({ type: "jpeg", quality: 85, filename: "docs.jpg" })
```

## Workflow Checklist

- [ ] Ensure target app is running (Streamlit on 8501, FastAPI on 8000)
- [ ] Use `browser_navigate` to open the app
- [ ] Use `browser_snapshot` to understand page structure (recommended)
- [ ] Call `browser_take_screenshot` with desired options
- [ ] Image appears inline in chat response
- [ ] Use `browser_lock` for multi-capture sequences
- [ ] Use `fullPage: true` for documentation screenshots

## When to Use vs. Video Recorder

### Use Screenshot Capture When:
- Quick visual verification
- Bug state documentation
- Documentation static images
- Element-specific debugging
- Before/after comparisons
- Inline chat context needed

### Use Video Recorder When:
- Demo walkthrough with timing
- Tutorial content with chapter markers
- CI forensics (full session recording)
- Animated interactions needed
- File-based delivery required

## Performance Notes

- Screenshots are near-instant (<1 second)
- No context flush or cleanup required
- Files saved to `.cursor/screenshots/` by default
- Inline preview limited to chat display
- Full resolution available via file path

## Integration with Other Skills

- **live-e2e-validation**: Capture screenshots during E2E testing
- **api-only-interaction**: Screenshot FastAPI docs during API testing
- **process-management**: Verify services running before capture
- **playwright-video-recorder**: Use screenshots for video storyboards