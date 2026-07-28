---
name: temporary-files
description: Prevents committing temporary test scripts, debug files, and scratch files to the repository. Covers what not to commit, .gitignore patterns, pre-commit cleanup commands, and rationale. Use when committing changes, reviewing staged files, or when the user asks about git commit hygiene.
---

# Temporary Files Rule

**NEVER commit temporary test scripts, debug files, or scratch files to the repository.**

## What NOT to Commit

- `test_*.py` files in the root directory (these are ad-hoc test scripts, not part of the test suite)
- `processing_*.json` or other temporary output files
- Debug scripts created during troubleshooting
- One-off validation scripts

## What IS Okay to Commit

- Files in `tests/` directory (these are part of the test suite)
- Files in `evals/` directory (evaluation framework)
- Actual application code in `src/`
- Documentation in `docs/`

## Prevention

### Before Committing

```powershell
# Check what you're about to commit
git status

# Review staged files
git diff --cached --name-only

# If you see test_*.py or processing_*.json in root, unstage them
git reset HEAD test_*.py processing_*.json
```

### .gitignore Patterns

Add these patterns to `.gitignore` for common scratch files:

```
# Temporary test scripts
/test_*.py
/processing_*.json
/debug_*.py
/scratch_*.py

# Temporary output
*.tmp
*.log
```

### Clean Up Before Committing

```powershell
# Remove temporary test files before committing
Remove-Item test_*.py -ErrorAction SilentlyContinue
Remove-Item processing_*.json -ErrorAction SilentlyContinue
```

## Rationale

- Keeps the repository clean and focused on actual application code
- Prevents confusion about which test files are part of the test suite
- Reduces repository size
- Makes code review easier

## Example

**Bad:** Committing `test_decision_card.py` (ad-hoc test script)
**Good:** Only committing `src/services/chat_service.py` (actual fix)
