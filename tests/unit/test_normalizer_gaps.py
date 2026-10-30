"""Tests for gap detection and state determination (T2: normalizer.gaps)."""

from __future__ import annotations

import pytest

from normalizer.gaps import Gap, detect_gaps, determine_state


@pytest.mark.smoke
def test_detect_missing_url_blocking_gap() -> None:
    """Missing URL in case and header returns blocking missing_url gap and NEEDS_INFO."""
    # Positive case: No URL in links or paragraphs
    dump_no_url = {
        "meta": {"módulo": "Ventas"},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Sin enlace", "images": []},
            {"line": 2, "text": "Paso 1: Abrir el sistema", "images": []},
        ],
        "cases": [{"n": 1, "title": "Sin enlace", "start_line": 1, "end_line": 2}],
        "links": [],
    }

    gaps = detect_gaps(dump_no_url)
    url_gaps = [g for g in gaps if g.type == "missing_url"]
    assert len(url_gaps) == 1
    assert url_gaps[0].severity == "blocking"
    assert "Link" in url_gaps[0].ask
    assert determine_state(gaps) == "NEEDS_INFO"

    # Negative case: Link present in global links (header) -> no missing_url gap
    dump_with_url = {
        "meta": {"módulo": "Ventas"},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Con enlace", "images": []},
            {"line": 2, "text": "Paso 1: Abrir el sistema", "images": []},
        ],
        "cases": [{"n": 1, "title": "Con enlace", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com/login"],
    }

    gaps_with_url = detect_gaps(dump_with_url)
    assert not any(g.type == "missing_url" for g in gaps_with_url)


def test_detect_missing_credentials_gap() -> None:
    """Login phrase without user returns missing_credentials; with user produces no gap."""
    # Positive: Login phrase present, but no Usuario line
    dump_missing_user = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Login", "images": []},
            {"line": 2, "text": "Iniciamos sesión en el sistema", "images": []},
            {"line": 3, "text": "Pulsamos aceptar", "images": []},
        ],
        "cases": [{"n": 1, "title": "Login", "start_line": 1, "end_line": 3}],
        "links": ["https://example.com"],
    }

    gaps = detect_gaps(dump_missing_user)
    cred_gaps = [g for g in gaps if g.type == "missing_credentials"]
    assert len(cred_gaps) == 1
    assert cred_gaps[0].severity == "blocking"
    assert determine_state(gaps) == "NEEDS_INFO"

    # Negative: Login phrase with explicit Usuario line
    dump_with_user = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Login", "images": []},
            {"line": 2, "text": "Iniciamos sesión en el sistema", "images": []},
            {"line": 3, "text": "Usuario: test_user", "images": []},
        ],
        "cases": [{"n": 1, "title": "Login", "start_line": 1, "end_line": 3}],
        "links": ["https://example.com"],
    }

    gaps_with_user = detect_gaps(dump_with_user)
    assert not any(g.type == "missing_credentials" for g in gaps_with_user)


@pytest.mark.smoke
def test_detect_credentials_in_plaintext_never_echoes_secret() -> None:
    """Plaintext password triggers warning and ask message NEVER echoes the secret."""
    secret_pass = "SuperSecretPassword123!"

    # Positive: Plaintext password in text
    dump_plaintext = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Credenciales", "images": []},
            {"line": 2, "text": f"Clave: {secret_pass}", "images": []},
        ],
        "cases": [{"n": 1, "title": "Credenciales", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com"],
    }

    gaps = detect_gaps(dump_plaintext)
    plaintext_gaps = [g for g in gaps if g.type == "credentials_in_plaintext"]
    assert len(plaintext_gaps) == 1
    gap = plaintext_gaps[0]
    assert gap.severity == "warning"
    # CRITICAL INVARIANT: ask must NEVER contain the secret
    assert secret_pass not in gap.ask

    # Negative: Parameterized password via environment variable ${QA_PASS_...}
    dump_parameterized = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Credenciales", "images": []},
            {"line": 2, "text": "Clave: ${QA_PASS_ADMIN}", "images": []},
        ],
        "cases": [{"n": 1, "title": "Credenciales", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com"],
    }

    gaps_param = detect_gaps(dump_parameterized)
    assert not any(g.type == "credentials_in_plaintext" for g in gaps_param)


def test_detect_missing_expected_verification_gap() -> None:
    """Bare verification phrase ('se muestra correctamente') triggers missing_expected warning."""
    # Positive: Bare phrase without explicit expectation
    dump_bare = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Verificación", "images": []},
            {"line": 2, "text": "Se muestra correctamente.", "images": []},
        ],
        "cases": [{"n": 1, "title": "Verificación", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com"],
    }

    gaps = detect_gaps(dump_bare)
    exp_gaps = [g for g in gaps if g.type == "missing_expected"]
    assert len(exp_gaps) == 1
    assert exp_gaps[0].severity == "warning"

    # Negative: Specific expectation mentioned
    dump_specific = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Verificación", "images": []},
            {"line": 2, "text": "Se muestra el mensaje Pago procesado con éxito", "images": []},
        ],
        "cases": [{"n": 1, "title": "Verificación", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com"],
    }

    gaps_specific = detect_gaps(dump_specific)
    assert not any(g.type == "missing_expected" for g in gaps_specific)


def test_detect_data_in_screenshot_gap() -> None:
    """Screenshot data phrase coupled with an image triggers data_in_screenshot warning."""
    # Positive: Phrase followed by an image
    dump_with_screenshot = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Captura", "images": []},
            {"line": 2, "text": "con la siguiente información:", "images": ["img/image1.png"]},
        ],
        "cases": [{"n": 1, "title": "Captura", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com"],
    }

    gaps = detect_gaps(dump_with_screenshot)
    screen_gaps = [g for g in gaps if g.type == "data_in_screenshot"]
    assert len(screen_gaps) == 1
    assert screen_gaps[0].severity == "warning"

    # Negative: Phrase without any image
    dump_no_screenshot = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Captura", "images": []},
            {"line": 2, "text": "con la siguiente información:", "images": []},
            {"line": 3, "text": "Código: 1234", "images": []},
        ],
        "cases": [{"n": 1, "title": "Captura", "start_line": 1, "end_line": 3}],
        "links": ["https://example.com"],
    }

    gaps_no_screen = detect_gaps(dump_no_screenshot)
    assert not any(g.type == "data_in_screenshot" for g in gaps_no_screen)


def test_detect_unsupported_flow_gap() -> None:
    """Unsupported flow phrases (OTP, pago móvil, SISIP) trigger unsupported_flow info."""
    # Positive: Step with OTP and pago móvil
    dump_unsupported = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Pago", "images": []},
            {"line": 2, "text": "Ingresamos el código OTP recibido", "images": []},
            {"line": 3, "text": "Realizar pago móvil", "images": []},
        ],
        "cases": [{"n": 1, "title": "Pago", "start_line": 1, "end_line": 3}],
        "links": ["https://example.com"],
    }

    gaps = detect_gaps(dump_unsupported)
    unsupported_gaps = [g for g in gaps if g.type == "unsupported_flow"]
    assert len(unsupported_gaps) == 2
    for g in unsupported_gaps:
        assert g.severity == "info"

    # Negative: Standard automated actions
    dump_standard = {
        "meta": {},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Estándar", "images": []},
            {"line": 2, "text": "Paso 1: clic en Emitir", "images": []},
        ],
        "cases": [{"n": 1, "title": "Estándar", "start_line": 1, "end_line": 2}],
        "links": ["https://example.com"],
    }

    gaps_standard = detect_gaps(dump_standard)
    assert not any(g.type == "unsupported_flow" for g in gaps_standard)


def test_determine_state_ready_needs_info_unsupported() -> None:
    """State is NEEDS_INFO on blocking gaps, UNSUPPORTED when no steps remain, READY otherwise."""
    blocking_gap = Gap(type="missing_url", severity="blocking", where="Caso 1", ask="Add link")
    warning_gap = Gap(type="missing_expected", severity="warning", where="Caso 1", ask="Specify text")
    unsupported_gap_1 = Gap(type="unsupported_flow", severity="info", where="Caso 1", ask="Manual step")
    unsupported_gap_2 = Gap(type="unsupported_flow", severity="info", where="Caso 1", ask="Manual step")

    # NEEDS_INFO when blocking gap present
    assert determine_state([blocking_gap, warning_gap], total_steps_or_cases=2) == "NEEDS_INFO"

    # READY when only warnings and active steps exist
    assert determine_state([warning_gap], total_steps_or_cases=2) == "READY"

    # UNSUPPORTED when all steps are unsupported
    assert determine_state([unsupported_gap_1, unsupported_gap_2], total_steps_or_cases=2) == "UNSUPPORTED"
