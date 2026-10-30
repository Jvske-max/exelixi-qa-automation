"""Unit tests for grounding checks and CLI validation (T3: normalizer.grounding & normalizer.cli)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from normalizer.cli import main as cli_main
from normalizer.gaps import Gap
from normalizer.grounding import Violation, check
from normalizer.schema import Case, NormalizedDoc, Step


@pytest.fixture
def synthetic_dump() -> dict:
    """Fixture providing a synthetic dump without sensitive or real data."""
    return {
        "meta": {"módulo": "Facturación", "portal": "https://qa.example.test/portal"},
        "paragraphs": [
            {"line": 1, "text": "Iniciamos el proceso en el portal", "images": []},
            {"line": 2, "text": "Pulsamos el botón Guardar registro", "images": []},
            {"line": 3, "text": "Escribimos FACTURA-2026 en el campo Código", "images": []},
            {"line": 4, "text": "El comprobante fue generado exitosamente", "images": []},
        ],
        "cases": [{"n": 1, "title": "Generar factura", "start_line": 1, "end_line": 4}],
        "links": ["https://qa.example.test/login"],
    }


@pytest.mark.smoke
def test_grounding_rule_a_source_quote(synthetic_dump: dict) -> None:
    """Regla (a): source_quote must be substring of dump text, collapsing spaces and case-insensitive with accents preserved."""
    # Positive case: exact quote with different spacing and casing
    doc_pos = NormalizedDoc(
        meta={"módulo": "Facturación"},
        cases=[
            Case(
                n=1,
                title="Prueba",
                objective="Validar quote",
                url="https://qa.example.test/portal",
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote="pulsamos   el botón  guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, synthetic_dump)
    assert not any(v.type == "ungrounded_quote" for v in violations_pos)

    # Negative case 1: hallucinated quote not present in dump
    doc_neg_missing = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba",
                objective="Quote falso",
                steps=[
                    Step(
                        action="click",
                        target="Boton Inexistente",
                        source_quote="Hacemos clic en el boton inexistente",
                        source_ref="Línea 99",
                    )
                ],
            )
        ],
    )
    violations_neg1 = check(doc_neg_missing, synthetic_dump)
    assert any(v.type == "ungrounded_quote" for v in violations_neg1)

    # Negative case 2: quote mismatching accents (e.g., 'boton' without accent vs 'botón' in dump)
    doc_neg_accent = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba",
                objective="Quote sin acento",
                steps=[
                    Step(
                        action="click",
                        target="Guardar",
                        source_quote="Pulsamos el boton Guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations_neg2 = check(doc_neg_accent, synthetic_dump)
    assert any(v.type == "ungrounded_quote" for v in violations_neg2)


@pytest.mark.smoke
@pytest.mark.parametrize("short_quote", ["a", "de", "en", "", "palabra123", "a b"])
def test_grounding_source_quote_length_and_word_count_rejected(synthetic_dump: dict, short_quote: str) -> None:
    """Verify that source_quotes with < 8 chars or < 2 words are rejected with invalid_source_quote_length."""
    doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Short Quote Test",
                objective="Verificar rechazo de quotes cortos o con pocas palabras",
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote=short_quote,
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations = check(doc, synthetic_dump)
    assert any(v.type == "invalid_source_quote_length" for v in violations)


@pytest.mark.smoke
def test_grounding_source_quote_valid_length_and_words(synthetic_dump: dict) -> None:
    """Verify that source_quote with >= 8 chars and >= 2 words in dump passes without invalid_source_quote_length."""
    doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Valid Quote Test",
                objective="Verificar aceptación de quotes válidos",
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote="Pulsamos el botón Guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations = check(doc, synthetic_dump)
    assert not any(v.type == "invalid_source_quote_length" for v in violations)
    assert not any(v.type == "ungrounded_quote" for v in violations)




@pytest.mark.smoke
def test_grounding_rule_b_url(synthetic_dump: dict) -> None:
    """Regla (b): URLs in Case.url or steps must appear literal in dump paragraphs or meta."""
    # Positive case: URL in meta/links
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Navegación",
                objective="Ir a portal",
                url="https://qa.example.test/portal",
                steps=[
                    Step(
                        action="navigate",
                        target="https://qa.example.test/login",
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, synthetic_dump)
    assert not any(v.type == "ungrounded_url" for v in violations_pos)

    # Negative case: URL not in dump
    doc_neg = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Navegación",
                objective="Ir a portal externo",
                url="https://unauthorized-domain.test/home",
                steps=[],
            )
        ],
    )
    violations_neg = check(doc_neg, synthetic_dump)
    assert any(v.type == "ungrounded_url" for v in violations_neg)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "partial_url",
    [
        "https://example.com/portal",       # Truncated path (dump has /portal/login)
        "https://example.com",              # Bare host without path
        "https://portal.example.com",       # Subdomain variant
        "https://example.com/port",         # Prefix of path
    ],
)
def test_grounding_rule_b_url_truncated_or_partial_rejected(partial_url: str) -> None:
    """Verify that truncated, partial, or prefix URLs are rejected against full dump URLs."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Navegamos a https://example.com/portal/login para iniciar", "images": []},
        ],
        "cases": [{"n": 1, "title": "Login", "start_line": 1, "end_line": 1}],
        "links": ["https://example.com/portal/login"],
    }

    # Case URL check
    doc_case_url = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Partial URL in case",
                objective="Verificar rechazo",
                url=partial_url,
                steps=[],
            )
        ],
    )
    violations_case = check(doc_case_url, dump)
    assert any(v.type == "ungrounded_url" for v in violations_case)

    # Step URL check
    doc_step_url = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Partial URL in step",
                objective="Verificar rechazo",
                steps=[
                    Step(
                        action="navigate",
                        target=partial_url,
                        source_quote="Navegamos a https://example.com/portal/login para iniciar",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_step = check(doc_step_url, dump)
    assert any(v.type == "ungrounded_url" for v in violations_step)


@pytest.mark.smoke
def test_grounding_rule_b_url_exact_match_trailing_slash_accepted() -> None:
    """Verify that exact URL match with or without trailing slash is accepted."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Acceder a https://example.com/portal/login/ desde el navegador", "images": []},
        ],
        "cases": [{"n": 1, "title": "Login", "start_line": 1, "end_line": 1}],
        "links": ["https://example.com/portal/login/"],
    }
    # Test without trailing slash against dump with trailing slash
    doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Exact URL match",
                objective="Verificar coincidencia exacta normalizada",
                url="https://example.com/portal/login",
                steps=[
                    Step(
                        action="navigate",
                        target="https://example.com/portal/login",
                        source_quote="Acceder a https://example.com/portal/login/ desde el navegador",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations = check(doc, dump)
    assert not any(v.type == "ungrounded_url" for v in violations)


@pytest.mark.smoke
def test_grounding_navigate_target_must_be_valid_grounded_url() -> None:
    """Verify that navigate step target must be a valid URL present in dump, rejecting invalid paths or absent URLs."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Navegamos a https://qa.example.test/portal para iniciar", "images": []},
        ],
        "cases": [{"n": 1, "title": "Portal", "start_line": 1, "end_line": 1}],
        "links": ["https://qa.example.test/portal"],
    }

    # Negative check 1: arbitrary invalid string / non-URL target must be rejected with ungrounded_url
    doc_invalid_path = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Invalid Path",
                objective="Test navigate path validation",
                steps=[
                    Step(
                        action="navigate",
                        target="pagina/invalida",
                        source_quote="Navegamos a https://qa.example.test/portal para iniciar",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_invalid = check(doc_invalid_path, dump)
    assert any(v.type == "ungrounded_url" for v in violations_invalid)

    # Negative check 2: valid URL syntax but not present in dump must be rejected with ungrounded_url
    doc_absent_url = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Absent URL",
                objective="Test navigate absent URL validation",
                steps=[
                    Step(
                        action="navigate",
                        target="https://inexistente.test/login",
                        source_quote="Navegamos a https://qa.example.test/portal para iniciar",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_absent = check(doc_absent_url, dump)
    assert any(v.type == "ungrounded_url" for v in violations_absent)

    # Positive check: valid grounded URL passes
    doc_valid = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Valid URL",
                objective="Test navigate valid grounded URL",
                steps=[
                    Step(
                        action="navigate",
                        target="https://qa.example.test/portal",
                        source_quote="Navegamos a https://qa.example.test/portal para iniciar",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_valid = check(doc_valid, dump)
    assert not any(v.type == "ungrounded_url" for v in violations_valid)


@pytest.mark.smoke
def test_grounding_rule_c_fill_value(synthetic_dump: dict) -> None:
    """Regla (c): fill step value must appear literal in dump or be an env var ${VAR}."""
    # Positive case: literal value from dump text and ${VAR} reference
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Fill Case",
                objective="Llenar datos",
                steps=[
                    Step(
                        action="fill",
                        target="Código",
                        value="FACTURA-2026",
                        source_quote="Escribimos FACTURA-2026 en el campo Código",
                        source_ref="Línea 3",
                    ),
                    Step(
                        action="fill",
                        target="Usuario",
                        value="${QA_USER_TESTER}",
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    ),
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, synthetic_dump)
    assert not any(v.type == "ungrounded_fill_value" for v in violations_pos)

    # Negative case: value not in dump and not a valid ${VAR} format
    doc_neg = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Fill Case",
                objective="Llenar inventado",
                steps=[
                    Step(
                        action="fill",
                        target="Código",
                        value="VALOR_INVENTADO_NO_DUMP",
                        source_quote="Escribimos FACTURA-2026 en el campo Código",
                        source_ref="Línea 3",
                    )
                ],
            )
        ],
    )
    violations_neg = check(doc_neg, synthetic_dump)
    assert any(v.type == "ungrounded_fill_value" for v in violations_neg)


@pytest.mark.smoke
@pytest.mark.parametrize("cred_target", ["Clave", "Contraseña", "password", "PIN", "token"])
def test_grounding_fill_literal_credential_rejected(cred_target: str) -> None:
    """Verify that fill step for credential targets rejects literal values, even if present in dump."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": f"Escribimos mi_clave_literal en el campo {cred_target}", "images": []},
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }
    doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar clave",
                steps=[
                    Step(
                        action="fill",
                        target=cred_target,
                        value="mi_clave_literal",
                        source_quote=f"Escribimos mi_clave_literal en el campo {cred_target}",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations = check(doc, dump)
    assert any(v.type == "literal_credential_in_fill" for v in violations)


@pytest.mark.smoke
def test_grounding_fill_narrative_password_detected_on_generic_target() -> None:
    """Verify that passwords in narrative paragraphs are captured in known_passwords and rejected in fill even with non-standard targets."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Iniciamos con Clave: clave_en_relato_xyz para el portal", "images": []},
        ],
        "cases": [{"n": 1, "title": "Narrative Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }

    # Negative check: non-standard target with literal password from narrative text is rejected
    doc_literal = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Narrative Auth Case",
                objective="Llenar clave de relato",
                steps=[
                    Step(
                        action="fill",
                        target="CampoGenerico",
                        value="clave_en_relato_xyz",
                        source_quote="Iniciamos con Clave: clave_en_relato_xyz para el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations = check(doc_literal, dump)
    assert any(v.type == "literal_credential_in_fill" for v in violations), (
        "Expected literal_credential_in_fill when literal password extracted from narrative paragraph is used in fill"
    )

    # Positive check: using ${VAR} for the same field is accepted
    doc_env = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Narrative Auth Case",
                objective="Llenar clave con variable",
                steps=[
                    Step(
                        action="fill",
                        target="CampoGenerico",
                        value="${QA_GENERIC_PASS}",
                        source_quote="Iniciamos con Clave: clave_en_relato_xyz para el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_env = check(doc_env, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_env)


@pytest.mark.smoke
def test_grounding_fill_prose_narrative_password_detected_on_generic_target() -> None:
    """Verify narrative password in prose without colon is captured and rejected in fill with generic target."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {
                "line": 1,
                "text": "Ingresamos con la clave secret_flotante_123 al formulario",
                "images": [],
            },
        ],
        "cases": [{"n": 1, "title": "Narrative Prose Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }

    # Negative check: non-standard target with literal password from prose narrative is rejected
    doc_literal = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Narrative Prose Auth Case",
                objective="Llenar clave de relato en prosa",
                steps=[
                    Step(
                        action="fill",
                        target="campo_auxiliar",
                        value="secret_flotante_123",
                        source_quote="Ingresamos con la clave secret_flotante_123 al formulario",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations = check(doc_literal, dump)
    assert any(v.type == "literal_credential_in_fill" for v in violations), (
        "Expected literal_credential_in_fill when literal password extracted from prose narrative is used in fill"
    )

    # Positive check: using ${QA_AUX_PASS} for the same field is accepted without violations
    doc_env = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Narrative Prose Auth Case",
                objective="Llenar clave de relato en prosa con variable",
                steps=[
                    Step(
                        action="fill",
                        target="campo_auxiliar",
                        value="${QA_AUX_PASS}",
                        source_quote="Ingresamos con la clave secret_flotante_123 al formulario",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_env = check(doc_env, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_env)


@pytest.mark.smoke
def test_grounding_fill_credential_env_var_accepted() -> None:
    """Verify that fill step for credential target with ${VAR} is accepted."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Escribimos en el campo Clave de acceso", "images": []},
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }
    doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar clave con var",
                steps=[
                    Step(
                        action="fill",
                        target="Clave",
                        value="${QA_PASS_ADMIN}",
                        source_quote="Escribimos en el campo Clave de acceso",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations = check(doc, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "complex_target",
    [
        "input[name='pwd']",
        "secret_token",
        "input[id='user_pass']",
        "auth_token_field",
    ],
)
def test_grounding_fill_complex_credential_targets_rejected(complex_target: str) -> None:
    """Verify that fill step rejects literal values for complex/abbreviated credential selectors."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": f"Escribimos my_secret_val en el campo {complex_target}", "images": []},
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }
    # Negative test case (violation expected): literal credential value
    doc_literal = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar selector complejo",
                steps=[
                    Step(
                        action="fill",
                        target=complex_target,
                        value="my_secret_val",
                        source_quote=f"Escribimos my_secret_val en el campo {complex_target}",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations = check(doc_literal, dump)
    assert any(v.type == "literal_credential_in_fill" for v in violations)

    # Positive test case: env var is accepted for complex target
    doc_env = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar selector complejo con env var",
                steps=[
                    Step(
                        action="fill",
                        target=complex_target,
                        value="${QA_SECRET_TOKEN}",
                        source_quote=f"Escribimos my_secret_val en el campo {complex_target}",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_env = check(doc_env, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_env)


@pytest.mark.smoke
def test_grounding_fill_known_password_in_credentials_or_meta_rejected() -> None:
    """Verify that fill value matching a password from case.credentials or dump meta is rejected even for generic targets."""
    # 1. Known password in case.credentials
    dump1 = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Escribimos SecretPass123 en el campo CustomInput", "images": []},
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }
    doc_cred = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar pass conocido de credentials",
                credentials={"clave": "SecretPass123"},
                steps=[
                    Step(
                        action="fill",
                        target="CustomInput",
                        value="SecretPass123",
                        source_quote="Escribimos SecretPass123 en el campo CustomInput",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations1 = check(doc_cred, dump1)
    assert any(v.type == "literal_credential_in_fill" for v in violations1)

    # 2. Known password in dump meta
    dump2 = {
        "meta": {"módulo": "Seguridad", "password": "MetaSecretPassword999"},
        "paragraphs": [
            {"line": 1, "text": "Escribimos MetaSecretPassword999 en el campo Generico", "images": []},
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }
    doc_meta = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar pass conocido de meta",
                credentials={},
                steps=[
                    Step(
                        action="fill",
                        target="Generico",
                        value="MetaSecretPassword999",
                        source_quote="Escribimos MetaSecretPassword999 en el campo Generico",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations2 = check(doc_meta, dump2)
    assert any(v.type == "literal_credential_in_fill" for v in violations2)

    # Positive test: non-password normal value filled in generic target is NOT flagged as literal_credential_in_fill
    doc_ok = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar texto normal en campo generico",
                credentials={"clave": "SecretPass123"},
                steps=[
                    Step(
                        action="fill",
                        target="CustomInput",
                        value="NormalTextValue",
                        source_quote="Escribimos SecretPass123 en el campo CustomInput",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    dump_ok = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Escribimos SecretPass123 en el campo CustomInput NormalTextValue", "images": []},
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }
    violations_ok = check(doc_ok, dump_ok)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_ok)




@pytest.mark.smoke
def test_grounding_rule_d_credentials(synthetic_dump: dict) -> None:
    """Regla (d): Case.credentials must only contain ${VAR} environment references."""
    # Positive case: strictly ${VAR} format
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Autenticar",
                credentials={"user": "${QA_USER_ADMIN}", "pass": "${QA_PASS_ADMIN}"},
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote="Pulsamos el botón Guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, synthetic_dump)
    assert not any(v.type == "invalid_credential_format" for v in violations_pos)

    # Negative case: plaintext credentials in credentials dict
    doc_neg = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Autenticar",
                credentials={"user": "admin_plaintext", "pass": "secret_pass_123"},
                steps=[],
            )
        ],
    )
    violations_neg = check(doc_neg, synthetic_dump)
    cred_violations = [v for v in violations_neg if v.type == "invalid_credential_format"]
    assert len(cred_violations) >= 1
    assert all(isinstance(v, Violation) for v in cred_violations)


@pytest.mark.smoke
def test_grounding_rule_e_no_credentials_in_steps(synthetic_dump: dict) -> None:
    """Regla (e): no step should contain 'Usuario:' or 'Clave:' in target or value."""
    # Positive case: clean step target and value
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Step Clean",
                objective="Paso limpio",
                steps=[
                    Step(
                        action="fill",
                        target="Campo Nombre de Usuario",
                        value="${QA_USER_TESTER}",
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, synthetic_dump)
    assert not any(v.type == "credentials_in_step" for v in violations_pos)

    # Negative case: step target containing 'Usuario:'
    doc_neg_target = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Step Dirty",
                objective="Paso con Usuario:",
                steps=[
                    Step(
                        action="fill",
                        target="Usuario: admin",
                        value="${QA_USER_TESTER}",
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_neg_target = check(doc_neg_target, synthetic_dump)
    assert any(v.type == "credentials_in_step" for v in violations_neg_target)

    # Negative case: step value containing 'Clave:'
    doc_neg_value = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Step Dirty Value",
                objective="Paso con Clave:",
                steps=[
                    Step(
                        action="fill",
                        target="Campo Password",
                        value="Clave: ${QA_PASS_TESTER}",
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_neg_value = check(doc_neg_value, synthetic_dump)
    assert any(v.type == "credentials_in_step" for v in violations_neg_value)


@pytest.mark.smoke
def test_grounding_rule_f_sensitive_data(synthetic_dump: dict) -> None:
    """Regla (f): no output field can contain cédulas, RIF, personal emails, or JWT unless inside ${VAR}."""
    # Positive case: variable reference containing pattern-like string inside ${VAR}
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba limpia",
                objective="Validar variables de entorno",
                credentials={"user": "${QA_USER_V12345678}"},
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote="Pulsamos el botón Guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, synthetic_dump)
    assert not any(v.type == "sensitive_data" for v in violations_pos)

    # Negative cases with synthetic dummy data outside ${VAR}
    # 1. Cédula pattern in title
    doc_neg_cedula = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba para V-12345678",
                objective="Prueba cédula",
                steps=[],
            )
        ],
    )
    assert any(v.type == "sensitive_data" for v in check(doc_neg_cedula, synthetic_dump))

    # 2. RIF pattern in objective
    doc_neg_rif = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba Empresa",
                objective="Generar factura para J-12345678-0",
                steps=[],
            )
        ],
    )
    assert any(v.type == "sensitive_data" for v in check(doc_neg_rif, synthetic_dump))

    # 3. Email pattern in step target
    doc_neg_email = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba Correo",
                objective="Enviar confirmación",
                steps=[
                    Step(
                        action="fill",
                        target="Campo correo test.user@example.test",
                        value="${QA_EMAIL_VAR}",
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    assert any(v.type == "sensitive_data" for v in check(doc_neg_email, synthetic_dump))

    # 4. JWT pattern in value
    synthetic_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IlRlc3QifQ."
        "dummy_signature_value_1234567890_test"
    )
    doc_neg_jwt = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Prueba Token",
                objective="Pasar token JWT",
                steps=[
                    Step(
                        action="fill",
                        target="Header Auth",
                        value=synthetic_jwt,
                        source_quote="Iniciamos el proceso en el portal",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    assert any(v.type == "sensitive_data" for v in check(doc_neg_jwt, synthetic_dump))


@pytest.mark.smoke
def test_positive_full_document_states(synthetic_dump: dict) -> None:
    """Document satisfying all 6 rules determines correct status for READY, NEEDS_INFO, and UNSUPPORTED."""
    # 1. READY case
    case_ready = Case(
        n=1,
        title="Caso Facturación Exitosa",
        objective="Generar comprobante exitosamente",
        url="https://qa.example.test/portal",
        credentials={"user": "${QA_USER_FACTURACION}", "pass": "${QA_PASS_FACTURACION}"},
        steps=[
            Step(
                action="navigate",
                target="https://qa.example.test/login",
                source_quote="Iniciamos el proceso en el portal",
                source_ref="Línea 1",
            ),
            Step(
                action="fill",
                target="Campo Código",
                value="FACTURA-2026",
                source_quote="Escribimos FACTURA-2026 en el campo Código",
                source_ref="Línea 3",
            ),
            Step(
                action="click",
                target="Botón Guardar",
                source_quote="Pulsamos el botón Guardar registro",
                source_ref="Línea 2",
            ),
        ],
    )
    assert case_ready.status == "READY"

    # 2. NEEDS_INFO case
    case_needs_info = Case(
        n=2,
        title="Caso con faltante",
        objective="Objetivo faltante",
        url="https://qa.example.test/portal",
        steps=[
            Step(
                action="click",
                target="Botón Guardar",
                source_quote="Pulsamos el botón Guardar registro",
                source_ref="Línea 2",
            )
        ],
        gaps=[Gap(type="missing_credentials", severity="blocking", where="Caso 2", ask="Indicar credencial")],
    )
    assert case_needs_info.status == "NEEDS_INFO"

    # 3. UNSUPPORTED case
    case_unsupported = Case(
        n=3,
        title="Caso manual",
        objective="Objetivo manual",
        url="https://qa.example.test/portal",
        steps=[
            Step(
                action="manual",
                target="Subir archivo",
                source_quote="Iniciamos el proceso en el portal",
                source_ref="Línea 1",
            )
        ],
    )
    assert case_unsupported.status == "UNSUPPORTED"

    full_doc = NormalizedDoc(
        meta={"módulo": "Facturación"},
        cases=[case_ready, case_needs_info, case_unsupported],
    )
    violations = check(full_doc, synthetic_dump)
    assert violations == []


@pytest.mark.smoke
def test_cli_validate_redacts_sensitive_data(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI validate exits with 1 on violations and NEVER prints sensitive text to stdout/stderr."""
    # Write dump
    dump_data = {
        "meta": {"portal": "https://qa.example.test/app"},
        "paragraphs": [{"line": 1, "text": "Texto base en dump", "images": []}],
        "links": ["https://qa.example.test/app"],
    }
    dump_file = tmp_path / "dump.json"
    dump_file.write_text(json.dumps(dump_data), encoding="utf-8")

    # Sensitive dummy payload
    secret_cedula = "V-12345678"
    secret_pass = "plain_secret_password_xyz"

    invalid_doc = {
        "meta": {"módulo": "Seguridad"},
        "cases": [
            {
                "n": 1,
                "title": f"Caso filtración {secret_cedula}",
                "objective": "Objetivo de prueba",
                "url": "https://qa.example.test/app",
                "credentials": {"user": "${QA_USER}", "pass": secret_pass},
                "steps": [
                    {
                        "action": "click",
                        "target": "Usuario: admin",
                        "source_quote": "Texto base en dump",
                        "source_ref": "Línea 1",
                    }
                ],
                "gaps": [],
            }
        ],
    }
    doc_file = tmp_path / "normalized.json"
    doc_file.write_text(json.dumps(invalid_doc), encoding="utf-8")

    # Execute CLI validate
    exit_code = cli_main(["validate", str(doc_file), "--original", str(dump_file)])
    captured = capsys.readouterr()
    combined_output = captured.out + captured.err

    # Must fail with code 1
    assert exit_code == 1

    # Output MUST indicate violation types and locations
    assert "sensitive_data" in combined_output or "credentials_in_step" in combined_output
    assert "Caso 1" in combined_output

    # CRITICAL: Output MUST NOT contain the sensitive strings!
    assert secret_cedula not in combined_output
    assert secret_pass not in combined_output

    # Positive test: valid file exits with 0
    valid_doc = {
        "meta": {"módulo": "Seguridad"},
        "cases": [
            {
                "n": 1,
                "title": "Caso limpio",
                "objective": "Objetivo limpio",
                "url": "https://qa.example.test/app",
                "credentials": {"user": "${QA_USER}", "pass": "${QA_PASS}"},
                "steps": [
                    {
                        "action": "click",
                        "target": "Boton Enviar",
                        "source_quote": "Texto base en dump",
                        "source_ref": "Línea 1",
                    }
                ],
                "gaps": [],
            }
        ],
    }
    valid_file = tmp_path / "valid.json"
    valid_file.write_text(json.dumps(valid_doc), encoding="utf-8")

    exit_code_pos = cli_main(["validate", str(valid_file), "--original", str(dump_file)])
    assert exit_code_pos == 0


@pytest.mark.smoke
@pytest.mark.parametrize(
    "formatted_sensitive",
    [
        "V-12.345.678",
        "J-12.345.678-9",
        "E 12 345 678",
        "V 14.500.123",
    ],
)
def test_grounding_rejects_formatted_cedula_and_rif(synthetic_dump: dict, formatted_sensitive: str) -> None:
    """Regla (f): Cédulas and RIFs formatted with dots or spaces must be detected as sensitive data."""
    # Positive case: properly masked / parameterized reference inside ${VAR}
    clean_doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Caso sin datos sensibles directos",
                objective="Verificar que datos en ${VAR} pasan",
                credentials={"user": "${QA_USER_V12345678}"},
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote="Pulsamos el botón Guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations_clean = check(clean_doc, synthetic_dump)
    assert not any(v.type in ("sensitive_data", "sensitive_data_detected") for v in violations_clean)

    # Negative case: formatted sensitive ID in title outside ${VAR}
    dirty_doc = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=2,
                title=f"Prueba con documento {formatted_sensitive}",
                objective="Verificar detección de formato con puntos o espacios",
                steps=[
                    Step(
                        action="click",
                        target="Guardar registro",
                        source_quote="Pulsamos el botón Guardar registro",
                        source_ref="Línea 2",
                    )
                ],
            )
        ],
    )
    violations_dirty = check(dirty_doc, synthetic_dump)
    sensitive_violations = [v for v in violations_dirty if v.type in ("sensitive_data", "sensitive_data_detected")]
    assert len(sensitive_violations) >= 1, f"Expected sensitive data violation for {formatted_sensitive}"


@pytest.mark.smoke
def test_grounding_detects_non_ascii_narrative_password_in_generic_fill() -> None:
    """Verify that narrative passwords containing non-ASCII characters (e.g. ñ, tildes) are detected in generic fill steps."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {
                "line": 1,
                "text": "Ingresamos con la clave contraseñá_segura_99 al sistema",
                "images": [],
            },
        ],
        "cases": [{"n": 1, "title": "Acceso", "start_line": 1, "end_line": 1}],
        "links": [],
    }

    # Negative case: step uses generic target but passes literal non-ASCII secret
    doc_violating = NormalizedDoc(
        meta={"módulo": "Seguridad"},
        cases=[
            Case(
                n=1,
                title="Acceso al sistema",
                objective="Validar ingreso",
                steps=[
                    Step(
                        action="fill",
                        target="campo_codigo",
                        value="contraseñá_segura_99",
                        source_quote="Ingresamos con la clave contraseñá_segura_99 al sistema",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )

    violations = check(doc_violating, dump)
    assert any(
        v.type == "literal_credential_in_fill" for v in violations
    ), f"Expected literal_credential_in_fill violation, got: {violations}"

    # Positive case: properly masked / parameterized with ${QA_PASS_DEFAULT}
    doc_valid = NormalizedDoc(
        meta={"módulo": "Seguridad"},
        cases=[
            Case(
                n=1,
                title="Acceso al sistema",
                objective="Validar ingreso",
                steps=[
                    Step(
                        action="fill",
                        target="campo_codigo",
                        value="${QA_PASS_DEFAULT}",
                        source_quote="Ingresamos con la clave contraseñá_segura_99 al sistema",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )

    violations_valid = check(doc_valid, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_valid)


@pytest.mark.smoke
def test_grounding_detects_quoted_and_equal_sign_narrative_passwords() -> None:
    """Verify that quoted passwords and equal-sign passwords in narrative are extracted and detected in fill."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {
                "line": 1,
                "text": 'El operador ingresa con Clave: "secreto_comillas_123" para iniciar sesión.',
                "images": [],
            },
            {
                "line": 2,
                "text": "Luego en el paso de autorización Contraseña = mi_clave.2026 para confirmar.",
                "images": [],
            },
        ],
        "cases": [{"n": 1, "title": "Acceso seguro", "start_line": 1, "end_line": 2}],
        "links": [],
    }

    # Negative case: fill steps with generic targets use raw secrets in plain text
    doc_violating = NormalizedDoc(
        meta={"módulo": "Seguridad"},
        cases=[
            Case(
                n=1,
                title="Acceso seguro",
                objective="Validar credenciales",
                steps=[
                    Step(
                        action="fill",
                        target="input_generico_1",
                        value="secreto_comillas_123",
                        source_quote='El operador ingresa con Clave: "secreto_comillas_123"',
                        source_ref="Línea 1",
                    ),
                    Step(
                        action="fill",
                        target="input_generico_2",
                        value="mi_clave.2026",
                        source_quote="Contraseña = mi_clave.2026 para confirmar",
                        source_ref="Línea 2",
                    ),
                ],
            )
        ],
    )

    violations = check(doc_violating, dump)
    fill_violations = [v for v in violations if v.type == "literal_credential_in_fill"]
    assert len(fill_violations) == 2, f"Expected 2 literal_credential_in_fill violations, got: {violations}"

    # Positive case: properly parameterized with environment variables
    doc_valid = NormalizedDoc(
        meta={"módulo": "Seguridad"},
        cases=[
            Case(
                n=1,
                title="Acceso seguro",
                objective="Validar credenciales",
                steps=[
                    Step(
                        action="fill",
                        target="input_generico_1",
                        value="${QA_PASS_QUOTED}",
                        source_quote='El operador ingresa con Clave: "secreto_comillas_123"',
                        source_ref="Línea 1",
                    ),
                    Step(
                        action="fill",
                        target="input_generico_2",
                        value="${QA_PASS_EQUAL}",
                        source_quote="Contraseña = mi_clave.2026 para confirmar",
                        source_ref="Línea 2",
                    ),
                ],
            )
        ],
    )

    violations_valid = check(doc_valid, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_valid)


@pytest.mark.smoke
def test_grounding_rejects_quote_spanning_across_different_paragraphs() -> None:
    """Verify that a source_quote spanning across paragraph boundaries is rejected as ungrounded."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {"line": 1, "text": "Primer párrafo fin.", "images": []},
            {"line": 2, "text": "Segundo párrafo inicio.", "images": []},
        ],
        "cases": [{"n": 1, "title": "Párrafos", "start_line": 1, "end_line": 2}],
        "links": [],
    }

    # 1. Negative case: quote stitches end of first paragraph and start of second
    doc_spanning = NormalizedDoc(
        meta={"módulo": "Seguridad"},
        cases=[
            Case(
                n=1,
                title="Párrafos",
                objective="Validar quote que cruza párrafos",
                steps=[
                    Step(
                        action="click",
                        target="Boton",
                        source_quote="fin. Segundo párrafo",
                        source_ref="Líneas 1-2",
                    )
                ],
            )
        ],
    )

    violations_neg = check(doc_spanning, dump)
    assert any(
        v.type == "ungrounded_quote" for v in violations_neg
    ), f"Expected ungrounded_quote violation, got: {violations_neg}"

    # 2. Positive case: quote completely contained within a single paragraph
    doc_contained = NormalizedDoc(
        meta={"módulo": "Seguridad"},
        cases=[
            Case(
                n=1,
                title="Párrafos",
                objective="Validar quote contenido en un párrafo",
                steps=[
                    Step(
                        action="click",
                        target="Boton",
                        source_quote="Primer párrafo fin.",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )

    violations_pos = check(doc_contained, dump)
    assert not any(v.type == "ungrounded_quote" for v in violations_pos)


@pytest.mark.smoke
def test_grounding_accepts_clean_url_when_dump_url_has_trailing_punctuation() -> None:
    """Verify that URLs ending with punctuation in free text match clean URLs in normalized cases."""
    dump = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Ingresamos a https://qa.example.test/portal.", "images": []},
        ],
        "cases": [{"n": 1, "title": "Portal", "start_line": 1, "end_line": 1}],
        "links": [],
    }

    # Positive case: normalized test uses clean canonical URL without trailing dot
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Acceso al portal",
                objective="Validar URL limpia contra texto de dump con puntuación",
                steps=[
                    Step(
                        action="navigate",
                        target="https://qa.example.test/portal",
                        source_quote="Ingresamos a https://qa.example.test/portal.",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, dump)
    assert not any(v.type == "ungrounded_url" for v in violations_pos)

    # Negative case: normalized test uses an ungrounded URL not present in dump
    doc_neg = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Acceso no documentado",
                objective="Validar rechazo de URL no documentada",
                steps=[
                    Step(
                        action="navigate",
                        target="https://qa.example.test/unauthorized-portal",
                        source_quote="Ingresamos a https://qa.example.test/portal.",
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_neg = check(doc_neg, dump)
    assert any(v.type == "ungrounded_url" for v in violations_neg)


@pytest.mark.smoke
def test_grounding_detects_quoted_password_in_generic_fill_step() -> None:
    """Verify that quoted known password in fill step over generic target triggers literal_credential_in_fill."""
    dump = {
        "meta": {"módulo": "Seguridad"},
        "paragraphs": [
            {
                "line": 1,
                "text": 'Iniciamos con Clave: secreto_real_999 y "secreto_real_999" para ingresar al portal',
                "images": [],
            },
        ],
        "cases": [{"n": 1, "title": "Auth", "start_line": 1, "end_line": 1}],
        "links": [],
    }

    # Negative case: quoted known password on generic target is detected as credential leak
    doc_neg = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar clave entrecomillada en campo genérico",
                steps=[
                    Step(
                        action="fill",
                        target="campo_codigo",
                        value='"secreto_real_999"',
                        source_quote='Iniciamos con Clave: secreto_real_999 y "secreto_real_999" para ingresar al portal',
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_neg = check(doc_neg, dump)
    assert any(v.type == "literal_credential_in_fill" for v in violations_neg)

    # Positive case: parameterized password with ${QA_PASS_DEFAULT} passes without violation
    doc_pos = NormalizedDoc(
        meta={},
        cases=[
            Case(
                n=1,
                title="Auth Case",
                objective="Llenar clave parametrizada",
                steps=[
                    Step(
                        action="fill",
                        target="campo_codigo",
                        value="${QA_PASS_DEFAULT}",
                        source_quote='Iniciamos con Clave: secreto_real_999 y "secreto_real_999" para ingresar al portal',
                        source_ref="Línea 1",
                    )
                ],
            )
        ],
    )
    violations_pos = check(doc_pos, dump)
    assert not any(v.type == "literal_credential_in_fill" for v in violations_pos)

