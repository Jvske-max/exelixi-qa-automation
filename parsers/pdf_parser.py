"""PDF specification parser extracting metadata and steps via pypdf."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from parsers.docx_parser import (
    NOISE_STEP_PATTERN,
    PSR_STEP_PATTERN,
    STD_STEP_PATTERN,
    normalize_psr_action,
    parse_standard_description,
)
from parsers.models import StepDefinition, TestCase


class PdfParser:
    """Parser for PDF (.pdf) test specifications."""

    @classmethod
    def parse(cls, file_path: str | Path) -> TestCase:
        """Parse a .pdf document into a TestCase model."""
        path = Path(file_path)
        reader = PdfReader(str(path))

        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # Extract metadata
        m_case = re.search(
            r"(?:^|\n)\s*(?:Identificador(?:\s+del\s+caso)?|Case\s*ID|Caso\s*ID|Caso)\s*[:=]\s*([A-Za-z0-9_-]+)",
            full_text,
            re.IGNORECASE,
        )
        case_id = m_case.group(1).strip() if m_case else ""

        m_mod = re.search(r"(?:^|\n)\s*(?:Módulo|Modulo|Module)\s*[:=]\s*([^\n]+)", full_text, re.IGNORECASE)
        module = m_mod.group(1).strip() if m_mod else "General"

        m_title = re.search(r"(?:^|\n)\s*(?:Título|Titulo|Title|Caso # \d+:?)\s*[:=]\s*([^\n]+)", full_text, re.IGNORECASE)
        title = m_title.group(1).strip() if m_title else path.stem

        m_obj = re.search(
            r"(?:^|\n)\s*(?:Objetivo(?:\s+de\s+la\s+Prueba)?|Objective)\s*[:=]\s*([^\n]+)",
            full_text,
            re.IGNORECASE,
        )
        objective = m_obj.group(1).strip() if m_obj else ""

        m_url = re.search(r"(?:^|\n)\s*(?:Link|URL)\s*[:=]?\s*(https?://[^\s\n]+)", full_text, re.IGNORECASE)
        url = m_url.group(1).strip() if m_url else None

        m_env = re.search(
            r"(?:^|\n)\s*(?:Ambiente(?:\s+de\s+prueba)?|Environment)\s*[:=]\s*([^\s\n]+)",
            full_text,
            re.IGNORECASE,
        )
        environment = m_env.group(1).strip() if m_env else "QA"

        m_dev = re.search(
            r"(?:^|\n)\s*(?:Analista(?:\s+Programador)?|Developer|Tester)\s*[:=]\s*([^\n]+)",
            full_text,
            re.IGNORECASE,
        )
        developer = m_dev.group(1).strip() if m_dev else "Exelixi QA"

        credentials: dict[str, str] = {}
        m_user = re.search(r"(?:^|\n)\s*(?:Usuario|User|Username)\s*[:=]\s*([^\s\n]+)", full_text, re.IGNORECASE)
        if m_user:
            user_val = m_user.group(1).strip()
            credentials["username"] = user_val
            credentials["usuario"] = user_val

        m_pass = re.search(
            r"(?:^|\n)\s*(?:Clave|Password|Contraseña|Contrasena)\s*[:=]\s*([^\s\n]+)",
            full_text,
            re.IGNORECASE,
        )
        if m_pass:
            pass_val = m_pass.group(1).strip()
            credentials["password"] = pass_val
            credentials["clave"] = pass_val

        # Fallback for case_id
        if not case_id:
            m_id = re.search(r"(R-\d+)", path.name)
            case_id = m_id.group(1) if m_id else "UNKNOWN"

        # Extract steps
        steps = cls._extract_steps(full_text.splitlines())

        return TestCase(
            case_id=case_id,
            module=module,
            title=title,
            objective=objective,
            credentials=credentials,
            steps=steps,
            source_file=str(path),
            environment=environment,
            developer=developer,
            url=url,
        )

    @classmethod
    def _extract_steps(cls, lines: list[str]) -> list[StepDefinition]:
        """Parse step definitions from lines of text."""
        steps: list[StepDefinition] = []

        for line in lines:
            clean = line.replace("\u200e", "").replace("\u200f", "").strip()

            if not clean or NOISE_STEP_PATTERN.match(clean) or clean.lower() == "previous next":
                continue

            # Try PSR pattern
            m_psr = PSR_STEP_PATTERN.match(clean)
            if m_psr:
                step_num = int(m_psr.group(1))
                timestamp = m_psr.group(2).strip() if m_psr.group(2) else None
                action = normalize_psr_action(m_psr.group(3))
                target = m_psr.group(4).strip()
                value = m_psr.group(6).strip() if m_psr.group(6) else None
                steps.append(
                    StepDefinition(
                        step_num=step_num,
                        raw_text=clean,
                        action=action,
                        target=target,
                        value=value,
                        timestamp=timestamp,
                    )
                )
                continue

            # Try standard numbered step pattern
            m_std = STD_STEP_PATTERN.match(clean)
            if m_std:
                step_num = int(m_std.group(1))
                desc = m_std.group(2).strip()
                action, target, value = parse_standard_description(desc)
                steps.append(
                    StepDefinition(
                        step_num=step_num,
                        raw_text=clean,
                        action=action,
                        target=target,
                        value=value,
                        timestamp=None,
                    )
                )

        return steps
