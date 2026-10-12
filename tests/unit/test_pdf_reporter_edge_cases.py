"""Edge-case unit tests for the PDF evidence reporter (PDFReporter and NumberedCanvas).

Covers edge conditions including:
1. Empty steps report (0 steps, verify no division-by-zero or indexing crash).
2. Long error messages and multiline descriptions wrapped in Paragraphs without overflowing.
3. Missing or corrupted screenshot paths falling back gracefully without crashing PDF generation.
4. Multi-page pagination (>25 steps across multiple pages, verifying page counts and footers).
5. XML entities and Spanish / special characters handling without ReportLab parsing exceptions.
"""

from html import escape
from pathlib import Path
from unittest.mock import patch

import pypdf
import pytest
from PIL import Image

from parsers.models import ExecutionReport, StepResult
from reporting.pdf_reporter import PDFReporter

# ==============================================================================
# Requirement 1: Empty steps report (0 steps)
# ==============================================================================


@pytest.mark.smoke
def test_empty_steps_report_generates_valid_pdf_positive(tmp_path: Path) -> None:
    """Positive: Generating a report with steps=[] produces a valid PDF file."""
    output_pdf = tmp_path / "empty_steps_report.pdf"
    reporter = PDFReporter()

    report = ExecutionReport(
        case_id="TC-EDGE-001",
        module="Authentication",
        title="Empty Steps Scenario",
        status="PASSED",
        started_at="2026-10-12 10:00:00",
        finished_at="2026-10-12 10:00:05",
        duration_seconds=5.0,
        environment="Staging",
        summary_notes="Execution without discrete action steps recorded.",
        steps=[],
    )

    result_path = reporter.generate_report(report, str(output_pdf))

    assert Path(result_path).exists()
    assert result_path == str(output_pdf)

    content = output_pdf.read_bytes()
    assert content.startswith(b"%PDF-"), "Generated file must start with PDF header marker"
    assert len(content) > 1024, "Generated PDF must contain valid binary payload"

    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    extracted_text = "".join(page.extract_text() for page in reader.pages)
    assert "TC-EDGE-001" in extracted_text
    assert "No se registraron pasos en la ejecución" in extracted_text
    assert "0 Aprobados / 0 Fallidos" in extracted_text


@pytest.mark.smoke
def test_empty_steps_report_zero_duration_and_counts_negative(tmp_path: Path) -> None:
    """Negative: Report with 0 steps, 0.0s duration, None summary notes does not crash or raise ZeroDivisionError."""
    output_pdf = tmp_path / "empty_steps_zero_duration.pdf"
    reporter = PDFReporter()

    # Minimal edge payload with 0.0 duration and no summary notes
    report = ExecutionReport(
        case_id="TC-ZERO-000",
        module="Core",
        title="Zero Duration Scenario",
        status="FAILED",
        started_at="2026-10-12 10:00:00",
        finished_at="2026-10-12 10:00:00",
        duration_seconds=0.0,
        environment="QA",
        summary_notes=None,
        steps=[],
    )

    result_path = reporter.generate_report(report, str(output_pdf))

    assert Path(result_path).exists()
    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    extracted_text = "".join(page.extract_text() for page in reader.pages)
    assert "0.00 s" in extracted_text
    assert "FAILED" in extracted_text
    assert "No se registraron pasos en la ejecución" in extracted_text


# ==============================================================================
# Requirement 2: Long error messages / text wrapping
# ==============================================================================


@pytest.mark.smoke
def test_long_error_stack_traces_wrapped_without_crashing_positive(tmp_path: Path) -> None:
    """Positive: Test step with 1000+ char multiline error stack trace generates PDF successfully."""
    output_pdf = tmp_path / "long_error_report.pdf"
    reporter = PDFReporter()

    multiline_stack_trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/runners/doc_runner.py", line 142, in execute_action\n'
        "    await page.locator(selector).click(timeout=30000)\n"
        "PlaywrightTimeoutError: Timeout 30000ms exceeded.\n"
        "Call log:\n"
        "  - waiting for locator('#submit-btn')\n"
        "  - locator resolved to <button id='submit-btn' disabled>Submit</button>\n"
        "  - element is disabled, waiting for element to be enabled...\n"
        + ("Additional trace context line repeating for length validation. " * 15)
    )
    assert len(multiline_stack_trace) > 700

    report = ExecutionReport(
        case_id="TC-LONG-ERR",
        module="Checkout",
        title="Payment Gateway Timeout Scenario",
        status="FAILED",
        started_at="2026-10-12 11:00:00",
        finished_at="2026-10-12 11:00:35",
        duration_seconds=35.0,
        environment="Production-Staging",
        summary_notes="Step failed with an extensive multiline diagnostic error dump.",
        steps=[
            StepResult(
                step_num=1,
                action="click",
                target="Confirm and submit payment order transaction button",
                status="FAILED",
                duration_ms=30000.0,
                error_message=multiline_stack_trace,
            )
        ],
    )

    result_path = reporter.generate_report(report, str(output_pdf))

    assert Path(result_path).exists()
    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) >= 1
    text = "".join(page.extract_text() for page in reader.pages)
    assert "PlaywrightTimeoutError" in text
    assert "TC-LONG-ERR" in text


@pytest.mark.smoke
def test_long_target_and_summary_descriptions_negative_boundary(tmp_path: Path) -> None:
    """Negative/Boundary: Step target and summary notes containing continuous strings (500+ chars) wrap cleanly."""
    output_pdf = tmp_path / "long_descriptions_report.pdf"
    reporter = PDFReporter()

    very_long_target = "ComplexDeeplyNestedDOMElementSelectorPath_" + ("Section_SubSection_Component_" * 15)
    very_long_summary = (
        "Executive Summary Deep Analysis: "
        + ("Comprehensive regression testing conducted over microservices architecture with high concurrency. " * 8)
    )
    assert len(very_long_target) > 400
    assert len(very_long_summary) > 600

    report = ExecutionReport(
        case_id="TC-LONG-TEXT",
        module="Catalog",
        title="Long Description Text Scenario",
        status="PASSED",
        started_at="2026-10-12 11:15:00",
        finished_at="2026-10-12 11:15:10",
        duration_seconds=10.0,
        summary_notes=very_long_summary,
        steps=[
            StepResult(
                step_num=1,
                action="validate_deep_tree",
                target=very_long_target,
                status="PASSED",
                duration_ms=450.0,
            )
        ],
    )

    result_path = reporter.generate_report(report, str(output_pdf))

    assert Path(result_path).exists()
    reader = pypdf.PdfReader(str(output_pdf))
    raw_text = "".join(page.extract_text() for page in reader.pages)
    normalized_text = "".join(raw_text.split())
    assert "TC-LONG-TEXT" in raw_text
    assert "ComplexDeeplyNestedDOMElementSelectorPath" in normalized_text
    assert "ExecutiveSummaryDeepAnalysis" in normalized_text


# ==============================================================================
# Requirement 3: Missing or corrupted screenshot handling
# ==============================================================================


@pytest.mark.smoke
def test_valid_screenshot_thumbnail_embedded_positive(tmp_path: Path) -> None:
    """Positive: Valid screenshot image is rendered as a thumbnail inside the evidence table."""
    valid_screenshot = tmp_path / "valid_screenshot.png"
    img = Image.new("RGB", (640, 480), color=(34, 139, 34))
    img.save(valid_screenshot)

    report = ExecutionReport(
        case_id="TC-VALID-IMG",
        module="UI",
        title="Valid Image Scenario",
        status="PASSED",
        started_at="2026-10-12 12:00:00",
        finished_at="2026-10-12 12:00:05",
        duration_seconds=5.0,
        steps=[
            StepResult(
                step_num=1,
                action="screenshot",
                target="dashboard header viewport",
                status="PASSED",
                duration_ms=300.0,
                screenshot_path=str(valid_screenshot),
            )
        ],
    )

    output_pdf = tmp_path / "valid_image_report.pdf"
    reporter = PDFReporter()
    reporter.generate_report(report, str(output_pdf))

    assert output_pdf.exists()
    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "TC-VALID-IMG" in text
    # Should not display fallback labels when valid image is loaded
    assert "Sin captura" not in text
    assert "Error de lectura" not in text


@pytest.mark.smoke
def test_missing_screenshot_falls_back_gracefully_negative(tmp_path: Path) -> None:
    """Negative: Referencing a non-existent image path does not crash and renders 'Sin captura' fallback."""
    non_existent_img = tmp_path / "does_not_exist_snapshot_999.png"
    assert not non_existent_img.exists()

    report = ExecutionReport(
        case_id="TC-MISSING-IMG",
        module="Reports",
        title="Missing Image Fallback Scenario",
        status="PASSED",
        started_at="2026-10-12 12:05:00",
        finished_at="2026-10-12 12:05:08",
        duration_seconds=8.0,
        steps=[
            StepResult(
                step_num=1,
                action="click",
                target="Download Report Button",
                status="PASSED",
                duration_ms=450.0,
                screenshot_path=str(non_existent_img),
            )
        ],
    )

    output_pdf = tmp_path / "missing_image_report.pdf"
    reporter = PDFReporter()
    reporter.generate_report(report, str(output_pdf))

    assert output_pdf.exists()
    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "TC-MISSING-IMG" in text
    assert "Sin captura" in text


@pytest.mark.smoke
def test_corrupted_screenshot_falls_back_gracefully_negative(tmp_path: Path) -> None:
    """Negative: Referencing a corrupted screenshot file falls back gracefully without raising an exception."""
    corrupted_img = tmp_path / "corrupted_screenshot.png"
    corrupted_img.write_bytes(b"CORRUPTED_BINARY_HEADER_NOT_A_PNG")

    report = ExecutionReport(
        case_id="TC-CORRUPT-IMG",
        module="Reports",
        title="Corrupted Screenshot Fallback Scenario",
        status="FAILED",
        started_at="2026-10-12 12:10:00",
        finished_at="2026-10-12 12:10:04",
        duration_seconds=4.0,
        steps=[
            StepResult(
                step_num=1,
                action="verify_element",
                target="Broken Chart Visual Canvas",
                status="FAILED",
                duration_ms=1200.0,
                screenshot_path=str(corrupted_img),
                error_message="Image binary header invalid",
            )
        ],
    )

    output_pdf = tmp_path / "corrupted_image_report.pdf"
    reporter = PDFReporter()

    with patch("reporting.pdf_reporter.Image", side_effect=OSError("Unidentified image error")):
        reporter.generate_report(report, str(output_pdf))

    assert output_pdf.exists()
    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "TC-CORRUPT-IMG" in text
    assert "Error de lectura" in text


# ==============================================================================
# Requirement 4: Multi-page pagination (>25 steps)
# ==============================================================================


@pytest.mark.smoke
def test_single_page_short_report_positive(tmp_path: Path) -> None:
    """Positive: Test report with 3 steps fits within a single page and has 'Página 1 de 1'."""
    steps = [
        StepResult(step_num=i, action="click", target=f"Field {i}", status="PASSED", duration_ms=100.0)
        for i in range(1, 4)
    ]
    report = ExecutionReport(
        case_id="TC-PAG-SHORT",
        module="Settings",
        title="Short Execution Scenario",
        status="PASSED",
        started_at="2026-10-12 13:00:00",
        finished_at="2026-10-12 13:00:03",
        duration_seconds=3.0,
        steps=steps,
    )

    output_pdf = tmp_path / "short_page_report.pdf"
    reporter = PDFReporter()
    reporter.generate_report(report, str(output_pdf))

    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Página 1 de 1" in text


@pytest.mark.smoke
def test_multi_page_pagination_with_many_steps_positive(tmp_path: Path) -> None:
    """Positive: Test report with 30 steps spanning multiple pages calculates accurate page counts and footers."""
    total_steps_count = 30
    steps = [
        StepResult(
            step_num=i,
            action="verify_grid_row" if i % 2 == 0 else "click_table_action",
            target=f"Data Grid Record Row #{i} - Detailed Description",
            status="PASSED" if i != 28 else "FAILED",
            duration_ms=120.0 + (i * 10),
            error_message="Assertion mismatch on row 28" if i == 28 else None,
        )
        for i in range(1, total_steps_count + 1)
    ]

    report = ExecutionReport(
        case_id="TC-MULTI-PAGE",
        module="Enterprise Data Grid",
        title="Massive Data Grid Validation",
        status="FAILED",
        started_at="2026-10-12 13:30:00",
        finished_at="2026-10-12 13:31:15",
        duration_seconds=75.0,
        summary_notes="Execution suite covering 30 steps across large tables.",
        steps=steps,
    )

    output_pdf = tmp_path / "multi_page_report.pdf"
    reporter = PDFReporter()
    reporter.generate_report(report, str(output_pdf))

    assert output_pdf.exists()
    reader = pypdf.PdfReader(str(output_pdf))
    total_pages = len(reader.pages)
    assert total_pages > 1, f"Expected >1 pages for 30 steps, got {total_pages}"

    # Verify dynamic two-pass canvas footers on every page
    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        expected_footer = f"Página {page_idx} de {total_pages}"
        assert expected_footer in page_text, (
            f"Footer '{expected_footer}' not found on page {page_idx} of {total_pages}"
        )


# ==============================================================================
# Requirement 5: XML entities and Spanish / Special characters handling
# ==============================================================================


@pytest.mark.smoke
def test_safe_xml_entities_and_spanish_characters_positive(tmp_path: Path) -> None:
    """Positive: Test report containing safely escaped XML entities (&lt;, &gt;, &amp;, &quot;) and Spanish accents."""
    title_raw = "Módulo de Facturación: Verificación de Contraseña & Parámetros"
    title_escaped = escape(title_raw)

    summary_notes_escaped = (
        "Prueba ejecutada con éxito en entorno de Staging. "
        "Soporta caracteres en español como á, é, í, ó, ú, ñ, Ñ, ü, Ü, ¡, ¿. "
        "Entidades XML protegidas: " + escape('<div id="invoice" data-active="true"> & Total > 100</div>')
    )

    steps = [
        StepResult(
            step_num=1,
            action="fill_input",
            target=escape("Campo de texto: <input name='contraseña' id=\"pwd_1\"> & botón 'Validar'"),
            status="PASSED",
            duration_ms=250.0,
        ),
        StepResult(
            step_num=2,
            action="click",
            target=escape("Botón 'Confirmar Envío de Información'"),
            status="FAILED",
            duration_ms=500.0,
            error_message=escape("Error: <XMLResponse code='500'> & status='failed'</XMLResponse>"),
        ),
    ]

    report = ExecutionReport(
        case_id="TC-SPANISH-XML",
        module="Facturación Electrónica",
        title=title_escaped,
        status="FAILED",
        started_at="2026-10-12 14:00:00",
        finished_at="2026-10-12 14:00:10",
        duration_seconds=10.0,
        summary_notes=summary_notes_escaped,
        steps=steps,
    )

    output_pdf = tmp_path / "xml_spanish_report.pdf"
    reporter = PDFReporter()

    # Must complete cleanly without ReportLab paraparser XML entity syntax errors
    result_path = reporter.generate_report(report, str(output_pdf))

    assert Path(result_path).exists()
    reader = pypdf.PdfReader(str(output_pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()

    assert "TC-SPANISH-XML" in text
    assert "Facturación Electrónica" in text
    assert "Contraseña" in text
    assert "Confirmar Envío de Información" in text


@pytest.mark.smoke
def test_unescaped_malformed_xml_tags_cause_parsing_exception_negative(tmp_path: Path) -> None:
    """Negative: Demonstrates that unescaped raw malformed XML syntax (e.g. unclosed tags) causes paraparser syntax error."""
    unclosed_malformed_title = "Unclosed Tag Scenario <unclosed_tag_without_closing_bracket"

    report = ExecutionReport(
        case_id="TC-MALFORMED-XML",
        module="Security",
        title=unclosed_malformed_title,
        status="PASSED",
        started_at="2026-10-12 14:10:00",
        finished_at="2026-10-12 14:10:05",
        duration_seconds=5.0,
        steps=[],
    )

    output_pdf = tmp_path / "malformed_xml_report.pdf"
    reporter = PDFReporter()

    with pytest.raises(ValueError, match="paraparser: syntax error"):
        reporter.generate_report(report, str(output_pdf))
