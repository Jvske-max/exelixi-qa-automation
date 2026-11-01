# Proposal: Static Type Checking Quality Gate

## Intent
Implement a static type checking quality gate using Mypy to catch type errors, attribute errors, and invalid None dereferences ahead of runtime, standardizing type annotations across core modules.

## Scope

### In Scope
- Add `mypy`, `types-requests`, and `types-PyYAML` to `requirements.txt`.
- Configure `[tool.mypy]` in `pyproject.toml` with `explicit_package_bases`, `check_untyped_defs`, and third-party import rules (e.g., `reportlab`, `playwright`).
- Resolve type errors and missing annotations across core packages: `normalizer/`, `parsers/`, `runners/`, `reporting/`, `pageobjects/`, `mocks/`, and `tools/`.
- Update `openspec/config.yaml` (`testing.quality.type_checker.available = true`, command: `python -m mypy .`).
- Add static type checking step to `.github/workflows/ci.yml`.
- Add unit test verifying mypy configuration and clean execution.

### Out of Scope
- Rewriting dynamic ReportLab canvas layout methods into strict typed classes.

## Capabilities

### New Capabilities
- `static-type-checking`: Automated quality gate running Mypy static analysis to catch type issues ahead of runtime.

### Modified Capabilities
- `openspec-quality-gate`: Enforces static type checking alongside Ruff linting and formatting gates.

## Approach
- Configure `[tool.mypy]` in `pyproject.toml` for Python 3.13 and repository package structure.
- Add stub packages and pragmatic overrides for third-party libraries.
- Annotate and resolve typing errors in core packages without modifying runtime logic.
- Integrate type check gate into OpenSpec configuration and CI workflow.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `requirements.txt` | Modified | Add `mypy`, `types-requests`, `types-PyYAML` |
| `pyproject.toml` | Modified / New | Add `[tool.mypy]` configuration |
| `openspec/config.yaml` | Modified | Enable `type_checker` gate |
| `.github/workflows/ci.yml` | Modified | Add type checking CI step |
| Core modules (`normalizer/`, `parsers/`, `runners/`, `reporting/`, `pageobjects/`, `mocks/`, `tools/`) | Modified | Add type annotations and fixes |
| `tests/unit/test_type_checker.py` | New | Unit tests for mypy execution |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Third-party libraries without stubs | Medium | Use stub packages and `ignore_missing_imports` overrides |
| Regressions from annotation edits | Low | Verify test suite passes with zero functional changes |

## Rollback Plan
Revert changes to `requirements.txt`, `pyproject.toml`, `openspec/config.yaml`, and `.github/workflows/ci.yml`.

## Dependencies
- `mypy`
- `types-requests`
- `types-PyYAML`

## Success Criteria
- [ ] `requirements.txt` includes `mypy`, `types-requests`, and `types-PyYAML`.
- [ ] `pyproject.toml` defines `[tool.mypy]` configuration.
- [ ] `python -m mypy .` passes with zero errors across core packages.
- [ ] `openspec/config.yaml` sets `type_checker.available = true`.
- [ ] CI workflow executes `python -m mypy .` successfully.
- [ ] Unit test verifies clean mypy execution.
