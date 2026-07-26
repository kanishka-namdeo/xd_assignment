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