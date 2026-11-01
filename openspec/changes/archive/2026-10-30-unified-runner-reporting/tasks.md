# Tasks: Unified Runner Allure Reporting

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 350 - 450 lines |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | 2 PRs (PR1: AllureReporter core; PR2: DocRunner integration & audit) |
| Delivery strategy | chained-pr |
| Chain strategy | serial |

---

## Phase 1: AllureReporter Core (`reporting/allure_reporter.py`)

### T1.1: [RED] Unit Tests for AllureReporter Core - COMPLETED
Add unit tests validating Allure lifecycle events, containers, steps, statuses (`passed`/`failed`/`broken`), error masking, and PNG attachments.
- **File**: `tests/unit/test_allure_reporter.py`
- **Command**: `python -m pytest tests/unit/test_allure_reporter.py -q`
- **Verification**: Tests created and initially verified failing with `ImportError`.

### T1.2: [GREEN] Implement AllureReporter - COMPLETED
Implement `AllureReporter` using `allure_commons.reporter.AllureReporter` and `AllureFileLogger` to emit Allure v2 JSON. Export in `reporting/__init__.py`.
- **Source**: `reporting/allure_reporter.py`, `reporting/__init__.py`
- **Scope**:
  - `start_test_case(test_case: TestCase)` / `stop_test_case(report: ExecutionReport)`
  - `start_step(step: StepDefinition)` / `stop_step(result: StepResult)`
  - Status mapping: PASS -> `Status.PASSED`, FAIL -> `Status.FAILED`, ERROR -> `Status.BROKEN`
  - Redacted error details and screenshot PNG attachments
- **Verification**: `python -m pytest tests/unit/test_allure_reporter.py -q` passes (21/21).

### T1.3: [REFACTOR] AllureReporter Clean-up - COMPLETED
Refactor error masking extraction, type hints, and exception handlers; prevent credential leakage in step attributes.
- **Verification**: `python -m pytest tests/unit/test_allure_reporter.py -q` and `python -m ruff check reporting/` pass with zero warnings.

---

## Phase 2: DocRunner Integration & CLI Flags (`runners/doc_runner.py`)

### T2.1: [RED] Integration Tests for DocRunner Allure Output - COMPLETED
Add integration tests verifying `--allure-dir` CLI flag, `allure_dir` runner parameter, and simultaneous PDF + Allure generation.
- **File**: `tests/integration/test_doc_runner_allure.py`
- **Command**: `python -m pytest tests/integration/test_doc_runner_allure.py -q`
- **Verification**: Tests created and verified failing initially on collection/imports.

### T2.2: [GREEN] Wire AllureReporter into DocRunner - COMPLETED
Update `DocRunner` to support `allure_dir` across constructor, execution methods, and CLI flags.
- **Source**: `runners/doc_runner.py`
- **Scope**:
  - Add `--allure-dir` argument in `parse_args`
  - Accept `allure_dir: str | Path | None` in `DocRunner.__init__`, `run_document`, `run_test_case`
  - Dispatch lifecycle step events and screenshots to `AllureReporter`
  - Preserve existing `output_report_path` PDF generation
- **Verification**: `python -m pytest tests/integration/test_doc_runner_allure.py -q` passes (11/11).

### T2.3: [REFACTOR] Runner Dispatch Decoupling - COMPLETED
Streamline lifecycle reporter dispatch logic in `DocRunner` to decouple PDF and Allure handlers without redundant disk I/O.
- **Verification**: `python -m pytest tests/integration/test_doc_runner_allure.py -q` and `python -m ruff check runners/ tests/` pass cleanly.

---

## Phase 3: Code Auditor Review & Verification Suite

### T3.1: [RED] End-to-End Dual Reporting Regression - COMPLETED
Add regression test running a document with dual PDF and Allure outputs, asserting JSON schema compliance and secret masking.
- **File**: `tests/integration/test_doc_runner_allure.py::test_full_dual_reporting_regression`
- **Command**: `python -m pytest tests/integration/test_doc_runner_allure.py -k test_full_dual_reporting_regression -q`
- **Verification**: Verified failing initially on raw password leakage in test result name; passes (2/2) after secret masking.

### T3.2: [GREEN] Pass Complete Verification Suite - COMPLETED
Execute combined unit and integration verification suites to ensure all tests pass.
- **Command**: `python -m pytest tests/unit/test_allure_reporter.py tests/integration/test_doc_runner_allure.py -q`
- **Scope & Fixes**:
  - Masked `step_name` in `AllureReporter.start_step` and `stop_step` via `self.mask_text(...)`.
  - Masked `test_case.title` and `test_case.objective` in `AllureReporter.start_test_case`.
  - Enhanced `PASSWORD_MASK_PATTERN` for quoted passwords with whitespace.
  - Applied `URL_CREDENTIAL_PATTERN` to general traces and error messages in `AllureReporter.mask_text` and `DocRunner._mask_error_message`.
  - Wrapped blocked step errors in `DocRunner` with `_mask_error_message`.
  - Prevented step value over-masking on short non-sensitive values in `AllureReporter.mask_text`.
- **Verification**: 50/50 tests passing in `tests/unit/test_allure_reporter.py` and `tests/integration/test_doc_runner_allure.py`.

### T3.3: [REFACTOR] Code Audit & Static Analysis - COMPLETED
Run linter, type checks, and audit security boundaries against credential leaks in Allure results.
- **Commands**:
  - `python -m ruff check reporting/ runners/ tests/` (All checks passed)
  - `python -m pytest -m smoke -q` (161 passed)
