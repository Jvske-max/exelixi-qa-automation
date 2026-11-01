# Tasks: Static Type Checking Quality Gate

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 250 - 350 lines |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes |
| Suggested split | 2 PRs (PR1: Tooling & Typing; PR2: CI & Activation) |
| Delivery strategy | chained-pr |
| Chain strategy | serial |

---

## Phase 1: Tooling & Configuration

### T1.1: [x] [RED] Type Checking Quality Gate Unit Tests
Add unit tests asserting `pyproject.toml` contains `[tool.mypy]`, `openspec/config.yaml` enables `type_checker`, and Mypy executes cleanly.
- **File**: `tests/unit/test_type_checking.py`
- **Command**: `python -m pytest tests/unit/test_type_checking.py -q`
- **Exit Criteria**: Tests fail initially due to missing files and unset configuration keys.

### T1.2: [x] [GREEN] Dependencies & Mypy Base Setup
Add `mypy`, `types-requests`, and `types-PyYAML` to `requirements.txt`. Create `pyproject.toml` with `[tool.mypy]` for Python 3.13, `explicit_package_bases = true`, `check_untyped_defs = true`, and third-party overrides (`reportlab`, `playwright`). Update `openspec/config.yaml` (`type_checker.available = true`, `command: python -m mypy normalizer pageobjects parsers reporting runners tools`).
- **Files**: `requirements.txt`, `pyproject.toml`, `openspec/config.yaml`
- **Exit Criteria**: `python -m pytest tests/unit/test_type_checking.py -q` passes.

### T1.3: [x] [REFACTOR] Configuration Hygiene
Format TOML/YAML files and verify configuration schema alignment.
- **Verification**: `python -m ruff check pyproject.toml` and pytest pass cleanly.

---

## Phase 2: Core Package Typing & Stubs Resolution

### T2.1: [x] [RED] Surface Core Package Typing Violations
Execute Mypy against core modules to reveal untyped callables, missing annotations, and stubs gaps.
- **Command**: `python -m mypy normalizer/ parsers/ reporting/ runners/ pageobjects/ mocks/ tools/`
- **Exit Criteria**: Type check detects errors without runtime harness failures.

### T2.2: [x] [GREEN] Core Package Annotation & Stubs Resolution
Annotate signatures, resolve None dereferences, and configure stubs across `normalizer/`, `parsers/`, `reporting/`, `runners/`, `pageobjects/`, `mocks/`, and `tools/`.
- **Files**: Core packages (`normalizer/`, `parsers/`, `reporting/`, `runners/`, `pageobjects/`, `mocks/`, `tools/`)
- **Command**: `python -m mypy normalizer pageobjects parsers reporting runners tools`
- **Exit Criteria**: `python -m mypy normalizer pageobjects parsers reporting runners tools` exits 0 across all core modules.

### T2.3: [x] [REFACTOR] Type Hints Clean-up & DRY Harmonization
Standardize shared type aliases across runners and parsers without changing runtime behavior.
- **Verification**: `python -m mypy normalizer pageobjects parsers reporting runners tools` and `python -m ruff check .` pass cleanly.

---

## Phase 3: CI Pipeline Integration & Code Auditor Verification

### T3.1: [x] [RED] CI Workflow Verification Pre-Check
Assert CI workflow requires static type checking step and confirm current gate gap.
- **File**: `.github/workflows/ci.yml`
- **Exit Criteria**: Workflow inspection confirms missing Mypy gate step.

### T3.2: [x] [GREEN] CI Integration & Verification Suite
Add `python -m mypy .` step to `.github/workflows/ci.yml`. Run smoke, unit, and integration suites.
- **Commands**:
  - `python -m pytest -m smoke -q`
  - `python -m pytest tests/unit tests/integration -q`
  - `python -m mypy .`
- **Exit Criteria**: All unit, integration, smoke tests, and static type checks pass.

### T3.3: [REFACTOR] Code Auditor Review & Sign-Off
Run `code-auditor audit` and formatting validation to guarantee zero regressions.
- **Commands**:
  - `code-auditor audit`
  - `python -m ruff check .`
  - `python -m ruff format --check .`
- **Exit Criteria**: Code auditor audit passes with zero critical findings.
