"""Executive PDF Reporter using ReportLab Platypus.

Compiles test case execution telemetry, metadata grids, step-by-step verdicts,
and scaled screenshot thumbnails into executive PDF reports.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from parsers.models import ExecutionReport, StepResult


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic total page count in footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        """Capture page state for deferred rendering."""
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        """Render footers with accurate total page count on final pass."""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_footer(self, page_count: int) -> None:
        """Draw running footer line, timestamp, and page numbers."""
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        page_width, _ = self._pagesize
        margin = 36.0

        # Footer divider line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(margin, 36, page_width - margin, 36)

        # Footer left: brand & generated timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.drawString(margin, 24, f"Exelixi QA • Generado: {now_str} • Confidencial")

        # Footer right: page numbers
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(page_width - margin, 24, page_str)

        self.restoreState()


class PDFReporter:
    """Generates professional executive test execution reports in PDF format."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Define customized typographic styles for report elements."""
        self.title_style = ParagraphStyle(
            "ExecutiveTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
        )
        self.subtitle_style = ParagraphStyle(
            "ExecutiveSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#475569"),
        )
        self.badge_style = ParagraphStyle(
            "StatusBadge",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            alignment=1,  # Center
            textColor=colors.white,
        )
        self.meta_label_style = ParagraphStyle(
            "MetaLabel",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#475569"),
        )
        self.meta_value_style = ParagraphStyle(
            "MetaValue",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
        )
        self.section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=6,
        )
        self.cell_center = ParagraphStyle(
            "CellCenter",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=1,  # Center
            textColor=colors.HexColor("#1E293B"),
        )
        self.cell_text = ParagraphStyle(
            "CellText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1E293B"),
        )
        self.callout_title = ParagraphStyle(
            "CalloutTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#1E3A8A"),
        )
        self.callout_text = ParagraphStyle(
            "CalloutText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1E293B"),
        )

    def _build_header(self, report: ExecutionReport) -> Table:
        status_upper = report.status.upper()
        if status_upper == "PASSED":
            badge_bg = colors.HexColor("#16A34A")
            badge_text = "PASSED"
        elif status_upper == "PARTIAL":
            badge_bg = colors.HexColor("#D97706")
            badge_text = "PARTIAL"
        else:
            badge_bg = colors.HexColor("#DC2626")
            badge_text = "FAILED"

        badge_p = Paragraph(f"<b>{badge_text}</b>", self.badge_style)
        badge_table = Table([[badge_p]], colWidths=[120], rowHeights=[32])
        badge_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), badge_bg),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("CORNERPAD", (0, 0), (-1, -1), 4),
                ]
            )
        )

        left_content = [
            Paragraph("EXELIXI QA", self.title_style),
            Paragraph("Informe Ejecutivo de Automatización de Pruebas", self.subtitle_style),
            Spacer(1, 4),
            Paragraph(f"<b>Escenario:</b> {report.title}", self.meta_value_style),
        ]

        header_table = Table([[left_content, badge_table]], colWidths=[400, 140])
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return header_table

    def _build_metadata_grid(self, report: ExecutionReport) -> Table:
        """Construct the structured test run metadata grid."""
        result_parts = [f"{report.passed_count} Aprobados", f"{report.failed_count} Fallidos"]
        if getattr(report, "manual_count", 0) > 0:
            result_parts.append(f"{report.manual_count} Manuales")
        result_summary = " / ".join(result_parts)
        grid_data = [
            [
                Paragraph("Caso ID:", self.meta_label_style),
                Paragraph(report.case_id, self.meta_value_style),
                Paragraph("Módulo:", self.meta_label_style),
                Paragraph(report.module, self.meta_value_style),
            ],
            [
                Paragraph("Entorno:", self.meta_label_style),
                Paragraph(report.environment, self.meta_value_style),
                Paragraph("Duración Total:", self.meta_label_style),
                Paragraph(f"{report.duration_seconds:.2f} s", self.meta_value_style),
            ],
            [
                Paragraph("Inicio:", self.meta_label_style),
                Paragraph(report.started_at, self.meta_value_style),
                Paragraph("Fin:", self.meta_label_style),
                Paragraph(report.finished_at, self.meta_value_style),
            ],
            [
                Paragraph("Total Pasos:", self.meta_label_style),
                Paragraph(str(report.total_steps), self.meta_value_style),
                Paragraph("Balance:", self.meta_label_style),
                Paragraph(result_summary, self.meta_value_style),
            ],
        ]

        table = Table(grid_data, colWidths=[100, 170, 100, 170])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return table

    def _build_summary_callout(self, report: ExecutionReport) -> Table | None:
        """Build callout element for scenario purpose and execution notes."""
        if not report.summary_notes:
            return None

        content = [
            Paragraph("<b>Objetivo y Notas de Ejecución:</b>", self.callout_title),
            Spacer(1, 2),
            Paragraph(report.summary_notes, self.callout_text),
        ]
        table = Table([[content]], colWidths=[540])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#BFDBFE")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3.0, colors.HexColor("#2563EB")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return table

    def _build_step_evidence_table(self, steps: list[StepResult]) -> Table:
        """Construct the step-by-step evidence table with embedded thumbnails."""
        col_widths = [30, 55, 170, 55, 50, 180]
        header_row = [
            Paragraph("<b>#</b>", self.cell_center),
            Paragraph("<b>Acción</b>", self.cell_center),
            Paragraph("<b>Detalle / Objetivo</b>", self.cell_text),
            Paragraph("<b>Estado</b>", self.cell_center),
            Paragraph("<b>Duración</b>", self.cell_center),
            Paragraph("<b>Captura de Evidencia</b>", self.cell_center),
        ]

        table_data: list[list[Any]] = [header_row]

        if not steps:
            empty_row: list[Any] = [
                Paragraph("—", self.cell_center),
                Paragraph("—", self.cell_center),
                Paragraph("<i>No se registraron pasos en la ejecución.</i>", self.cell_text),
                Paragraph("—", self.cell_center),
                Paragraph("—", self.cell_center),
                Paragraph("<i>Sin evidencia</i>", self.cell_center),
            ]
            table_data.append(empty_row)
        else:
            for step in steps:
                step_status = step.status.upper()
                if step_status == "PASSED":
                    status_color = "#16A34A"
                elif step_status == "MANUAL":
                    status_color = "#D97706"
                else:
                    status_color = "#DC2626"
                status_html = f"<font color='{status_color}'><b>{step_status}</b></font>"

                detail_html = f"<b>{step.target}</b>"
                if step.error_message:
                    detail_html += (
                        f"<br/><font color='#DC2626'><b>Error:</b> {step.error_message}</font>"
                    )

                img_element: Any
                if step.screenshot_path and os.path.isfile(step.screenshot_path):
                    try:
                        img_element = Image(step.screenshot_path, width=170, height=95)
                    except (OSError, ValueError, TypeError):
                        img_element = Paragraph(
                            "<font color='#94A3B8'><i>Error de lectura</i></font>",
                            self.cell_center,
                        )
                else:
                    img_element = Paragraph(
                        "<font color='#94A3B8'><i>Sin captura</i></font>",
                        self.cell_center,
                    )

                row: list[Any] = [
                    Paragraph(str(step.step_num), self.cell_center),
                    Paragraph(step.action.upper(), self.cell_center),
                    Paragraph(detail_html, self.cell_text),
                    Paragraph(status_html, self.cell_center),
                    Paragraph(f"{step.duration_ms:.0f} ms", self.cell_center),
                    img_element,
                ]
                table_data.append(row)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_commands: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]

        # Add alternating row background for steps
        for row_idx in range(1, len(table_data)):
            bg = colors.white if row_idx % 2 == 1 else colors.HexColor("#F8FAFC")
            style_commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))

        table.setStyle(TableStyle(style_commands))
        return table

    def generate_report(self, report: ExecutionReport, output_path: str) -> str:
        """Compile execution report data into an executive PDF document.

        Args:
            report: Populated ExecutionReport instance with telemetry and step details.
            output_path: Target filesystem path for the output PDF.

        Returns:
            The string path of the generated PDF report.
        """
        resolved_path = Path(output_path).resolve()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(resolved_path),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=48,
        )

        story: list[Any] = []

        # 1. Executive Header
        story.append(self._build_header(report))
        story.append(Spacer(1, 12))

        # 2. Metadata Grid
        story.append(self._build_metadata_grid(report))
        story.append(Spacer(1, 10))

        # 3. Callout / Scope (if present)
        callout = self._build_summary_callout(report)
        if callout:
            story.append(callout)
            story.append(Spacer(1, 12))

        # 4. Step Evidence Section
        story.append(
            KeepTogether(
                [
                    Paragraph("Evidencia Paso a Paso / Step Evidence", self.section_heading_style),
                ]
            )
        )
        story.append(self._build_step_evidence_table(report.steps))

        doc.build(story, canvasmaker=NumberedCanvas)
        return str(resolved_path)
