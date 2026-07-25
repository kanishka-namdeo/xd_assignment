# Agent Evaluation Framework

## Purpose
Evaluation framework for measuring agent accuracy and quality. Distinct from unit tests: evaluates agent performance against ground truth datasets, not code correctness. Measures extraction accuracy, validation rule effectiveness, and eligibility scoring performance.

## Ownership
- Primary: Development Team
- Review Required: Evaluation changes require review

## Local Contracts

### Evaluation Types
- **Extraction accuracy** (`test_extraction_accuracy.py`): Measure OCR, PDF parsing, table extraction accuracy against labeled datasets
- **Validation rules** (`test_validation_rules.py`): Measure validation rule effectiveness (true positive rate, false positive rate)
- **Eligibility scoring** (`test_eligibility_scoring.py`): Measure ML model accuracy, precision, recall against labeled applicant data

### Evaluation Standards
- Use labeled datasets with ground truth
- Report metrics: accuracy, precision, recall, F1-score
- Track metrics over time (version-to-version comparison)
- Minimum thresholds:
  - Extraction accuracy: >90% for structured data, >80% for handwritten
  - Validation true positive rate: >85%
  - Eligibility model accuracy: >75%

### Evaluation Data
- Store evaluation datasets in `evals/data/` (not committed to git)
- Use synthetic data from fake data generators
- Include edge cases and failure modes

## Work Guidance

### Adding a New Evaluation
1. Create test file in `evals/` (e.g., `test_decision_accuracy.py`)
2. Load ground truth dataset
3. Run agent on test inputs
4. Compare outputs to ground truth
5. Calculate and report metrics

### Running Evaluations
```bash
# All evaluations
.\.venv\Scripts\pytest.exe evals/

# Specific evaluation
.\.venv\Scripts\pytest.exe evals/test_extraction_accuracy.py

# With verbose output
.\.venv\Scripts\pytest.exe evals/ -v
```

### Interpreting Results
- Metrics below threshold indicate model/prompt degradation
- Compare metrics across versions to detect regressions
- Use Langfuse traces to debug low-performing cases

## Verification
- Evaluations run on CI after each merge
- Metrics tracked in dashboard (future)
- Regression alerts if metrics drop >5%

## Child DOX Index
None - single-level structure.
