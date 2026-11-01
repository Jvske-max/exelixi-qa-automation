# Tasks: Archive Completed Changes and Promote Canonical Specifications

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 350 - 450 lines (docs + tests) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | 2 PRs (PR1: Verification & Canonical Specs; PR2: Archival & Integrity Gate) |
| Delivery strategy | chained-pr |
| Chain strategy | serial |

---

## Phase 1: Verification Reports & Integrity Tests

### T1.1: [x] [RED] OpenSpec Structure & Verification Integrity Tests
Create unit tests asserting existence of `verify-report.md` for completed changes, canonical specs in `openspec/specs/`, and archived directories.
- **File**: `tests/unit/test_openspec_integrity.py`
- **Command**: `python -m pytest tests/unit/test_openspec_integrity.py -q`
- **Exit Criteria**: Tests fail (RED) due to missing verify reports and canonical specs.

### T1.2: [x] [GREEN] Generate Verification Reports
Synthesize test executions and generate compliant `verify-report.md` files for unverified completed changes.
- **Files**:
  - `openspec/changes/ai-test-normalizer/verify-report.md`
  - `openspec/changes/unified-runner-reporting/verify-report.md`
  - `openspec/changes/static-type-checking-gate/verify-report.md`
- **Exit Criteria**: Verification report existence assertions pass.

### T1.3: [x] [REFACTOR] Report Formatting & Consistency
Standardize report headings, evidence metrics, and markdown formatting across all new verification reports.
- **Verification**: Markdown formatting consistency and integrity assertions pass.

---

## Phase 2: Canonical Specifications Promotion

### T2.1: [x] [RED] Canonical Specification Requirement Tests
Extend `tests/unit/test_openspec_integrity.py` with assertions verifying the presence of all 5 canonical living specs and their required sections.
- **File**: `tests/unit/test_openspec_integrity.py`
- **Command**: `python -m pytest tests/unit/test_openspec_integrity.py -k test_canonical_specs -q`
- **Exit Criteria**: Tests fail (RED) awaiting spec file creation.

### T2.2: [x] [GREEN] Draft Canonical Specifications
Draft and place RFC 2119 compliant canonical specifications into `openspec/specs/`.
- **Files**:
  - `openspec/specs/page-object-architecture/spec.md`
  - `openspec/specs/doc-runner-engine/spec.md`
  - `openspec/specs/canonical-test-format/spec.md`
  - `openspec/specs/allure-runner-reporting/spec.md`
  - `openspec/specs/static-type-checking-gate/spec.md`
- **Exit Criteria**: `python -m pytest tests/unit/test_openspec_integrity.py -k test_canonical_specs -q` passes (GREEN).

### T2.3: [x] [REFACTOR] Specification Harmonization
Verify cross-spec terminology consistency and remove obsolete temporary delta references.
- **Verification**: Specs lint cleanly and pass all integrity assertions.

---

## Phase 3: Change Archiving & Verification

### T3.1: [x] [RED] Archive Directory Structure Tests
Add tests verifying completed changes are archived with ISO date prefixes (`YYYY-MM-DD-<name>`) and active changes directory is clean.
- **File**: `tests/unit/test_openspec_integrity.py`
- **Command**: `python -m pytest tests/unit/test_openspec_integrity.py -k test_archive_structure -q`
- **Exit Criteria**: Tests fail (RED) before directory migration.

### T3.2: [x] [GREEN] Archive Changes & Validate Suite
Move completed change folders to `openspec/changes/archive/` with ISO date prefixes:
- `2026-10-12-vertical-slice-automation`
- `2026-10-12-doc-driven-testing`
- `2026-10-30-ai-test-normalizer`
- `2026-10-30-unified-runner-reporting`
- `2026-10-30-static-type-checking-gate`
- **Exit Criteria**: `python -m pytest tests/unit/test_openspec_integrity.py -q` passes (GREEN).

### T3.3: [x] [REFACTOR] Code Auditor & Full Regression Gate
Execute comprehensive regression testing, type checking, and code audit.
- **Commands**:
  - `python -m pytest tests/unit tests/integration -q`
  - `python -m mypy normalizer pageobjects parsers reporting runners tools`
  - `code-auditor audit`
- **Exit Criteria**: Full test suite passes; zero type check errors; code auditor reports zero critical issues.
