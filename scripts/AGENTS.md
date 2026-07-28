# Utility Scripts

## Purpose
Development and operational scripts for data generation, maintenance, and automation tasks. Not part of the main application.

## Ownership
- Primary: Development Team
- Review Required: Script changes require review

## Local Contracts

### Script Categories
- **Data Generation** (`generate_test_data.py`): Generates synthetic test applicant profiles with cross-document consistency
- **Fresh Account Generation** (`generate_fresh_account.py`): Generates a single fresh applicant account with full document set, supports custom seeds and output directories
- **E2E Testing** (`e2e_test.py`, `final_e2e_test.py`, `continue_e2e_test.py`, `stream_e2e_test.py`): End-to-end testing scripts for various scenarios
- **Database Maintenance** (`check_db.py`, `check_db_column.py`, `check_column.py`, `check_migration.py`, `add_validation_confidence_column.py`, `apply_checkpoint_migration.py`): Database inspection and migration scripts
- **Demo/Smoke Tests** (`demo_smoke_test.py`, `quick_smoke_test.py`): Quick validation scripts
- **API Testing** (`test_fastapi.py`, `test_persist.py`, `api_client.py`): API and persistence testing; `api_client.py` is the CLI client for the API-only agent skill
- **Streaming Tests** (`long_stream_test.py`, `stream_upload_test.py`, `upload_and_process.py`): Streaming functionality tests
- **Browser E2E** (`browser_e2e_test.py`): Playwright-based browser automation testing
- **Enablement Debugging** (`debug_enablement.py`, `test_enablement_detailed.py`): Enablement phase debugging and detailed testing
- **MCP/Credential Management** (`mcp_callback.py`, `scrub_github_pat.py`, `scrub_mcp.py`, `scrub_mcp_tree.py`): MCP server callback handling and credential scrubbing utilities

### Execution Requirements
- All scripts must use the project venv: `.\.venv\Scripts\python.exe`
- Scripts should be idempotent where possible
- Output paths default to `data/` directory

### Dependencies
- Scripts import from `src/data_generation/` module
- Must be run from project root for correct path resolution

## Work Guidance

### Running Scripts
```bash
# Generate test applicants
.\.venv\Scripts\python.exe scripts/generate_test_data.py
```

### Adding a New Script
1. Create script in `scripts/`
2. Add project root to sys.path if importing from src/
3. Use venv Python for execution
4. Document usage in this file

## Verification
- Scripts should run without errors
- Generated data validated by data generation module

## Child DOX Index
None - single-level structure.