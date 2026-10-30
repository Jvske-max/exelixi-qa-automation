"""Rule-based gap detection and case state determination for free-form QA tests.

Note:
    The gap type 'ambiguous_step' is detected analytically by the `test-normalizer`
    agent during semantic interpretation of test narratives, not programmatically
    by detect_gaps().
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES_PATH = Path(__file__).parent / "rules.yaml"

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)
USER_PATTERN = re.compile(
    r"(?:(?:Usuario|User|Username)\s*[:=]\s*\S+|\$\{QA_USER[^\}]*\}|(?:(?:con\s+el\s+)?usuario|user)\s+\S+)",
    re.IGNORECASE,
)
PASS_PATTERN = re.compile(r"(?:Clave|Password|Contraseña|Contrasena)\s*:\s*(\S+)", re.IGNORECASE)


@dataclass
class Gap:
    """Represents an identified defect or ambiguity in the test specification."""

    type: str  # missing_url, missing_credentials, credentials_in_plaintext, missing_expected, ambiguous_step, data_in_screenshot, unsupported_flow
    severity: str  # blocking, warning, info
    where: str  # e.g., "Caso 2, línea 7" or "Cabecera"
    ask: str  # Spanish guidance explaining how to resolve the gap


def _load_rules(rules_path: Path | None = None) -> dict[str, list[str]]:
    """Load and normalize rule keywords from YAML configuration."""
    target_path = rules_path or DEFAULT_RULES_PATH
    if not target_path.exists():
        return {
            "login_phrases": ["iniciamos sesión", "iniciar sesión", "ingresar al sistema", "login"],
            "verification_phrases": ["se muestra correctamente", "funciona correctamente", "se visualiza correctamente"],
            "screenshot_data_phrases": ["con la siguiente información", "con los siguientes datos", "como se muestra en la captura"],
            "unsupported_flows": ["otp", "pago móvil", "pago movil", "pasarela", "correo", "sisip", "subir archivo", "descarga"],
        }

    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return {
        "login_phrases": [str(p).strip().lower() for p in data.get("login_phrases", [])],
        "verification_phrases": [str(p).strip().lower() for p in data.get("verification_phrases", [])],
        "screenshot_data_phrases": [str(p).strip().lower() for p in data.get("screenshot_data_phrases", [])],
        "unsupported_flows": [str(p).strip().lower() for p in data.get("unsupported_flows", [])],
    }


def _find_case_for_line(line: int, cases: list[dict[str, Any]]) -> int | None:
    """Find the case number corresponding to a specific paragraph line."""
    for c in cases:
        if c.get("start_line", 0) <= line <= c.get("end_line", 0):
            return c.get("n")
    return cases[0].get("n") if cases else None


def detect_gaps(dump: dict[str, Any], rules_path: Path | None = None) -> list[Gap]:
    """Scan extracted document content and identify all canonical specification gaps.

    Note:
        The gap type 'ambiguous_step' is detected analytically by the `test-normalizer`
        agent during test normalization, rather than programmatically by this function.
    """
    rules = _load_rules(rules_path)
    gaps: list[Gap] = []

    meta = dump.get("meta", {})
    paragraphs = dump.get("paragraphs", [])
    cases = dump.get("cases", [])
    links = dump.get("links", [])

    # 1. URL check: If global links exist in header/meta, no missing_url gap
    has_global_link = False
    for val in meta.values():
        if isinstance(val, str) and URL_PATTERN.search(val):
            has_global_link = True
            break

    # For single-case documents, links array also serves as global/case URL
    if not has_global_link and len(cases) <= 1 and bool(links):
        has_global_link = True

    if not has_global_link:
        if cases:
            for case in cases:
                n = case.get("n", 1)
                start_l = case.get("start_line", 0)
                end_l = case.get("end_line", 0)
                # For case 1, include paragraphs before start_line (such as leading Link: ...)
                if n == 1:
                    case_paragraphs = [
                        p for p in paragraphs
                        if p.get("line", 0) <= end_l
                    ]
                else:
                    case_paragraphs = [
                        p for p in paragraphs
                        if start_l <= p.get("line", 0) <= end_l
                    ]
                case_has_link = any(URL_PATTERN.search(p.get("text", "")) for p in case_paragraphs)
                if not case_has_link:
                    gaps.append(
                        Gap(
                            type="missing_url",
                            severity="blocking",
                            where=f"Caso {n}",
                            ask=f"Añadir Link: https://... en el caso {n}",
                        )
                    )
        else:
            gaps.append(
                Gap(
                    type="missing_url",
                    severity="blocking",
                    where="Cabecera",
                    ask="Añadir Link: https://... en la cabecera",
                )
            )

    # 2. Per-case login and credentials check
    if cases:
        for case in cases:
            case_paragraphs = [
                p for p in paragraphs
                if case.get("start_line", 0) <= p.get("line", 0) <= case.get("end_line", 0)
            ]
            has_login = False
            login_line = case.get("start_line", 1)
            for p in case_paragraphs:
                text_lower = p.get("text", "").lower()
                if any(phrase in text_lower for phrase in rules["login_phrases"]):
                    has_login = True
                    login_line = p.get("line", login_line)
                    break

            if has_login:
                has_user = any(USER_PATTERN.search(p.get("text", "")) for p in case_paragraphs)
                if not has_user:
                    # Check metadata as fallback
                    for k in meta:
                        if "usuario" in k or "user" in k:
                            has_user = True
                            break

                if not has_user:
                    n = case.get("n", 1)
                    gaps.append(
                        Gap(
                            type="missing_credentials",
                            severity="blocking",
                            where=f"Caso {n}, línea {login_line}",
                            ask="Indicar el usuario de prueba; la clave va en .env como QA_PASS_<ROL>",
                        )
                    )

    # 3. Plaintext password check, missing expected, screenshot data, unsupported flows
    for idx, p in enumerate(paragraphs):
        text = p.get("text", "")
        line = p.get("line", idx + 1)
        case_n = _find_case_for_line(line, cases)
        where_desc = f"Caso {case_n}, línea {line}" if case_n is not None else f"Línea {line}"

        # Plaintext password check
        m_pass = PASS_PATTERN.search(text)
        if m_pass:
            secret = m_pass.group(1).strip()
            # If not parameterized variable like ${QA_PASS_...}
            if not (secret.startswith("${") and secret.endswith("}")):
                gaps.append(
                    Gap(
                        type="credentials_in_plaintext",
                        severity="warning",
                        where=where_desc,
                        ask="Cambiar esa clave y moverla a .env como QA_PASS_<ROL>",
                    )
                )

        # Missing expected verification check (bare verification phrase without explicit outcome)
        clean_text = re.sub(
            r"^(?:paso\s*\d*[:.]?\s*|verificar[:.]?\s*|\d+[:.]?\s*)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip().rstrip(".").strip().lower()

        clean_phrase = re.sub(
            r"^(?:el\s+sistema|el\s+portal|la\s+p[aá]gina|la\s+aplicaci[oó]n)\s+",
            "",
            clean_text,
        )

        if clean_text in rules["verification_phrases"] or clean_phrase in rules["verification_phrases"]:
            gaps.append(
                Gap(
                    type="missing_expected",
                    severity="warning",
                    where=where_desc,
                    ask="Escribir qué texto o estado se espera",
                )
            )

        # Screenshot data phrase check
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in rules["screenshot_data_phrases"]):
            has_images = bool(p.get("images"))
            if not has_images and idx + 1 < len(paragraphs):
                # Check if next paragraph has images
                next_p = paragraphs[idx + 1]
                if bool(next_p.get("images")):
                    has_images = True

            if has_images:
                gaps.append(
                    Gap(
                        type="data_in_screenshot",
                        severity="warning",
                        where=where_desc,
                        ask="Escribir el dato de prueba (ficticio) en texto",
                    )
                )

        # Unsupported flows check
        for phrase in rules["unsupported_flows"]:
            pattern = rf"(?:\b|_){re.escape(phrase)}(?:\b|_)"
            if re.search(pattern, text_lower):
                gaps.append(
                    Gap(
                        type="unsupported_flow",
                        severity="info",
                        where=where_desc,
                        ask="Flujo no soportado; el paso queda como pendiente manual",
                    )
                )
                break

    return gaps


def determine_state(gaps: list[Gap], total_steps_or_cases: int = 1) -> str:
    """Determine the normalization state: READY, NEEDS_INFO, or UNSUPPORTED."""
    if any(g.severity == "blocking" for g in gaps):
        return "NEEDS_INFO"

    unsupported_count = sum(1 for g in gaps if g.type == "unsupported_flow")
    if total_steps_or_cases > 0 and unsupported_count >= total_steps_or_cases:
        return "UNSUPPORTED"
    if total_steps_or_cases <= 0:
        return "UNSUPPORTED"

    return "READY"
