# Proposal: Archive and Promote Specifications

## Intent
Complete the SDD lifecycle for previously implemented changes by producing missing verification reports, promoting living architectural specifications into `openspec/specs/`, and moving completed changes into `openspec/changes/archive/` using ISO date prefixes.

## Scope

### In Scope
- Generate formal `verify-report.md` for `ai-test-normalizer`, `unified-runner-reporting`, and `static-type-checking-gate`.
- Populate canonical living specs under `openspec/specs/`:
  - `page-object-architecture/spec.md`
  - `doc-runner-engine/spec.md`
  - `canonical-test-format/spec.md`
  - `allure-runner-reporting/spec.md`
  - `static-type-checking-gate/spec.md`
- Archive completed changes into `openspec/changes/archive/` with ISO date prefixes:
  - `2026-10-12-vertical-slice-automation`
  - `2026-10-12-doc-driven-testing`
  - `2026-10-30-ai-test-normalizer`
  - `2026-10-30-unified-runner-reporting`
  - `2026-10-30-static-type-checking-gate`
- Add unit tests verifying OpenSpec structure, canonical specs integrity, and archive completeness.

### Out of Scope
- Modifying application runtime code or test runner implementation.

## Capabilities

### New Capabilities
- `canonical-specifications`: Long-lived authoritative domain and architectural specifications in `openspec/specs/`.
- `openspec-integrity-testing`: Automated test validation of OpenSpec specifications and archive structure.

### Modified Capabilities
- `sdd-lifecycle`: Transitions implemented temporary delta changes to permanent archived states with formal verification records.

## Approach
1. Synthesize verification results and create formal `verify-report.md` for unverified changes.
2. Draft RFC 2119 compliant canonical specifications in `openspec/specs/` consolidating the framework architecture.
3. Move completed change directories to `openspec/changes/archive/YYYY-MM-DD-<change-name>/`.
4. Implement automated integrity assertions in `tests/unit/test_openspec_integrity.py`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `openspec/changes/` | Modified | Add verification reports; move completed changes to `archive/` |
| `openspec/specs/` | New | Create 5 canonical specification documents |
| `tests/unit/test_openspec_integrity.py` | New | Unit tests verifying specs and archive integrity |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Broken references to active changes | Low | Maintain historical changelogs; verify tests reflect archived paths |
| Spec drift from implementation | Low | Base canonical specs directly on existing validated implementations |

## Rollback Plan
Move archived change folders back to `openspec/changes/` and remove newly added specs in `openspec/specs/` via git checkout.

## Dependencies
- Existing test suites and verified implementations in repository.

## Success Criteria
- [x] Formal `verify-report.md` created for `ai-test-normalizer`, `unified-runner-reporting`, and `static-type-checking-gate`.
- [x] 5 canonical specs populated in `openspec/specs/` matching system design.
- [x] 5 completed changes archived with ISO date prefixes under `openspec/changes/archive/`.
- [x] Unit tests pass verifying OpenSpec directory integrity and canonical spec contents.
