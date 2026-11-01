# Proposal: Unified Runner Allure Reporting

## Intent
Integrate document-driven test execution (`DocRunner`) with Allure reporting via `allure_commons`. Automated runs from parsed test documents (`.docx`/`.pdf`) will emit standard Allure test results, hierarchical steps, execution statuses, durations, masked error traces, and screenshot attachments into a configurable `--allure-dir` alongside PDF evidence.

## Scope

### In Scope
- **Allure Reporter**: Add `AllureReporter` in `reporting/allure_reporter.py` using `allure_commons` / `AllureFileLogger` to emit Allure v2 JSON results and containers.
- **DocRunner CLI & API**: Add `--allure-dir` flag and `allure_dir` parameter to `DocRunner` for optional or concurrent Allure output.
- **Event Mapping**: Map test cases to Allure containers/results with steps, statuses (`passed`/`failed`/`broken`), timing, masked errors, and PNG screenshots.
- **Backward Compatibility**: Keep existing `PDFReporter` functionality intact.
- **Strict TDD**: Comprehensive unit and integration test coverage for Allure reporting.

### Out of Scope
- Hosting web UI or running `allure serve` (handled externally).
- Modifying standard pytest Allure fixtures outside `DocRunner`.

## Capabilities

### New Capabilities
- `allure-runner-reporter`: Emits Allure v2 JSON results, step events, containers, and screenshot attachments from standalone `DocRunner` runs.

### Modified Capabilities
- `doc-test-runner`: Supports `--allure-dir` and dispatches lifecycle events and screenshots to Allure and PDF reporters.

## Approach
- Implement `reporting/allure_reporter.py` wrapping `allure_commons.reporter.AllureReporter` and `AllureFileLogger`.
- Hook `DocRunner` test and step lifecycles, attaching PNG screenshots and recording masked error traces on failures.
- Keep reporters decoupled so runners can output PDF, Allure, or both.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `reporting/allure_reporter.py` | New | Allure lifecycle manager and result emitter |
| `runners/doc_runner.py` | Modified | Add `--allure-dir` flag and reporter dispatch hooks |
| `reporting/__init__.py` | Modified | Export `AllureReporter` |
| `tests/unit/test_allure_reporter.py` | New | Unit tests for Allure report generation |
| `tests/integration/test_doc_runner_allure.py` | New | Integration test for DocRunner with Allure |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Credential leaks in Allure step details | Low | Mask sensitive fields before reporting to Allure |
| Duplicate screenshot storage overhead | Low | Reuse captured PNG evidence across reporters |

## Rollback Plan
Revert changes to `runners/doc_runner.py` and delete `reporting/allure_reporter.py`. `DocRunner` returns to PDF reporting only.

## Dependencies
- `allure-commons`
- `allure-pytest`

## Success Criteria
- [ ] `DocRunner` accepts `--allure-dir` and emits valid Allure result JSONs and attachments.
- [ ] Steps, statuses (`passed`/`failed`/`broken`), and PNG screenshots appear in Allure results.
- [ ] PDF report generation continues working unmodified.
- [ ] Strict TDD with high test coverage for new reporter code.
