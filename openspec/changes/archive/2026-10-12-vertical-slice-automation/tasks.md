# Tasks: Vertical Slice QA Automation Framework

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 250 - 320 lines |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Baseline Tooling & API Mock Layer | PR 1 | `.venv/bin/pytest -m "smoke or api" -v` | In-memory FastAPI mock runner | Revert `apiclients/ocr_client.py`, `tests/api/` |
| 2 | Sys2000 User Management POM & E2E | PR 2 | `.venv/bin/pytest tests/e2e/test_user_management.py` | Playwright Chromium on QA Sys2000 | Revert `pageobjects/user_management_page.py`, `tests/e2e/` |

## Phase 1: Foundation & Tooling Baseline (pipeline-engineer)

- [x] 1.1 Add `httpx>=0.28.1`, `pytest-cov>=6.0.0`, and `ruff>=0.9.0` to `requirements.txt` and install into `.venv`.
- [x] 1.2 Update `openspec/config.yaml` to register `ruff check` as linter and `pytest --cov` as coverage tool.
- [x] 1.3 Ensure `.agents/hooks.json` executes without stdout pollution to protect Antigravity hooks.

## Phase 2: Mock API Client & Integration Tests (test-writer)

- [x] 2.1 Create `apiclients/ocr_client.py` using `httpx.Client` with methods for successful document extraction, handling 422 errors, and configurable timeouts.
- [x] 2.2 Create `tests/api/test_ocr_service.py` with `@pytest.mark.api` and `@pytest.mark.smoke` verifying:
  - 2.2.1 Successful extraction returns sample cedula and confidence score >= 0.9.
  - 2.2.2 Illegible document returns 422 with descriptive error detail.
  - 2.2.3 Provider timeout properly raises client timeout exception without hanging for 10s.

## Phase 3: Sys2000 User Management Automation (test-writer)

- [x] 3.1 Create `pageobjects/user_management_page.py` following `pom-conventions`:
  - 3.1.1 Private locators for `Mantenimiento`, `Seguridad`, and `Agregar Usuario` button/modal.
  - 3.1.2 Methods: `navigate_to_user_management()`, `fill_user_form()`, `assign_reports()`, `save_user()`.
- [x] 3.2 Create `tests/e2e/test_user_management.py` with `@pytest.mark.e2e`:
  - 3.2.1 Positive scenario: login as `rmuñoz`, navigate to security menu, create reporter user.
  - 3.2.2 Negative scenario: submission with empty required fields triggers validation message.

## Phase 4: Quality Gate & Code Audit (code-auditor & sdd-verify)

- [x] 4.1 Audit all newly created files to ensure zero hardcoded passwords, zero `time.sleep` calls, and strictly explicit Playwright locators.
- [x] 4.2 Execute `ruff check .` and `.venv/bin/pytest -m "smoke or api"` to verify clean pass under 3s.
