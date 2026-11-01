# Proposal: AI Test Normalizer for Free-Form QA Specifications

## Intent
Exelixi QA receives test specifications drafted in free-form style by developers or manual QA analysts in Microsoft Word (`.docx`) or PDF formats. Currently, these documents feature heterogeneous layouts, narrative steps, missing URLs or credentials, manual workflow blockers, and unformatted assertions. The existing `parsers/docx_parser.py` and `runners/doc_runner.py` expect a strict canonical structure with exact keywords (`Link:`, `Caso N:`, `Objetivo de la Prueba:`, `Usuario:`, `Clave:`, and standard step verbs).

This change introduces an automated **normalizer** pipeline that bridges free-form specifications with the canonical automation engine:
1. Ingest free-form documents (`.docx` or `.pdf`) and deterministically extract raw text, tables, and visual evidence into an isolated build workspace.
2. Detect gaps and ambiguities (missing URLs, plaintext credentials, missing assertions, ambiguous targets, unsupported manual flows) without hallucinating missing data.
3. Facilitate structured AI normalization via the `test-normalizer` subagent producing an intermediate validated JSON representation.
4. Strictly validate JSON grounding: verify source quotes verbatim, enforce environment variable credentials (`${QA_USER_<ROL>}`, `${QA_PASS_<ROL>}`), and prevent PII leakage (cédulas, RIF, emails).
5. Render canonical, single-case `.docx` documents in `normalized/` matching `canonical-test-format` specifications, routing manual steps to `Pendiente manual N:` so they are safely skipped by `DocxParser`.
6. Integrate with `runners/doc_runner.py` to gate execution based on normalization state (`READY` executes; `NEEDS_INFO` or `UNSUPPORTED` halt with exit code 2).

## Scope

### In Scope
- **Package `normalizer/`**:
  - `extract.py`: Extraction of text, tables, and embedded images from `.docx`/`.pdf` to `build/<id>/`.
  - `gaps.py`: Deterministic detection of test specification gaps and assignment of case states (`READY`, `NEEDS_INFO`, `UNSUPPORTED`).
  - `rules.yaml`: Configurable keyword lists for actions, manual flows, and gap detection heuristics.
  - `schema.py`: Typed data schemas for intermediate normalization models (`NormalizedCase`, `NormalizedStep`, `MissingGap`, `TestSpecification`).
  - `grounding.py`: Anti-hallucination, quote verification, and PII/leakage validation routines.
  - `render.py`: Generation of canonical `.docx` files (one per case) compatible with `DocParser.parse`.
  - `cli.py`: Unified CLI entrypoints for extract, validate, and render workflows.
- **Sub-Agent Integration**: Pairing with `.agents/agents/test-normalizer.md` for AI-assisted transformation into grounded JSON.
- **Runner Gating & Credential Interpolation**:
  - Check "Estado de normalización" in `runners/doc_runner.py`; abort execution with exit code 2 if not `READY`.
  - Resolve `${QA_USER_<ROL>}` and `${QA_PASS_<ROL>}` environment variables dynamically.
  - Purge hardcoded real credentials and analyst names from runner fallbacks.
- **Evaluation Harness**: Automated evaluation script measuring gap detection accuracy, grounding adherence, and round-trip fidelity.

### Out of Scope
- Direct LLM calls within Python package source code (all LLM inference is performed exclusively by the `test-normalizer` subagent).
- Direct browser automation or visual regression in the normalizer (execution remains the sole responsibility of `runners/doc_runner.py`).
- Mutating or overwriting original source documents in `docs-qa/`.

## Capabilities

### New Capabilities
- `test-extraction`: Deterministic extraction of raw text, tables, and screenshots from unstructured `.docx` and `.pdf` files.
- `gap-detection`: Rule-based analysis identifying missing URLs, credentials, ungrounded steps, and unsupported flows.
- `grounded-json-validation`: Multi-check grounding validation ensuring verbatim quotes, parameterized credentials, and zero PII leaks.
- `canonical-docx-renderer`: Generator of canonical `.docx` test files adhering to `canonical-test-format` and verifying 100% round-trip compatibility with `DocParser.parse`.
- `normalization-evaluation`: Synthetic benchmarking suite quantifying normalization quality and hallucination rate.

### Modified Capabilities
- `doc-test-runner`: Enhanced to enforce the normalization state gate (`READY` vs. `NEEDS_INFO`/`UNSUPPORTED`) and expand environment variables in credentials.

## Approach
The pipeline operates in clearly separated stages:
```
Free-Form Document (.docx / .pdf)
   │
   ▼
1. Deterministic Extraction (normalizer.extract) ──► build/<id>/ (text + images)
   │
   ▼
2. Rule-based Gap Analysis (normalizer.gaps) ──► Initial Gap Report
   │
   ▼
3. AI Normalization (test-normalizer subagent) ──► normalized/<id>.json
   │
   ▼
4. Grounding & Anti-Leak Validation (normalizer.grounding) ──► Pass / Fail Gate
   │
   ▼
5. Canonical Rendering (normalizer.render) ──► normalized/<case_id>.docx (1 per case)
   │
   ▼
6. Runner Execution (runners.doc_runner) ──► Exit 2 on NEEDS_INFO/UNSUPPORTED, else Run
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `normalizer/` | New | Core normalizer modules (`extract.py`, `gaps.py`, `schema.py`, `grounding.py`, `render.py`, `cli.py`, `rules.yaml`) |
| `runners/doc_runner.py` | Modified | Add normalization gate check (exit code 2) and `${VAR}` credential expansion |
| `tests/unit/` | New | Comprehensive unit tests for extraction, gap detection, schema, grounding, rendering, and CLI |
| `tests/integration/` | New | Integration tests verifying runner exit codes and canonical round-trip with `DocParser` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Hallucination of selectors or credentials by AI agent | Medium | Strict 3-point grounding check in `grounding.py`: verbatim source quotes, literal value matching, and regex rejection of PII |
| Parsing failure of manual steps in `DocParser` | Low | Manual steps are explicitly rendered as `Pendiente manual N: <motivo>` (never as `Paso N:`), ensuring `DocParser` safely ignores them |
| Malformed Word table formatting in generated canonical `.docx` | Low | Round-trip unit test asserting `DocParser.parse(render(case)) == case` for all generated files |
| Secrets leakage in test fixtures or logs | Low | All tests utilize synthetic documents generated in-memory via `python-docx`; real documents in `docs-qa/` remain untouched |

## Rollback Plan
Delete the `normalizer/` package directory and new tests under `tests/unit/test_normalizer_*` and `tests/integration/test_doc_runner_normalization_gate.py`. Revert changes in `runners/doc_runner.py` via git. The core `parsers/`, `pageobjects/`, and `reporting/` packages will remain fully functional.

## Dependencies
- `python-docx` (already in `.venv`)
- `pypdf` (already in `.venv`)
- `pydantic` or standard Python `dataclasses`
- `pyyaml` for `rules.yaml`
