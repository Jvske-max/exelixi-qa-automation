# Proposal: Vertical Slice QA Automation Framework

## Intent
Exelixi.Tech requires a reliable, multi-tier QA test automation framework for insurance software products (Sys2000 and auxiliary microservices). Current manual workflows (such as R-055429 User Management) need automation to prevent regressions. Simultaneously, automated verification gates and CI hooks require a fast, deterministic API mock tier to remain stable when external staging environments are unreachable.

## Scope

### In Scope
- Fix smoke gate reliability and add quality baseline dependencies (`httpx`, `pytest-cov`, `ruff`).
- Implement API client `apiclients/ocr_client.py` and unit/integration test suite `tests/api/test_ocr_service.py` for mock OCR endpoints.
- Implement Page Object `pageobjects/user_management_page.py` and test suite `tests/e2e/test_user_management.py` automating manual case R-055429.
- Formalize subagent roles (`pipeline-engineer`, `code-auditor`, `test-writer`) to divide framework responsibilities.

### Out of Scope
- Full policy emission and claims settlement flows (deferred to subsequent changes).
- Connecting to live production insurance databases.

## Capabilities

### New Capabilities
- `api-mock-testing`: Client abstraction and integration tests for FastAPI service mocks.
- `user-management-e2e`: Playwright Page Object Model and tests automating Sys2000 user maintenance flows.

### Modified Capabilities
- None

## Approach
Implement a multi-tier test pyramid:
1. **Infrastructure**: Stabilize runner markers (`smoke`), configure linting (`ruff`), and install mock test client dependencies (`httpx`).
2. **API/Mock Layer**: Decouple test execution from external providers using `FastAPI` mocks and `apiclients/`.
3. **E2E/POM Layer**: Automate manual regression cases following strict Page Object Model conventions (private locators, explicit waits, decoupled business actions).
4. **Agent Roles**: Distribute specialized tasks among `pipeline-engineer`, `test-writer`, and `code-auditor`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `.agents/agents/` | New | Add `pipeline-engineer.md` and `code-auditor.md` agent specifications |
| `.agents/hooks.json` | Modified | Ensure hook commands execute reliably without breaking protojson unmarshaling |
| `requirements.txt` | Modified | Add `httpx`, `pytest-cov`, and `ruff` |
| `apiclients/ocr_client.py` | New | API client for OCR service mock |
| `tests/api/test_ocr_service.py` | New | Integration tests with `@pytest.mark.api` |
| `pageobjects/user_management_page.py` | New | POM for Sys2000 user maintenance |
| `tests/e2e/test_user_management.py` | New | E2E test suite for manual test R-055429 |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Remote QA Sys2000 environment timeout/unavailability | High | Isolate CI and local smoke checks to deterministic API mock tests; run E2E against remote environment with explicit timeouts |
| Slow provider OCR test blocking suite | Medium | Test timeout endpoint with short client timeout (e.g. 1s) expecting TimeoutException rather than sleeping 10s |

## Rollback Plan
Revert changes to `requirements.txt` and delete newly added test/pageobject files. The existing `tests/e2e/test_login.py` will remain intact.

## Dependencies
- Python 3.13 virtual environment (`.venv`)
- Playwright browser binaries (already installed)

## Success Criteria
- [ ] `.venv/bin/pytest -m smoke` and `.venv/bin/pytest -m api` pass deterministically in under 3 seconds.
- [ ] `tests/api/test_ocr_service.py` covers happy path, 422 error, and timeout scenarios.
- [ ] `pageobjects/user_management_page.py` exposes business actions matching manual test R-055429.
