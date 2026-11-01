# Specification: Unified Allure Runner Reporting

## Overview

The Unified Allure Runner Reporting specification governs the integration of Allure v2 lifecycle telemetry into the document test runner. By decoupling test execution from reporting, `reporting/allure_reporter.py` allows standalone runners to emit industry-standard Allure results, step timelines, container structures, and screenshot attachments alongside executive PDF reports. The reporter incorporates robust credential and PII sanitization to prevent sensitive data exposure in CI/CD artifacts.

## Requirements

### 1. Result Structure and File Logger Integration

The reporter MUST output compliant Allure v2 JSON structures to a designated directory.

- The reporter MUST instantiate `allure_commons.logger.AllureFileLogger` directed to `--allure-dir`.
- Test cases MUST produce a primary `*-result.json` file adhering to Allure v2 `TestResult` schema.
- Test suites or runner batches MUST emit corresponding `*-container.json` files tracking lifecycle boundaries.

### 2. Status and Step Mapping

Execution outcomes MUST map deterministically to Allure statuses:

- `PASS` / `PASSED` MUST map to `allure_commons.model2.Status.PASSED`.
- `FAIL` / `FAILED` MUST map to `allure_commons.model2.Status.FAILED`.
- `ERROR` / `BLOCKED` / `BROKEN` MUST map to `allure_commons.model2.Status.BROKEN`.
- `SKIPPED` / `MANUAL` MUST map to `allure_commons.model2.Status.SKIPPED`.
- Granular steps within a test case MUST be emitted as nested `TestStepResult` items with accurate start and stop millisecond timestamps.

### 3. Attachment Handling

Visual evidence MUST be registered as standard Allure attachments.

- When step or test failure screenshots are captured, the reporter MUST attach the PNG file using `AllureReporter.attach_file()`.
- Attachments MUST declare `attachment_type="image/png"` and provide descriptive titles.
- Missing screenshot files SHALL NOT raise unhandled exceptions; the reporter MUST log a warning and proceed gracefully.

### 4. Credential and PII Masking

The reporter MUST sanitize all textual fields before serializing results to disk.

- Passwords, keys, tokens, and PIN values matching `PASSWORD_MASK_PATTERN` MUST be replaced with `[REDACTED]`.
- URLs containing inline basic credentials (`http://user:password@host`) MUST have the password segment masked.
- Venezuelan identity numbers (cédulas and RIFs), personal emails, and JWT tokens MUST be redacted.
- Common non-sensitive short strings SHOULD NOT be over-masked unless explicitly associated with sensitive credential keys.

---

### Scenarios

#### Scenario: Allure Result and Step Emission
- **Given** an initialized `AllureReporter` pointing to `build/allure-results`
- **When** a test case executes with 3 sequential steps and completes with status `PASS`
- **Then** a `*-result.json` file MUST be created in the output directory
- **And** the result status MUST be `"passed"`
- **And** exactly 3 child step results SHALL be recorded in the steps array.

#### Scenario: Credential Sanitization in Step Metadata
- **Given** a step executing `fill` with target `password` and value `"SecretPass123"`
- **When** `AllureReporter.start_step()` and `stop_step()` record the action
- **Then** the serialized step name and parameters MUST display `[REDACTED]`
- **And** the plaintext string `"SecretPass123"` SHALL NOT exist in the emitted JSON file.

#### Scenario: Broken Step Status Propagation
- **Given** a step that raises `BlockedStepError` due to unavailable external dependencies
- **When** `AllureReporter.stop_step()` and `stop_test_case()` process the execution report
- **Then** the test outcome status MUST be set to `"broken"`
- **And** the error trace MUST have all basic auth and sensitive query parameters masked.
