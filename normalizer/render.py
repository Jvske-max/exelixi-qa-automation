"""Renderer converting NormalizedDoc specifications into canonical Word (.docx) and Markdown gaps documents."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

import docx

from normalizer.schema import Case, NormalizedDoc

SEVERITY_ORDER: dict[str, int] = {
    "blocking": 0,
    "warning": 1,
    "info": 2,
}


def _get_gap_field(gap: Any, field: str, default: str = "") -> str:
    """Safely extract field from Gap instance or dictionary."""
    if isinstance(gap, dict):
        return str(gap.get(field, default))
    return str(getattr(gap, field, default))


def _sanitize_filename(raw_id: str) -> str:
    """Sanitize identifier to ensure safe filenames without path traversal."""
    cleaned = re.sub(r"[^\w\-.]", "_", raw_id)
    # Strip dangerous characters and excessive underscores
    cleaned = cleaned.replace("..", "_").strip("._")
    return cleaned if cleaned else "UNKNOWN"


ENV_VAR_PATTERN = re.compile(r"^\$\{[A-Z0-9_]+\}$")
CREDENTIAL_TARGET_PATTERN = re.compile(r"\b(?:clave|contrase[ñn]a|password|pin|token)\b", re.IGNORECASE)
USER_TARGET_PATTERN = re.compile(r"\b(?:usuario|user|username)\b", re.IGNORECASE)
CEDULA_PATTERN = re.compile(r"\b[VEve]-?\d{6,9}(?!-\d)\b")
RIF_PATTERN = re.compile(r"\b(?:[JjGg]-?\d{8,9}-?\d?|[VvEePp]-?\d{6,9}-\d)\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\b")


def sanitize_narrative_text(
    text: str,
    secrets_to_mask: list[str] | None = None,
) -> str:
    """Sanitize PII (cédulas, RIFs, emails, tokens) and secrets from narrative text."""
    if not text:
        return text

    sanitized = text

    if secrets_to_mask:
        for sec in sorted(secrets_to_mask, key=len, reverse=True):
            if sec and len(sec.strip()) > 1:
                sanitized = sanitized.replace(sec, "[DATO_PROTEGIDO]")

    sanitized = JWT_PATTERN.sub("[TOKEN_PROTEGIDO]", sanitized)
    sanitized = RIF_PATTERN.sub("[RIF_PROTEGIDO]", sanitized)
    sanitized = CEDULA_PATTERN.sub("[CEDULA_PROTEGIDA]", sanitized)
    sanitized = EMAIL_PATTERN.sub("[EMAIL_PROTEGIDO]", sanitized)

    return sanitized


def _format_credential(value: str | None, prefix: str, role: str | None = None) -> str:
    """Format credential ensuring environment variable derived only from role or DEFAULT."""
    if value:
        val = str(value).strip()
        if ENV_VAR_PATTERN.match(val):
            return val
    if role:
        clean_role = re.sub(r"[^\w]", "_", str(role).strip()).upper()
        return f"${{{prefix}_{clean_role}}}"
    return f"${{{prefix}_DEFAULT}}"


def _render_gaps_report(case: Case, gaps_file: Path, secrets_to_mask: list[str] | None = None) -> None:
    """Generate Markdown report for identified gaps ordered by severity."""
    sorted_gaps = sorted(
        case.gaps,
        key=lambda g: SEVERITY_ORDER.get(_get_gap_field(g, "severity").lower(), 99),
    )

    lines: list[str] = [
        f"# Reporte de Faltantes - Caso {case.n}",
        "",
        f"**Estado de Normalización:** {case.status}  ",
        f"**Total de Faltantes:** {len(sorted_gaps)}",
        "",
        "## Resumen de Faltantes",
        "",
        "| Severidad | Tipo | Ubicación | Solicitud |",
        "| --- | --- | --- | --- |",
    ]

    for gap in sorted_gaps:
        sev = _get_gap_field(gap, "severity", "info")
        gap_type = _get_gap_field(gap, "type", "general")
        where = _get_gap_field(gap, "where", f"Caso {case.n}")
        ask = _get_gap_field(gap, "ask", "")
        # Sanitize pipe symbols to avoid breaking markdown tables
        safe_ask = ask.replace("|", "/")
        safe_where = where.replace("|", "/")
        lines.append(f"| {sev} | {gap_type} | {safe_where} | {safe_ask} |")

    lines.append("")
    lines.append("## Detalle de Faltantes")
    lines.append("")

    for idx, gap in enumerate(sorted_gaps, 1):
        sev = _get_gap_field(gap, "severity", "info").upper()
        gap_type = _get_gap_field(gap, "type", "general")
        where = _get_gap_field(gap, "where", f"Caso {case.n}")
        ask = _get_gap_field(gap, "ask", "")

        lines.append(f"### {idx}. [{sev}] `{gap_type}`")
        lines.append(f"- **Ubicación:** {where}")
        lines.append(f"- **Acción requerida:** {ask}")
        lines.append("")

    sanitized_lines = [sanitize_narrative_text(line, secrets_to_mask) for line in lines]
    report_text = "\n".join(sanitized_lines)
    if secrets_to_mask:
        for sec in secrets_to_mask:
            if sec and len(sec) > 1:
                report_text = report_text.replace(sec, "[REDACTED]")

    gaps_file.write_text(report_text, encoding="utf-8")


def render_case(
    doc: NormalizedDoc,
    case: Case,
    out_dir: Path,
    known_passwords: set[str] | None = None,
) -> Path:
    """Render a canonical .docx file (and optional .gaps.md) for an individual test case."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Determine safe filename
    raw_case_id = (
        doc.meta.get("identificador del caso")
        or doc.meta.get("caso_id")
        or doc.meta.get("caso")
        or f"CASE-{case.n}"
    )
    safe_case_id = _sanitize_filename(str(raw_case_id))
    stem = f"{safe_case_id}-caso{case.n}"
    docx_path = out_dir / f"{stem}.docx"

    # 2. Build Document
    document = docx.Document()

    # a. Tabla "Identificación" (2 rows x 9 cols)
    headers = [
        "Fecha",
        "Módulo",
        "Identificador del caso",
        "Descripción corta",
        "Descripción completa",
        "Ambiente de prueba",
        "Analista Programador",
        "Analista de prueba",
        "Estado de normalización",
    ]

    fecha = str(doc.meta.get("fecha") or datetime.date.today().isoformat())
    modulo = str(doc.meta.get("módulo") or doc.meta.get("modulo") or "General")
    identificador = str(raw_case_id)
    desc_corta = str(case.title or doc.meta.get("descripción corta") or doc.meta.get("descripcion corta") or "")
    desc_completa = str(case.objective or case.title or doc.meta.get("descripción completa") or "")
    ambiente = str(doc.meta.get("ambiente de prueba") or doc.meta.get("ambiente") or "QA")
    analista_prog = "Exelixi QA"
    analista_prueba = "Exelixi QA"
    estado = case.status

    values = [
        fecha,
        modulo,
        identificador,
        desc_corta,
        desc_completa,
        ambiente,
        analista_prog,
        analista_prueba,
        estado,
    ]

    table = document.add_table(rows=2, cols=len(headers))
    for col_idx, (h, v) in enumerate(zip(headers, values)):
        table.rows[0].cells[col_idx].text = h
        table.rows[1].cells[col_idx].text = v

    # b. Canonical Paragraph Sequence
    # CRITICAL: 'Caso <n>: <title>' must be the FIRST paragraph containing the word 'caso'.
    # Link: does not contain 'caso'.
    if case.url:
        document.add_paragraph(f"Link: {case.url.strip()}")

    document.add_paragraph(f"Caso {case.n}: {case.title.strip()}")
    document.add_paragraph(f"Objetivo de la Prueba: {case.objective.strip()}")

    # Collect literal secrets that must be masked from any gaps or error text
    secrets_to_mask: list[str] = []
    combined_passwords: set[str] = set(known_passwords) if known_passwords else set()

    # Determine role-based env vars
    role = None
    if case.credentials:
        role = case.credentials.get("rol") or case.credentials.get("role")
    user_default = _format_credential(None, "QA_USER", role)
    pass_default = _format_credential(None, "QA_PASS", role)
    pass_raw_val = None

    # Credentials
    if case.credentials:
        user_raw = (
            case.credentials.get("usuario")
            or case.credentials.get("username")
            or case.credentials.get("user")
        )
        pass_raw = (
            case.credentials.get("clave")
            or case.credentials.get("password")
            or case.credentials.get("pass")
        )

        if pass_raw and not (str(pass_raw).startswith("${") and str(pass_raw).endswith("}")):
            pass_raw_val = str(pass_raw).strip()
            secrets_to_mask.append(pass_raw_val)
            combined_passwords.add(pass_raw_val)

        if user_raw and not (str(user_raw).startswith("${") and str(user_raw).endswith("}")):
            secrets_to_mask.append(str(user_raw).strip())

        if user_raw or role:
            user_fmt = _format_credential(str(user_raw) if user_raw else None, "QA_USER", role)
            document.add_paragraph(f"Usuario: {user_fmt}")

        if pass_raw or role:
            pass_fmt = _format_credential(str(pass_raw) if pass_raw else None, "QA_PASS", role)
            document.add_paragraph(f"Clave: {pass_fmt}")

    # Extract secrets from gaps if any
    for gap in case.gaps:
        gap_type = _get_gap_field(gap, "type")
        if gap_type == "credentials_in_plaintext":
            for attr in ("secret", "value", "val"):
                sec = _get_gap_field(gap, attr)
                if sec and not (sec.startswith("${") and sec.endswith("}")):
                    combined_passwords.add(sec)
                    secrets_to_mask.append(sec)

    if known_passwords:
        for sec in known_passwords:
            if sec and not (sec.startswith("${") and sec.endswith("}")):
                secrets_to_mask.append(sec)

    # c & d. Steps and Manual steps
    exec_idx = 1
    manual_idx = 1

    for step in case.steps:
        action = step.action.lower()
        if action == "manual":
            motivo = step.target or step.value or step.source_quote or "Paso manual pendiente"
            motivo = sanitize_narrative_text(motivo, secrets_to_mask)
            document.add_paragraph(f"Pendiente manual {manual_idx}: {motivo.strip()}")
            manual_idx += 1
        elif action == "navigate":
            document.add_paragraph(f"Paso {exec_idx}: navegar a {step.target.strip()}")
            exec_idx += 1
        elif action == "fill":
            target_str = step.target.strip()
            val = (step.value or "").strip()
            val_unquoted = val.strip("\"'")
            if CREDENTIAL_TARGET_PATTERN.search(target_str):
                if not (val.startswith("${") and val.endswith("}")):
                    secrets_to_mask.append(val)
                    val = pass_default
            elif USER_TARGET_PATTERN.search(target_str):
                if not (val.startswith("${") and val.endswith("}")):
                    secrets_to_mask.append(val)
                    val = user_default
            elif (
                pass_raw_val and (val == pass_raw_val or val_unquoted == pass_raw_val)
            ) or (
                combined_passwords
                and (val in combined_passwords or val_unquoted in combined_passwords)
            ):
                secrets_to_mask.extend([val, val_unquoted])
                val = pass_default
            document.add_paragraph(f"Paso {exec_idx}: escribir {val} en {target_str}")
            exec_idx += 1
        elif action == "click":
            document.add_paragraph(f"Paso {exec_idx}: clic en {step.target.strip()}")
            exec_idx += 1
        elif action == "verify":
            document.add_paragraph(f"Paso {exec_idx}: verificar {step.target.strip()}")
            exec_idx += 1

    # Save document
    document.save(str(docx_path))

    # e. Gaps report generation
    if case.gaps or case.status == "NEEDS_INFO":
        gaps_path = out_dir / f"{stem}.gaps.md"
        _render_gaps_report(case, gaps_path, secrets_to_mask)

    return docx_path
