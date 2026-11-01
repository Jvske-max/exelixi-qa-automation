"""Unit tests for AllureReporter core lifecycle and Allure v2 emission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from parsers.models import ExecutionReport, StepDefinition, StepResult, TestCase
from reporting import AllureReporter


@pytest.fixture
def dummy_png(tmp_path: Path) -> Path:
    """Create a valid PNG image file for attachment testing."""
    png_path = tmp_path / "fixtures" / "screenshot.png"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (16, 16), color=(40, 120, 200))
    img.save(png_path, format="PNG")
    return png_path


@pytest.fixture
def sample_test_case() -> TestCase:
    """Provide a standard TestCase model with credential metadata."""
    return TestCase(
        case_id="R-TEST-001",
        module="Módulo de Seguridad",
        title="Validación de Credenciales y Sesión",
        objective="Verificar que el inicio de sesión funcione con enmascaramiento.",
        credentials={"usuario": "qa_operador", "clave": "ClaveSecreta123!"},
        steps=[
            StepDefinition(
                step_num=1,
                raw_text="Navegar al login",
                action="navigate",
                target="https://qa.local.test/login",
            ),
            StepDefinition(
                step_num=2,
                raw_text="Ingresar credenciales",
                action="fill",
                target="input[name='password']",
                value="ClaveSecreta123!",
            ),
            StepDefinition(
                step_num=3,
                raw_text="Hacer clic en submit",
                action="click",
                target="button#login-btn",
            ),
        ],
        environment="QA",
    )


@pytest.fixture
def sample_execution_report() -> ExecutionReport:
    """Provide a standard ExecutionReport model."""
    return ExecutionReport(
        case_id="R-TEST-001",
        module="Módulo de Seguridad",
        title="Validación de Credenciales y Sesión",
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:05",
        duration_seconds=5.0,
        environment="QA",
        summary_notes="Escenario ejecutado exitosamente.",
        steps=[
            StepResult(
                step_num=1,
                action="navigate",
                target="https://qa.local.test/login",
                status="PASSED",
                duration_ms=1200.0,
            ),
            StepResult(
                step_num=2,
                action="fill",
                target="input[name='password']",
                status="PASSED",
                duration_ms=450.0,
            ),
            StepResult(
                step_num=3,
                action="click",
                target="button#login-btn",
                status="PASSED",
                duration_ms=800.0,
            ),
        ],
    )


@pytest.mark.smoke
def test_allure_reporter_init_directory_creation_positive(tmp_path: Path) -> None:
    """Verify that AllureReporter automatically creates non-existent results_dir."""
    target_dir = tmp_path / "deeply" / "nested" / "allure_results"
    assert not target_dir.exists()

    reporter = AllureReporter(results_dir=str(target_dir))

    assert target_dir.exists()
    assert target_dir.is_dir()
    assert reporter.results_dir == target_dir.resolve()


def test_allure_reporter_init_invalid_path_negative(tmp_path: Path) -> None:
    """Verify that AllureReporter raises an error when results_dir cannot be a directory."""
    existing_file = tmp_path / "blocking_file.txt"
    existing_file.write_text("blocked")

    with pytest.raises((ValueError, NotADirectoryError, FileExistsError)):
        AllureReporter(results_dir=existing_file)


@pytest.mark.smoke
def test_allure_reporter_lifecycle_positive(
    tmp_path: Path, sample_test_case: TestCase, sample_execution_report: ExecutionReport
) -> None:
    """Verify standard lifecycle events create valid Allure v2 result JSON."""
    results_dir = tmp_path / "allure_out"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    for step in sample_test_case.steps:
        reporter.start_step(step=step, step_num=step.step_num)
        result = next(
            r for r in sample_execution_report.steps if r.step_num == step.step_num
        )
        reporter.stop_step(step=step, result=result)

    reporter.stop_test_case(sample_execution_report)

    result_files = list(results_dir.glob("*-result.json"))
    assert len(result_files) == 1, "Expected exactly one *-result.json file"

    result_json = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result_json["name"] == sample_test_case.title
    assert result_json["status"] == "passed"
    assert "start" in result_json and isinstance(result_json["start"], int)
    assert "stop" in result_json and isinstance(result_json["stop"], int)
    assert result_json["stop"] >= result_json["start"]
    assert "steps" in result_json
    assert len(result_json["steps"]) == 3
    assert "attachments" in result_json


def test_allure_reporter_stop_without_start_negative(
    tmp_path: Path, sample_execution_report: ExecutionReport
) -> None:
    """Verify that stopping a test case without starting one raises an error or handles cleanly."""
    reporter = AllureReporter(results_dir=tmp_path / "empty_run")

    with pytest.raises(RuntimeError):
        reporter.stop_test_case(sample_execution_report)


@pytest.mark.parametrize(
    ("input_status", "expected_allure_status"),
    [
        ("PASS", "passed"),
        ("PASSED", "passed"),
        ("passed", "passed"),
        ("FAIL", "failed"),
        ("FAILED", "failed"),
        ("failed", "failed"),
        ("ERROR", "broken"),
        ("BLOCKED", "broken"),
        ("BROKEN", "broken"),
        ("SKIPPED", "skipped"),
        ("MANUAL", "skipped"),
    ],
)
def test_allure_reporter_status_mapping_positive(
    tmp_path: Path,
    sample_test_case: TestCase,
    input_status: str,
    expected_allure_status: str,
) -> None:
    """Verify correct mapping of step and test case statuses to Allure 2 Status."""
    reporter = AllureReporter(results_dir=tmp_path / f"status_{input_status}")
    reporter.start_test_case(sample_test_case)

    step = sample_test_case.steps[0]
    reporter.start_step(step=step, step_num=1)
    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=step.target,
        status=input_status,
        duration_ms=100.0,
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status=input_status,
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next((tmp_path / f"status_{input_status}").glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))

    assert data["steps"][0]["status"] == expected_allure_status
    assert data["status"] == expected_allure_status


def test_allure_reporter_unrecognized_status_negative(
    tmp_path: Path, sample_test_case: TestCase
) -> None:
    """Verify that an unknown or invalid status string maps safely to broken or unknown."""
    reporter = AllureReporter(results_dir=tmp_path / "unknown_status")
    reporter.start_test_case(sample_test_case)

    step = sample_test_case.steps[0]
    reporter.start_step(step=step, step_num=1)
    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=step.target,
        status="INVALID_NON_EXISTENT_STATUS",
        duration_ms=50.0,
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="INVALID_NON_EXISTENT_STATUS",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next((tmp_path / "unknown_status").glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))

    assert data["steps"][0]["status"] in ("broken", "unknown")
    assert data["status"] in ("broken", "unknown")


@pytest.mark.smoke
def test_allure_reporter_screenshot_attachment_positive(
    tmp_path: Path,
    sample_test_case: TestCase,
    dummy_png: Path,
) -> None:
    """Verify that screenshots in StepResult are attached and copied to results_dir."""
    results_dir = tmp_path / "attachment_test"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    step = sample_test_case.steps[0]
    reporter.start_step(step=step, step_num=1)

    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=step.target,
        status="PASSED",
        duration_ms=250.0,
        screenshot_path=str(dummy_png),
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))

    step_attachments = data["steps"][0].get("attachments", [])
    assert len(step_attachments) == 1, "Expected attachment on step"
    attachment = step_attachments[0]
    assert attachment["type"] == "image/png"
    assert attachment["source"].endswith(".png")

    attached_file_path = results_dir / attachment["source"]
    assert attached_file_path.exists(), "Attachment file must be copied to results_dir"
    assert attached_file_path.read_bytes() == dummy_png.read_bytes()


def test_allure_reporter_screenshot_missing_file_negative(
    tmp_path: Path,
    sample_test_case: TestCase,
) -> None:
    """Verify that a missing screenshot file does not crash report generation."""
    results_dir = tmp_path / "missing_attachment_test"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    step = sample_test_case.steps[0]
    reporter.start_step(step=step, step_num=1)

    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=step.target,
        status="PASSED",
        duration_ms=250.0,
        screenshot_path=str(tmp_path / "does_not_exist.png"),
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert len(data["steps"][0].get("attachments", [])) == 0


@pytest.mark.smoke
def test_allure_reporter_redacts_sensitive_error_details_positive(
    tmp_path: Path,
    sample_test_case: TestCase,
) -> None:
    """Verify that sensitive credentials, tokens, and PII are redacted from statusDetails."""
    results_dir = tmp_path / "redaction_test"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    step = sample_test_case.steps[1]
    reporter.start_step(step=step, step_num=2)

    leaked_secret = "ClaveSecreta123!"
    leaked_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature1234"
    leaked_cedula = "V-18.765.432"
    leaked_email = "sensitive_admin@internal.corp"

    raw_error = (
        f"AssertionError: failed with password='{leaked_secret}' and token={leaked_jwt} "
        f"for user={leaked_cedula} email={leaked_email}"
    )

    step_result = StepResult(
        step_num=2,
        action=step.action,
        target=step.target,
        status="FAILED",
        duration_ms=300.0,
        error_message=raw_error,
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="FAILED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))

    step_data = data["steps"][0]
    assert step_data["status"] == "failed"
    status_details = step_data.get("statusDetails", {})
    message = status_details.get("message", "")

    # Ensure sensitive items are NOT present
    assert leaked_secret not in message
    assert leaked_jwt not in message
    assert leaked_cedula not in message
    assert leaked_email not in message

    # Ensure redaction marker is present
    assert "[REDACTED]" in message


def test_allure_reporter_status_details_none_when_no_error_negative(
    tmp_path: Path,
    sample_test_case: TestCase,
) -> None:
    """Verify that successful steps have no statusDetails or None without crashing."""
    results_dir = tmp_path / "clean_status_details"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    step = sample_test_case.steps[0]
    reporter.start_step(step=step, step_num=1)

    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=step.target,
        status="PASSED",
        duration_ms=50.0,
        error_message=None,
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["steps"][0].get("statusDetails") is None


def test_allure_reporter_container_emission_positive(
    tmp_path: Path,
    sample_test_case: TestCase,
    sample_execution_report: ExecutionReport,
) -> None:
    """Verify that container JSON (*-container.json) is emitted linking children test cases."""
    results_dir = tmp_path / "container_test"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    for step in sample_test_case.steps:
        reporter.start_step(step=step, step_num=step.step_num)
        result = next(
            r for r in sample_execution_report.steps if r.step_num == step.step_num
        )
        reporter.stop_step(step=step, result=result)
    reporter.stop_test_case(sample_execution_report)

    container_files = list(results_dir.glob("*-container.json"))
    assert len(container_files) == 1

    container_data = json.loads(container_files[0].read_text(encoding="utf-8"))
    assert "uuid" in container_data
    assert "children" in container_data
    assert len(container_data["children"]) == 1

    result_file = next(results_dir.glob("*-result.json"))
    result_data = json.loads(result_file.read_text(encoding="utf-8"))
    assert result_data["uuid"] in container_data["children"]


@pytest.mark.smoke
def test_allure_reporter_step_name_masks_target_credentials_positive(
    tmp_path: Path,
    sample_test_case: TestCase,
) -> None:
    """Verify that step_name in start_step and stop_step redacts URL credentials and tokens in target."""
    results_dir = tmp_path / "step_name_masking"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    sensitive_target = "https://admin:LeakPass12345@secure.gateway.org/api/v1?token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig1234567890"
    step = StepDefinition(
        step_num=1,
        raw_text="Call sensitive endpoint",
        action="navigate",
        target=sensitive_target,
    )
    reporter.start_step(step=step, step_num=1)
    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=sensitive_target,
        status="PASSED",
        duration_ms=150.0,
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))
    persisted_step_name = data["steps"][0]["name"]

    assert "LeakPass12345" not in persisted_step_name
    assert "sig1234567890" not in persisted_step_name
    assert "[REDACTED]" in persisted_step_name


def test_allure_reporter_stop_step_fallback_masks_target_negative(
    tmp_path: Path,
    sample_test_case: TestCase,
) -> None:
    """Verify that stop_step without prior start_step also masks credentials in step name."""
    results_dir = tmp_path / "stop_step_fallback_masking"
    reporter = AllureReporter(results_dir=results_dir)

    reporter.start_test_case(sample_test_case)
    sensitive_target = "https://ops:FallbackPass999@internal.db/query"
    step_result = StepResult(
        step_num=1,
        action="get",
        target=sensitive_target,
        status="PASSED",
        duration_ms=100.0,
    )
    # Stop step directly without prior start_step call
    reporter.stop_step(step=step_result)

    report = ExecutionReport(
        case_id=sample_test_case.case_id,
        module=sample_test_case.module,
        title=sample_test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    data = json.loads(result_file.read_text(encoding="utf-8"))
    persisted_step_name = data["steps"][0]["name"]

    assert "FallbackPass999" not in persisted_step_name
    assert "[REDACTED]" in persisted_step_name


@pytest.mark.smoke
def test_allure_reporter_masks_title_and_objective_positive(tmp_path: Path) -> None:
    """Verify that test_case.title and test_case.objective are masked in TestResult and Container."""
    results_dir = tmp_path / "title_objective_masking"
    reporter = AllureReporter(results_dir=results_dir)

    test_case = TestCase(
        case_id="SEC-TIT-001",
        module="AuthModule",
        title='Login con password="SecretPass123!" y correo admin@internal.net',
        objective="Verificar token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiYWRtaW4ifQ.secretSign12345678",
        credentials={"usuario": "admin", "clave": "SecretPass123!"},
        steps=[
            StepDefinition(
                step_num=1,
                raw_text="Navigate",
                action="navigate",
                target="https://qa.local.test",
            ),
        ],
        environment="QA",
    )

    reporter.start_test_case(test_case)
    step = test_case.steps[0]
    reporter.start_step(step=step, step_num=1)
    step_result = StepResult(
        step_num=1,
        action=step.action,
        target=step.target,
        status="PASSED",
        duration_ms=50.0,
    )
    reporter.stop_step(step=step, result=step_result)

    report = ExecutionReport(
        case_id=test_case.case_id,
        module=test_case.module,
        title=test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[step_result],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    container_file = next(results_dir.glob("*-container.json"))

    result_data = json.loads(result_file.read_text(encoding="utf-8"))
    container_data = json.loads(container_file.read_text(encoding="utf-8"))

    # Assert title in result and container is masked
    assert "SecretPass123!" not in result_data["name"]
    assert "admin@internal.net" not in result_data["name"]
    assert "SecretPass123!" not in container_data["name"]
    assert "admin@internal.net" not in container_data["name"]

    # Assert objective / description in result is masked
    assert "secretSign12345678" not in result_data["description"]
    assert "[REDACTED]" in result_data["description"]


def test_allure_reporter_title_and_objective_empty_clean_negative(
    tmp_path: Path,
) -> None:
    """Verify that empty objective or clean title does not cause errors or unintended redactions."""
    results_dir = tmp_path / "title_objective_clean"
    reporter = AllureReporter(results_dir=results_dir)

    test_case = TestCase(
        case_id="CLEAN-001",
        module="CleanModule",
        title="Escenario de prueba completamente limpio",
        objective="",
        credentials={},
        steps=[],
    )

    reporter.start_test_case(test_case)
    report = ExecutionReport(
        case_id=test_case.case_id,
        module=test_case.module,
        title=test_case.title,
        status="PASSED",
        started_at="2026-10-30 08:00:00",
        finished_at="2026-10-30 08:00:01",
        duration_seconds=1.0,
        steps=[],
    )
    reporter.stop_test_case(report)

    result_file = next(results_dir.glob("*-result.json"))
    result_data = json.loads(result_file.read_text(encoding="utf-8"))

    assert result_data["name"] == "Escenario de prueba completamente limpio"
    assert result_data.get("description", "") == ""


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("input_text", "expected_contains"),
    [
        ('password="secret pass with spaces"', "password: [REDACTED]"),
        ("clave = 'otra clave secreta con espacios'", "clave: [REDACTED]"),
        ('contraseña: "clave segura 2026 #!"', "contraseña: [REDACTED]"),
        ("token='jwt.token.with spaces inside'", "token: [REDACTED]"),
        ('secret: "multi word confidential key"', "secret: [REDACTED]"),
    ],
)
def test_allure_reporter_password_mask_pattern_quoted_with_spaces_positive(
    tmp_path: Path, input_text: str, expected_contains: str
) -> None:
    """Verify PASSWORD_MASK_PATTERN properly masks quoted passwords containing whitespace."""
    reporter = AllureReporter(results_dir=tmp_path / "quoted_passwords")
    masked = reporter.mask_text(input_text)
    assert expected_contains in masked
    assert "with spaces" not in masked


def test_allure_reporter_password_mask_pattern_unquoted_text_not_overmasked_negative(
    tmp_path: Path,
) -> None:
    """Verify normal quoted text not matching credential keywords is not masked."""
    reporter = AllureReporter(results_dir=tmp_path / "non_password_quoted")
    text = 'User selected "Option A with spaces" from dropdown'
    masked = reporter.mask_text(text)
    assert masked == text


@pytest.mark.smoke
def test_allure_reporter_url_credentials_in_traces_positive(tmp_path: Path) -> None:
    """Verify URL_CREDENTIAL_PATTERN redacts credentials in general error messages and traces."""
    reporter = AllureReporter(results_dir=tmp_path / "url_cred_traces")
    trace = "Connection failed at https://svc_user:VerySecretKey456@cluster.corp.internal:8080/health"
    masked = reporter.mask_text(trace, step=None)

    assert "VerySecretKey456" not in masked
    assert "https://svc_user:[REDACTED]@cluster.corp.internal:8080/health" in masked


def test_allure_reporter_clean_url_not_masked_negative(tmp_path: Path) -> None:
    """Verify clean URLs without embedded credentials are preserved intact."""
    reporter = AllureReporter(results_dir=tmp_path / "url_clean")
    url_text = "Navigated to https://portal.internal.net:8080/dashboard"
    masked = reporter.mask_text(url_text, step=None)
    assert masked == url_text


@pytest.mark.smoke
def test_allure_reporter_avoid_overmasking_short_values_positive(
    tmp_path: Path,
) -> None:
    """Verify mask_text avoids over-masking short step values (< 3 chars) on non-sensitive steps."""
    reporter = AllureReporter(results_dir=tmp_path / "overmasking_test")
    step = StepDefinition(
        step_num=1,
        raw_text="Select option",
        action="select",
        target="#country-code",
        value="VE",
    )
    text = "Selected country code VE successfully."
    masked = reporter.mask_text(text, step=step)

    # VE should NOT be redacted since length < 3 and action/target is not sensitive
    assert masked == "Selected country code VE successfully."


def test_allure_reporter_short_value_masked_when_sensitive_step_negative(
    tmp_path: Path,
) -> None:
    """Verify mask_text DOES mask short step values when action/target is a sensitive credential."""
    reporter = AllureReporter(results_dir=tmp_path / "sensitive_short_val")
    step = StepDefinition(
        step_num=1,
        raw_text="Enter pin",
        action="fill",
        target="input[name='pin']",
        value="12",
    )
    text = "Entered PIN 12 in the field"
    masked = reporter.mask_text(text, step=step)

    # 12 SHOULD be redacted because target is sensitive ('pin')
    assert "12" not in masked
    assert "[REDACTED]" in masked
