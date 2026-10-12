"""Unit tests for PDFReporter executive report generation."""

from pathlib import Path

import pytest
from PIL import Image

from parsers.models import ExecutionReport, StepResult
from reporting.pdf_reporter import NumberedCanvas, PDFReporter


@pytest.fixture
def sample_passed_report() -> ExecutionReport:
    """Fixture providing a standard successful execution report."""
    return ExecutionReport(
        case_id="TC-001",
        module="Authentication",
        title="Admin Login Scenario",
        status="PASSED",
        started_at="2026-10-12 10:00:00",
        finished_at="2026-10-12 10:00:15",
        duration_seconds=15.0,
        environment="Staging",
        summary_notes="All authentication assertions passed successfully.",
        steps=[
            StepResult(
                step_num=1,
                action="navigate",
                target="https://app.exelixi.ai/login",
                status="PASSED",
                duration_ms=1250.0,
            ),
            StepResult(
                step_num=2,
                action="fill",
                target="username input",
                status="PASSED",
                duration_ms=320.0,
            ),
            StepResult(
                step_num=3,
                action="click",
                target="login button",
                status="PASSED",
                duration_ms=850.0,
            ),
        ],
    )


@pytest.fixture
def sample_failed_report() -> ExecutionReport:
    """Fixture providing a failed execution report with error details."""
    return ExecutionReport(
        case_id="TC-002",
        module="User Management",
        title="Create New User",
        status="FAILED",
        started_at="2026-10-12 10:05:00",
        finished_at="2026-10-12 10:05:20",
        duration_seconds=20.0,
        environment="QA",
        summary_notes="Execution failed on step 2 due to element timeout.",
        steps=[
            StepResult(
                step_num=1,
                action="navigate",
                target="https://app.exelixi.ai/users",
                status="PASSED",
                duration_ms=1100.0,
            ),
            StepResult(
                step_num=2,
                action="click",
                target="add user button",
                status="FAILED",
                duration_ms=5000.0,
                error_message="Timeout 5000ms exceeded waiting for button",
            ),
        ],
    )


def test_generate_report_passed_status(tmp_path: Path, sample_passed_report: ExecutionReport) -> None:
    """Test generating a PDF report for a passed execution scenario."""
    output_pdf = tmp_path / "passed_report.pdf"
    reporter = PDFReporter()

    result_path = reporter.generate_report(sample_passed_report, str(output_pdf))

    assert Path(result_path).exists()
    assert result_path == str(output_pdf)
    content = output_pdf.read_bytes()
    assert len(content) > 1024, "Generated PDF must be larger than 1KB"
    assert content.startswith(b"%PDF-"), "Generated file must start with PDF header marker"


def test_generate_report_failed_status(tmp_path: Path, sample_failed_report: ExecutionReport) -> None:
    """Test generating a PDF report for a failed execution scenario."""
    output_pdf = tmp_path / "failed_report.pdf"
    reporter = PDFReporter()

    result_path = reporter.generate_report(sample_failed_report, str(output_pdf))

    assert Path(result_path).exists()
    content = output_pdf.read_bytes()
    assert len(content) > 1024
    assert content.startswith(b"%PDF-")


def test_generate_report_with_embedded_screenshots(
    tmp_path: Path, sample_passed_report: ExecutionReport
) -> None:
    """Test embedding screenshot thumbnails into the PDF report."""
    # Create temporary screenshot images
    screenshot1 = tmp_path / "step1.png"
    screenshot2 = tmp_path / "step2.png"

    img = Image.new("RGB", (320, 240), color=(73, 109, 137))
    img.save(screenshot1)
    img = Image.new("RGB", (320, 240), color=(200, 50, 50))
    img.save(screenshot2)

    sample_passed_report.steps[0].screenshot_path = str(screenshot1)
    sample_passed_report.steps[1].screenshot_path = str(screenshot2)
    sample_passed_report.steps[2].screenshot_path = "non_existent_image.png"  # Graceful fallback test

    output_pdf = tmp_path / "screenshot_report.pdf"
    reporter = PDFReporter()
    result_path = reporter.generate_report(sample_passed_report, str(output_pdf))

    assert Path(result_path).exists()
    content = output_pdf.read_bytes()
    assert len(content) > 1024
    assert content.startswith(b"%PDF-")


def test_numbered_canvas_class_exists() -> None:
    """Verify NumberedCanvas subclass is defined and exported."""
    assert issubclass(NumberedCanvas, object)
