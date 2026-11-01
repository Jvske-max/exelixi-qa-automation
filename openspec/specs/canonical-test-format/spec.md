# Specification: Canonical Test Specification Format

## Overview

The Canonical Test Specification Format defines the standardized contract for QA test specifications. Free-form narratives and developer documentation are converted into this authoritative schema to enable automated parsing by `parsers/docx_parser.py` and seamless execution by `runners/doc_runner.py`. The specification enforces strict structural layout, closed action vocabularies, anti-hallucination source quote grounding, and PII redaction rules.

## Requirements

### 1. File Organization and Identification Table

Canonical specifications MUST represent exactly one test case per document (`.docx`).

- Documents MUST begin with an "Identificación" table comprising 2 rows and 9 standard fields:
  - `Fecha`
  - `Módulo`
  - `Identificador del caso`
  - `Descripción corta`
  - `Descripción completa`
  - `Ambiente de prueba`
  - `Analista Programador`
  - `Analista de prueba`
  - `Estado de normalización` (`READY`, `NEEDS_INFO`, or `UNSUPPORTED`)
- The table values SHALL NOT be empty, and `Estado de normalización` MUST accurately reflect the presence of blocking gaps.

### 2. Paragraph Ordering and Metadata Declarations

Metadata paragraphs MUST follow a strict sequential ordering preceding step definitions:

1. `Link: <url>` declaring the entry-point web address.
2. `Caso N: <título>` declaring case number and title (MUST precede any subsequent narrative paragraph mentioning "caso").
3. `Objetivo de la Prueba: <descripción>` stating business objectives.
4. `Usuario: ${QA_USER_<ROL>}` and `Clave: ${QA_PASS_<ROL>}` declaring role-based credentials.
5. Steps declared sequentially as `Paso N: <acción>`.
- Plaintext credentials MUST NOT be written inline within step definitions or metadata lines.

### 3. Closed Action Vocabulary

Step text MUST strictly adhere to the five closed action patterns:

- `navigate`: MUST follow `Paso N: navegar a <url>`.
- `fill`: MUST follow `Paso N: escribir <valor> en <campo>`.
- `click`: MUST follow `Paso N: clic en <texto visible>`. Dropdowns SHALL be represented as two consecutive click steps.
- `verify`: MUST follow `Paso N: verificar <texto visible>`.
- `manual`: MUST follow `Pendiente manual N: <motivo>`.
  - Manual steps SHALL NEVER use the `Paso N:` prefix to prevent automated runners from attempting browser execution.

### 4. Anti-Hallucination Grounding and PII Protection

Every step generated through normalizer pipelines MUST satisfy grounding checks:

- Every step MUST include a `source_quote` attribute matching verbatim text extracted from the source document.
- Steps SHALL NOT introduce fabricated URLs, credentials, or values not present in the original narrative.
- Documents MUST NOT include raw Personally Identifiable Information (PII) such as Venezuelan cédulas (`V-...`), RIFs (`J-...`), personal emails, or plaintext passwords.

---

### Scenarios

#### Scenario: Canonical Document Ingestion Round-Trip
- **Given** a canonical `.docx` specification file containing the 9 identification fields and closed-vocabulary steps
- **When** `DocParser.parse(doc_path)` processes the document
- **Then** the resulting `TestCase` object MUST contain all metadata attributes
- **And** all parsed steps SHALL match expected action types (`navigate`, `fill`, `click`, `verify`)
- **And** `TestCase.normalization_state` MUST evaluate to `"READY"`.

#### Scenario: Manual Step Ignored by Browser Dispatcher
- **Given** a narrative step describing a CAPTCHA, OTP verification, or file upload
- **When** the canonical normalizer renders the step
- **Then** it MUST format the entry as `Pendiente manual N: <motivo>`
- **And** `parsers/docx_parser.py` SHALL NOT dispatch a browser action for that line.

#### Scenario: Missing URL Assigns NEEDS_INFO State
- **Given** a source specification missing an entry point URL or `Link:` definition
- **When** the gap analyzer scans the document
- **Then** a blocking gap of type `missing_url` MUST be registered
- **And** the document's `Estado de normalización` SHALL be set to `"NEEDS_INFO"`.
