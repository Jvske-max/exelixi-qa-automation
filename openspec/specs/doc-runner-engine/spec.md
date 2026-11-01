# Specification: Document-Driven Test Execution Engine

## Overview

The Document-Driven Test Execution Engine (`DocRunner`) provides an automated dispatcher that parses specification documents (`.docx` and `.pdf`), validates case readiness, orchestrates headless or headed Playwright browsers, captures step-level screenshot telemetry, and generates executive evidence reports. The engine guarantees deterministic browser synchronization, anti-hallucination execution, and security boundaries prohibiting plaintext credential exposure.

## Requirements

### 1. Document Ingestion and Normalization Gating

The runner MUST ingest parsed specifications produced by `DocParser`.

- The runner MUST inspect the `normalization_state` of each `TestCase` before launching browser contexts.
- If `normalization_state` is `NEEDS_INFO` or `UNSUPPORTED`, the execution engine MUST abort immediately with process exit code `2`.
- Execution SHALL proceed only when `normalization_state` is explicitly `READY`.

### 2. Dynamic Credential and Environment Expansion

The engine MUST resolve authentication credentials dynamically from runtime environment variables.

- Step definitions and case metadata containing `${QA_USER_<ROL>}` and `${QA_PASS_<ROL>}` placeholders MUST be interpolated using `os.environ`.
- If an interpolated variable is absent from the runtime environment, the engine SHALL raise a `ValueError` identifying the exact missing variable name.
- Plaintext passwords or secrets MUST NOT be hardcoded into default parameter values or persisted in unmasked error traces.

### 3. Step Execution Dispatch

Test steps MUST be dispatched deterministically based on their action definition:

- `navigate`: The runner MUST direct the browser to the target URL and wait for DOM synchronization (`domcontentloaded` or `networkidle`).
- `fill`: The runner MUST locate target input elements using resilient selectors, clear existing content, and type the resolved value.
- `click`: The runner MUST click matching interactive elements and synchronize for resulting state changes.
- `verify`: The runner MUST assert expected text or element presence using Playwright web-first assertions (`expect(locator).to_contain_text()`).
- `manual`: The runner MUST NOT execute browser automation for steps flagged as `manual` or `Pendiente manual`; it SHALL log the item as skipped or pending manual review.

### 4. Telemetry, Error Masking, and Reporting

The engine MUST produce comprehensive execution telemetry without exposing sensitive data.

- Screenshots SHOULD be captured for every executed step and saved into an isolated directory (`artifacts/` or `build/`).
- If an exception occurs, sensitive tokens, passwords, and URL credentials MUST be masked with `[REDACTED]` before inclusion in reports or console logs.
- The engine SHALL support dispatching execution events concurrently to `PDFReporter` (via `--output-report`) and `AllureReporter` (via `--allure-dir`).

---

### Scenarios

#### Scenario: Successful Document Execution with Dual Reporting
- **Given** a canonical test document with `normalization_state == "READY"`
- **When** `DocRunner.run_document()` is invoked with `--output-report report.pdf` and `--allure-dir allure-results/`
- **Then** the engine MUST execute all steps through Playwright
- **And** it MUST produce an executive PDF report and Allure v2 JSON results
- **And** process exit code SHALL be `0`.

#### Scenario: Pre-Flight Normalization Gate Aborts Incomplete Case
- **Given** a specification document flagged with `normalization_state == "NEEDS_INFO"`
- **When** `DocRunner` attempts to execute the case
- **Then** the engine MUST NOT launch or navigate the browser
- **And** it MUST terminate execution immediately with exit code `2`.

#### Scenario: Missing Environment Variable Triggers Explicit Error
- **Given** a test step referencing `${QA_PASS_SUPERVISOR}` which is not set in `os.environ`
- **When** the execution engine resolves step credentials
- **Then** it MUST raise `ValueError` stating `Missing required environment variable: ${QA_PASS_SUPERVISOR}`
- **And** no sensitive fallback string SHALL be submitted to the browser.
