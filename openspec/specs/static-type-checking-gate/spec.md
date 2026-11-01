# Specification: Static Type Checking Quality Gate

## Overview

The Static Type Checking Quality Gate enforces rigorous static type verification across the automation framework using Mypy. By analyzing function signatures, return types, container types, and None dereferences ahead of runtime, the quality gate prevents class attribute mismatches, type regressions, and subtle runtime defects. The gate is integrated into `pyproject.toml`, registered in `openspec/config.yaml`, and enforced as a mandatory check in CI pipelines.

## Requirements

### 1. Centralized Configuration in pyproject.toml

Static type checking options MUST be defined in `pyproject.toml` under `[tool.mypy]`.

- The configuration MUST specify `python_version = "3.13"`.
- It MUST enable `explicit_package_bases = true` to ensure consistent resolution of namespace roots.
- It MUST enable `check_untyped_defs = true` to analyze method bodies in partially typed classes.
- Third-party packages lacking complete type stubs (`reportlab.*`, `docx.*`, `pypdf.*`) MUST have explicit overrides with `ignore_missing_imports = true`.

### 2. Module Scope and Coverage

The static type checking gate MUST cover all primary business packages:

- `normalizer/` (extraction, gap analysis, schema, grounding, render, providers, CLI)
- `pageobjects/` (Page Object classes and locators)
- `parsers/` (document ingestion parsers and Pydantic models)
- `reporting/` (PDF and Allure telemetry reporters)
- `runners/` (Playwright document runner and dispatchers)
- `tools/` (synthetic generators and evaluation harnesses)
- All 28 source modules in the repository MUST maintain clean type definitions with zero errors.

### 3. OpenSpec and CI Quality Gate Integration

Static type checking MUST be established as an automated blocking quality barrier.

- `openspec/config.yaml` MUST configure `testing.quality.type_checker.available = true` and define the execution command `python -m mypy normalizer pageobjects parsers reporting runners tools`.
- `.github/workflows/ci.yml` MUST incorporate a dedicated `Run Mypy static type check` step.
- Pull requests and commits SHALL NOT merge if Mypy reports any type errors.

---

### Scenarios

#### Scenario: Full Repository Mypy Verification Passes
- **Given** all 28 core Python modules annotated with standard type hints
- **When** the static type checker command `python -m mypy normalizer pageobjects parsers reporting runners tools` executes
- **Then** Mypy MUST exit with status code `0`
- **And** output MUST indicate `Success: no issues found in 28 source files`.

#### Scenario: Type Violation Triggers Gate Failure
- **Given** a method annotated with return type `bool` that returns `None` or an incompatible type
- **When** Mypy executes against the affected file
- **Then** Mypy MUST fail with a non-zero exit code
- **And** it MUST output the specific line number and incompatible type diagnostic.

#### Scenario: OpenSpec Configuration Enforces Type Checking
- **Given** the configuration in `openspec/config.yaml`
- **When** the test harness or automated audit tool inspects `testing.quality.type_checker`
- **Then** `available` MUST be `True`
- **And** the configured check command MUST match the project-standard Mypy invocation.
