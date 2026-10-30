"""Unit tests for NormalizedDoc, Case, and Step Pydantic schemas (T3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from normalizer.gaps import Gap
from normalizer.schema import Case, NormalizedDoc, Step


@pytest.mark.smoke
def test_step_schema_validation() -> None:
    """Step validates allowed actions, confidence, and default values."""
    # Positive case: valid step with allowed action and defaults
    step = Step(
        action="click",
        target="Boton Guardar",
        source_quote="Hacemos clic en Guardar",
        source_ref="Párrafo 3",
    )
    assert step.action == "click"
    assert step.target == "Boton Guardar"
    assert step.value is None
    assert step.confidence == "high"

    # Negative case: invalid action not in vocabulary raises ValidationError
    with pytest.raises(ValidationError):
        Step(
            action="hover",  # type: ignore[arg-type]
            target="Menu",
            source_quote="Pasamos el cursor",
            source_ref="Párrafo 1",
        )


@pytest.mark.smoke
def test_case_status_property_needs_info() -> None:
    """Case with blocking gap has status NEEDS_INFO regardless of steps."""
    step = Step(
        action="click",
        target="Boton Login",
        source_quote="Clic en Login",
        source_ref="Párrafo 2",
    )

    # Positive: blocking gap sets NEEDS_INFO
    case_blocking = Case(
        n=1,
        title="Login Case",
        objective="Probar login",
        steps=[step],
        gaps=[Gap(type="missing_url", severity="blocking", where="Caso 1", ask="Agregar Link")],
    )
    assert case_blocking.status == "NEEDS_INFO"

    # Negative: warning or info gap does not set NEEDS_INFO (resolves to READY if steps exist)
    case_warning = Case(
        n=1,
        title="Login Case",
        objective="Probar login",
        steps=[step],
        gaps=[Gap(type="missing_expected", severity="warning", where="Caso 1", ask="Definir esperado")],
    )
    assert case_warning.status == "READY"


@pytest.mark.smoke
def test_case_status_property_unsupported() -> None:
    """Case with no executable steps (or empty) has status UNSUPPORTED."""
    # Positive: only manual steps results in UNSUPPORTED
    case_manual = Case(
        n=1,
        title="Manual Flow",
        objective="Probar OTP",
        steps=[
            Step(
                action="manual",
                target="Verificar OTP en móvil",
                source_quote="Se recibe OTP en el móvil",
                source_ref="Párrafo 1",
            )
        ],
    )
    assert case_manual.status == "UNSUPPORTED"

    # Positive: empty steps results in UNSUPPORTED
    case_empty = Case(
        n=2,
        title="Empty Case",
        objective="Caso sin pasos",
        steps=[],
    )
    assert case_empty.status == "UNSUPPORTED"

    # Negative: case with at least one executable step results in READY
    case_executable = Case(
        n=3,
        title="Executable Case",
        objective="Caso ejecutable",
        steps=[
            Step(
                action="click",
                target="Boton Continuar",
                source_quote="Pulsamos continuar",
                source_ref="Párrafo 1",
            )
        ],
    )
    assert case_executable.status == "READY"


@pytest.mark.smoke
def test_normalized_doc_validation() -> None:
    """NormalizedDoc validates meta and case list."""
    # Positive: valid NormalizedDoc with meta and cases
    valid_data = {
        "meta": {"módulo": "Ventas", "analista": "QA Team"},
        "cases": [
            {
                "n": 1,
                "title": "Caso de prueba",
                "objective": "Objetivo de prueba",
                "url": "https://example.com/test",
                "credentials": {"user": "${QA_USER}", "pass": "${QA_PASS}"},
                "steps": [
                    {
                        "action": "navigate",
                        "target": "https://example.com/test",
                        "source_quote": "Navegamos a la URL",
                        "source_ref": "Párrafo 1",
                    }
                ],
                "gaps": [],
            }
        ],
    }
    doc = NormalizedDoc.model_validate(valid_data)
    assert doc.meta["módulo"] == "Ventas"
    assert len(doc.cases) == 1
    assert doc.cases[0].status == "READY"

    # Negative: missing required fields in case raises ValidationError
    invalid_data = {
        "meta": {},
        "cases": [{"title": "Falta n y objective"}],
    }
    with pytest.raises(ValidationError):
        NormalizedDoc.model_validate(invalid_data)
