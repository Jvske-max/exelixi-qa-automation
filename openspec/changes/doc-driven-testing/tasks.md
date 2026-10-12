# Tasks: Document-Driven Testing & PDF Evidence Reporting

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 750 - 880 lines |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | 2 PRs (1: Ingestion & Models; 2: Runner & PDF Reporter) |
| Delivery strategy | chained-pr |
| Chain strategy | serial |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: serial
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Ingestion parsers & core dataclass models | PR 1 | `.venv/bin/pytest tests/unit/test_parsers.py` | Sample docx/pdf fixtures | Revert `parsers/` and tests |
| 2 | Executive PDF reporter & Playwright runner | PR 2 | `.venv/bin/pytest tests/unit/test_pdf_reporter.py tests/integration/test_doc_runner.py` | Playwright headless & ReportLab | Revert `reporting/`, `runners/` |

## Phase 1: Foundation & Dependencies

- [x] 1.1 Add `python-docx`, `pypdf`, and `reportlab` to [requirements.txt](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/requirements.txt) and install into `.venv`.
- [x] 1.2 Create [parsers/models.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/models.py) with typed dataclasses:
  - [x] 1.2.1 Define [`StepDefinition`](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/models.py) (`step_num`, `raw_text`, `action`, `target`, `value`, `timestamp`).
  - [x] 1.2.2 Define [`TestCase`](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/models.py) (`case_id`, `module`, `title`, `objective`, `credentials`, `steps`).
  - [x] 1.2.3 Define [`StepResult`](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/models.py) and [`ExecutionReport`](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/models.py) for run telemetry and screenshots.

## Phase 2: Document Ingestion Parsers

- [x] 2.1 Implement [parsers/docx_parser.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/docx_parser.py) using `python-docx` to extract case metadata and PSR steps.
- [x] 2.2 Implement [parsers/pdf_parser.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/pdf_parser.py) using `pypdf` with regex normalization for tabular/text steps.
- [x] 2.3 Expose unified parser interface in [parsers/__init__.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/parsers/__init__.py).
- [x] 2.4 Create [tests/unit/test_parsers.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/tests/unit/test_parsers.py) verifying `.docx` and `.pdf` ingestion, step regex parsing, and metadata extraction.

## Phase 3: Executive PDF Reporter

- [x] 3.1 Implement [reporting/pdf_reporter.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/reporting/pdf_reporter.py) using ReportLab Platypus:
  - [x] 3.1.1 Build executive header with Exelixi branding, metadata grid, and execution status badge.
  - [x] 3.1.2 Build step evidence table with action details, pass/fail status, and embedded screenshot thumbnails.
  - [x] 3.1.3 Add custom canvas for two-pass "Page X of Y" numbering and confidentiality footer.
- [x] 3.2 Create [tests/unit/test_pdf_reporter.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/tests/unit/test_pdf_reporter.py) verifying PDF generation, table formatting, and thumbnail inclusion.

## Phase 4: Test Dispatcher & Execution Engine

- [x] 4.1 Implement [runners/doc_runner.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/runners/doc_runner.py) using Playwright `sync_api`:
  - [x] 4.1.1 Route steps to Page Objects ([LoginPage](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/pageobjects/login_page.py), [UserManagementPage](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/pageobjects/user_management_page.py)) with fallback to locator heuristics.
  - [x] 4.1.2 Capture step-by-step screenshots into timestamped artifacts directory and collect `ExecutionReport`.
  - [x] 4.1.3 Expose CLI: `python -m runners.doc_runner --doc <path> --output-report <pdf_path>`.
- [x] 4.2 Create [tests/integration/test_doc_runner.py](file:///home/fernandojosesilvatrejo/Documents/9no%20Semestre/QA_AUTOMATIZACI%C3%93N/tests/integration/test_doc_runner.py) executing a sample test case end-to-end to generate report artifacts.

## Phase 5: Verification & Quality Audit

- [x] 5.1 Run `ruff check .` and fix formatting or lint issues across new modules.
- [x] 5.2 Execute `.venv/bin/pytest tests/unit/ tests/integration/` ensuring 100% test pass rate and clean execution.
- [x] 5.3 Audit generated PDF report artifact visually to confirm layout aesthetics, thumbnail readability, and footer integrity.
- [x] 5.4 Code and security audit (zero hardcoded secrets, explicit waits, error recovery, separation of concerns).

