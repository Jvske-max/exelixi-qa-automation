# Tasks: AI Test Normalizer for Free-Form QA Specifications

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 900 - 1100 lines |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 4 PRs (PR1: T1 & T2 Extraction/Gaps; PR2: T3 Grounding & Schema; PR3: T4 Rendering & Round-Trip; PR4: T5, T6, T7 Runner & CLI) |
| Delivery strategy | chained-pr |
| Chain strategy | serial |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: serial
400-line budget risk: High

### Suggested Work Units

| Unit | Task | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|---|
| 1 | T1 | Ingest unstructured .docx/.pdf to text and images | PR 1 | `python -m pytest tests/unit/test_normalizer_extract.py -q` | Synthetic docx fixtures | Delete `normalizer/extract.py` |
| 2 | T2 | Rule-based gap detection and case state determination | PR 1 | `python -m pytest tests/unit/test_normalizer_gaps.py -q` | `normalizer/rules.yaml` | Delete `normalizer/gaps.py` |
| 3 | T3 | Schema definition & 3-point grounding validation | PR 2 | `python -m pytest tests/unit/test_normalizer_grounding.py -q` | Grounding check fixtures | Delete `normalizer/schema.py`, `grounding.py` |
| 4 | T4 | Canonical `.docx` rendering & round-trip verification | PR 3 | `python -m pytest tests/unit/test_normalizer_render.py -q` | In-memory `DocParser.parse` | Delete `normalizer/render.py` |
| 5 | T5 | Runner integration: state gating (exit code 2) & env vars | PR 4 | `python -m pytest tests/integration/test_doc_runner_normalization_gate.py -q` | Headless Playwright runner | Revert `runners/doc_runner.py` |
| 6 | T6 | Normalizer CLI entrypoints & sub-agent wiring | PR 4 | `python -m pytest tests/unit/test_normalizer_cli.py -q` | CLI subprocess invocations | Delete `normalizer/cli.py` |
| 7 | T7 | Normalization quality evaluation harness | PR 4 | `python -m pytest tests/unit/test_normalizer_eval.py -q` | Synthetic benchmark suite | Delete `normalizer/evaluate.py` |

---

## T1: Deterministic Extraction (`normalizer/extract.py`)
Extract raw text paragraphs, table structures, and embedded visual screenshots from free-form `.docx` and `.pdf` files into an isolated build folder (`build/<id>/`).

- **First Red Test**:
  - Command: `python -m pytest tests/unit/test_normalizer_extract.py -q`
  - Test case: `tests/unit/test_normalizer_extract.py::test_extract_docx_paragraphs_tables_and_images` asserting that a synthetic `.docx` with a title, a sample table, two paragraphs, and an inline screenshot is unpacked into `build/<id>/content.json`, `build/<id>/raw_text.txt`, and `build/<id>/images/image1.png`.
- **Exit Criteria**:
  - `normalizer/extract.py` exports `extract_document(doc_path: Path, out_dir: Path) -> ExtractionResult`.
  - Synthetic test suite passes: `python -m pytest tests/unit/test_normalizer_extract.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.

---

## T2: Rule-Based Gap Analysis (`normalizer/gaps.py` & `normalizer/rules.yaml`)
Deterministically scan extracted content to detect missing URLs, missing credentials, plaintext passwords, ambiguous steps, and unsupported flows without AI inference.

- **First Red Test**:
  - Command: `python -m pytest tests/unit/test_normalizer_gaps.py -q`
  - Test case: `tests/unit/test_normalizer_gaps.py::test_detect_missing_url_and_credentials_blocking_gaps` asserting that narrative text without `Link:` or credentials returns gaps `missing_url` and `missing_credentials` with severity `blocking`, mapping the case state to `NEEDS_INFO`.
- **Exit Criteria**:
  - `normalizer/rules.yaml` defines editable keyword lists for navigation, fill, click, verify, and unsupported indicators (OTP, SISIP, payment gateways).
  - `normalizer/gaps.py` correctly classifies all 7 gap types and accurately assigns `READY`, `NEEDS_INFO`, or `UNSUPPORTED`.
  - Unit tests pass: `python -m pytest tests/unit/test_normalizer_gaps.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.

---

## T3: Data Schema & Grounding Validation (`normalizer/schema.py` & `normalizer/grounding.py`)
Implement data models for intermediate normalized JSON and enforce the 3-point anti-hallucination and anti-leak validation gate.

- **First Red Test**:
  - Command: `python -m pytest tests/unit/test_normalizer_grounding.py -q`
  - Test case: `tests/unit/test_normalizer_grounding.py::test_reject_step_with_fabricated_source_quote_or_pii` asserting that a step with a `source_quote` not matching original text or containing a Venezuelan cédula / plaintext password fails validation with descriptive errors.
- **Exit Criteria**:
  - `normalizer/schema.py` validates closed vocabulary actions (`navigate`, `fill`, `click`, `verify`, `manual`).
  - `normalizer/grounding.py` strictly checks:
    1. Verbatim presence of `source_quote` in original text.
    2. Literal match of values/URLs or conformance to `${QA_USER_<ROL>}` / `${QA_PASS_<ROL>}`.
    3. Rejection of cédulas, RIF, and personal emails.
  - Unit tests pass: `python -m pytest tests/unit/test_normalizer_grounding.py tests/unit/test_normalizer_schema.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.

---

## T4: Canonical Rendering, Case Splitting & Round-Trip (`normalizer/render.py`)
Transform normalized JSON into canonical `.docx` files in `normalized/` (one file per case) and prove 100% round-trip fidelity with `DocParser.parse`.

- **First Red Test**:
  - Command: `python -m pytest tests/unit/test_normalizer_render.py -q`
  - Test case: `tests/unit/test_normalizer_render.py::test_render_canonical_docx_roundtrip_docparser` asserting that a multi-case JSON generates independent canonical `.docx` files whose parsed `TestCase` matches original step actions, targets, values, and credentials, with manual steps rendered as `Pendiente manual N:`.
- **Exit Criteria**:
  - Generates 2-row "Identificación" table with all 9 standard fields including "Estado de normalización".
  - Renders manual steps as `Pendiente manual N: <motivo>` (never as `Paso N:`).
  - Round-trip assertion passes: `DocParser.parse(rendered_docx)` produces equivalent `StepDefinition` list.
  - Unit tests pass: `python -m pytest tests/unit/test_normalizer_render.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.

---

## T5: Runner Integration & Environment Credential Expansion (`runners/doc_runner.py`)
Integrate normalization metadata into `runners/doc_runner.py`: abort non-READY tests with exit code 2 and interpolate `${QA_...}` credentials.

- **First Red Test**:
  - Command: `python -m pytest tests/integration/test_doc_runner_normalization_gate.py -q`
  - Test case: `tests/integration/test_doc_runner_normalization_gate.py::test_runner_aborts_with_exit_code_2_on_needs_info` asserting that invoking `doc_runner` with a case marked `NEEDS_INFO` or `UNSUPPORTED` raises `SystemExit(2)`.
- **Exit Criteria**:
  - `DocRunner` inspects "Estado de normalización"; exits with code 2 on `NEEDS_INFO` or `UNSUPPORTED`.
  - `DocRunner` expands `${QA_USER_<ROL>}` and `${QA_PASS_<ROL>}` from `os.environ`.
  - Hardcoded default names/passwords in `runners/doc_runner.py` are cleaned up.
  - Integration tests pass: `python -m pytest tests/integration/test_doc_runner_normalization_gate.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.

---

## T6: Unified CLI Entrypoints (`normalizer/cli.py`)
Expose command-line interfaces for extraction, validation, and rendering used by human developers and the `test-normalizer` subagent.

- **First Red Test**:
  - Command: `python -m pytest tests/unit/test_normalizer_cli.py -q`
  - Test case: `tests/unit/test_normalizer_cli.py::test_cli_validate_and_render_workflow` asserting that running `python -m normalizer.cli validate` and `python -m normalizer.cli render` executes cleanly via CLI arguments.
- **Exit Criteria**:
  - Supports `python -m normalizer.extract <doc> --out <dir>`.
  - Supports `python -m normalizer.cli validate <json> --original <dir>`.
  - Supports `python -m normalizer.cli render <json> --out <dir>`.
  - Unit tests pass: `python -m pytest tests/unit/test_normalizer_cli.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.

---

## T7: Normalization Quality Evaluation Harness (`normalizer/evaluate.py`)
Build an automated evaluation benchmark to measure precision, recall, hallucination rate, and round-trip compliance across synthetic test datasets.

- **First Red Test**:
  - Command: `python -m pytest tests/unit/test_normalizer_eval.py -q`
  - Test case: `tests/unit/test_normalizer_eval.py::test_evaluate_synthetic_dataset_metrics` asserting that evaluation metrics calculate accuracy, precision, recall, and 0% hallucination rate on a controlled synthetic suite.
- **Exit Criteria**:
  - Computes precision and recall for gap detection.
  - Verifies 0 ungrounded facts or PII leaks across benchmark cases.
  - Verifies 100% round-trip conversion rate for valid cases.
  - Unit tests pass: `python -m pytest tests/unit/test_normalizer_eval.py -q`.
  - Smoke tests pass: `python -m pytest -m smoke -q`.
  - Linter passes: `python -m ruff check .`.
