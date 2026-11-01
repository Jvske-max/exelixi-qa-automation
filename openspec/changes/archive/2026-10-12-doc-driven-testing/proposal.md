# Proposal: Document-Driven Testing & PDF Evidence Reporting

## Intent
At Exelixi.Tech, developers typically deliver manual QA test specifications as `.docx` or `.pdf` documents defining interface-level test cases (e.g. `pruebas QA # 1 R-055429...docx`). Currently, QA engineers manually read these documents, execute steps in Sys2000, take screenshots, and compile results. 

This change automates that end-to-end lifecycle:
1. Ingest and parse test specifications from `.docx` and `.pdf` files.
2. Execute the parsed test scenarios automatically using Playwright and Page Objects.
3. Generate an executive PDF evidence report containing step-by-step pass/fail verdicts, execution timestamps, error traces, and captured browser screenshots.

## Scope

### In Scope
- **Document Ingestion**: Parser module supporting `.docx` (via `python-docx`) and `.pdf` (via `pypdf`/`pdfplumber`) to extract metadata (Module, Case ID, Objective, Steps, Credentials).
- **Execution Dispatcher**: Test runner bridging parsed test definitions with corresponding Page Object actions (`LoginPage`, `UserManagementPage`).
- **PDF Evidence Reporter**: PDF generation module (via `reportlab`) that produces a formatted QA execution evidence report with embedded screenshot attachments and execution summaries.
- **CLI / Pytest Integration**: Command-line interface or pytest plugin hook allowing: `python -m runners.doc_runner --doc <path_to_doc> --output-report <path_to_pdf>`.

### Out of Scope
- AI-driven arbitrary optical character recognition on raw scanned images without text layer (relies on digital `.docx`/`.pdf` or existing OCR service).
- Replacing Allure reporting (the PDF report complements Allure for business stakeholder delivery).

## Capabilities

### New Capabilities
- `doc-test-parser`: Structured parser for developer-provided `.docx` and `.pdf` test sheets.
- `pdf-evidence-reporter`: Styled PDF report generator with executive summary and screenshot logs.
- `doc-test-runner`: Dispatcher executing parsed steps via Playwright Page Objects.

### Modified Capabilities
- None

## Approach
Create a modular pipeline:
`Doc Parser (.docx/.pdf) → Structured TestCase Model → Playwright POM Dispatcher → Screenshot Capture → PDF Report Generator (ReportLab)`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `parsers/` | New | Ingestion parsers for `.docx` and `.pdf` |
| `reporting/` | New | PDF evidence report generator (`reportlab`) |
| `runners/` | New | Document test execution runner |
| `requirements.txt` | Modified | Add `python-docx`, `pypdf`, and `reportlab` |
| `tests/unit/` | New | Unit tests for parser and report generator |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Varied formatting in developer document templates | High | Define a flexible schema parser with keyword fallbacks (e.g. matching 'Usuario', 'Pasos', 'Caso #', 'Objetivo'); provide fallback manual mapping |
| Large PDF size due to high-resolution screenshots | Medium | Compress screenshot thumbnails before embedding in ReportLab PDF tables |

## Rollback Plan
Remove `parsers/`, `reporting/`, and `runners/` packages. Core Page Objects and standard pytest suites remain unaffected.

## Dependencies
- `python-docx`
- `pypdf`
- `reportlab`

## Success Criteria
- [x] Parser correctly extracts Case ID, steps, and credentials from `pruebas QA # 1 R-055429...docx`.
- [x] Runner executes the parsed steps with Playwright and captures screenshot evidence.
- [x] A formatted PDF report is produced containing the execution verdict and visual evidence.
