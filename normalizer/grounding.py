"""Grounding checks for normalized test specifications against extracted dump."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from normalizer.schema import Case, NormalizedDoc

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)
ENV_VAR_PATTERN = re.compile(r"^\$\{[A-Z0-9_]+\}$")
CRED_IN_STEP_PATTERN = re.compile(r"\b(?:usuario|clave)\s*:", re.IGNORECASE)
CREDENTIAL_TARGET_PATTERN = re.compile(
    r"(?:clave|contrase[ñn]a|password|pass|pwd|pin|token|secret|credencial|auth)",
    re.IGNORECASE,
)
NARRATIVE_PASSWORD_PATTERN = re.compile(
    r"(?:Clave|Password|Contrase[ñn]a|Pass|Pwd|Pin|Token)(?:\s*[:=]\s*|\s+(?:es\s+|de\s+|))\s*(\S+)",
    re.IGNORECASE,
)

NARRATIVE_STOPWORDS = {
    "acceso",
    "al",
    "campo",
    "con",
    "de",
    "del",
    "el",
    "en",
    "formulario",
    "la",
    "las",
    "los",
    "para",
    "por",
    "portal",
    "seguridad",
    "sistema",
    "un",
    "una",
    "usuario",
}

# Sensitive data patterns
CEDULA_PATTERN = re.compile(r"\b[VEve][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})\b")
RIF_PATTERN = re.compile(r"\b[JGVEjgve][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{8,9})(?:[\s\.-]*\d)?\b")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")


@dataclass
class Violation:
    """Represents a violation found during grounding checks."""

    type: str
    where: str
    message: str


def _extract_dump_strings(dump: dict[str, Any]) -> list[str]:
    """Extract all text fragments from dump structure (paragraphs, meta, links, text)."""
    strings: list[str] = []

    # 1. Paragraphs text
    for p in dump.get("paragraphs", []):
        if isinstance(p, dict) and "text" in p and isinstance(p["text"], str):
            strings.append(p["text"])
        elif isinstance(p, str):
            strings.append(p)

    # 2. Metadata values
    meta = dump.get("meta", {})
    if isinstance(meta, dict):
        for val in meta.values():
            if isinstance(val, str):
                strings.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        strings.append(item)

    # 3. Links list
    for link in dump.get("links", []):
        if isinstance(link, str):
            strings.append(link)

    # 4. Top-level raw text if present
    if "text" in dump and isinstance(dump["text"], str):
        strings.append(dump["text"])

    return strings


def _normalize_ws_case(text: str) -> str:
    """Collapse continuous whitespace and lowercase text while preserving accents."""
    return " ".join(text.lower().split())


def _appears_literal_in_dump(val: str, dump_strings: list[str]) -> bool:
    """Check if the string appears literally as a substring in any dump string."""
    return any(val in s for s in dump_strings)


def _extract_known_passwords(case: Case, dump: dict[str, Any]) -> set[str]:
    """Collect known literal password/credential values from case.credentials and dump metadata."""
    passwords: set[str] = set()

    def _consider_value(k: str, val: Any) -> None:
        if CREDENTIAL_TARGET_PATTERN.search(k):
            if isinstance(val, str) and val.strip() and not ENV_VAR_PATTERN.match(val.strip()):
                passwords.add(val.strip())
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip() and not ENV_VAR_PATTERN.match(item.strip()):
                        passwords.add(item.strip())
            elif isinstance(val, dict):
                for sub_k, sub_val in val.items():
                    _consider_value(str(sub_k), sub_val)

    # 1. From case.credentials
    for k, v in case.credentials.items():
        _consider_value(k, v)

    # 2. From dump meta
    meta = dump.get("meta", {})
    if isinstance(meta, dict):
        for k, v in meta.items():
            _consider_value(k, v)

    # 3. From dump paragraphs
    for p in dump.get("paragraphs", []):
        text = ""
        if isinstance(p, dict):
            text = p.get("text", "")
        elif isinstance(p, str):
            text = p
        if isinstance(text, str) and text:
            for match in NARRATIVE_PASSWORD_PATTERN.finditer(text):
                secret = match.group(1).strip()
                trimmed = secret.rstrip(".,;)")
                clean_secret = secret.strip("\"'")
                clean_trimmed = trimmed.strip("\"'").rstrip(".,;)")
                for candidate in (secret, trimmed, clean_secret, clean_trimmed):
                    cand = candidate.strip("\"'")
                    if (
                        cand
                        and not ENV_VAR_PATTERN.match(cand)
                        and cand.lower() not in NARRATIVE_STOPWORDS
                    ):
                        passwords.add(cand)

    return passwords


def _extract_dump_urls(dump: dict[str, Any], dump_strings: list[str]) -> set[str]:
    """Extract all URLs from dump links and strings, normalized by stripping trailing punctuation and slashes."""
    urls: set[str] = set()
    for link in dump.get("links", []):
        if isinstance(link, str) and link.strip():
            urls.add(link.strip().rstrip("/.,;:)"))
    for s in dump_strings:
        for found in URL_PATTERN.findall(s):
            urls.add(found.strip().rstrip("/.,;:)"))
    return urls


def _is_url_in_dump(url: str, dump_urls: set[str]) -> bool:
    """Check if normalized URL exactly matches any normalized URL in dump."""
    return url.strip().rstrip("/.,;:)") in dump_urls


def _check_sensitive_text(text: str | None, where: str) -> Violation | None:
    """Check if text contains cédulas, RIF, personal emails, or JWT outside ${VAR}."""
    if not text:
        return None

    # Strip environment variable references before checking
    cleaned = re.sub(r"\$\{[A-Z0-9_]+\}", "", text)

    if (
        CEDULA_PATTERN.search(cleaned)
        or RIF_PATTERN.search(cleaned)
        or EMAIL_PATTERN.search(cleaned)
        or JWT_PATTERN.search(cleaned)
    ):
        return Violation(
            type="sensitive_data",
            where=where,
            message="Dato sensible detectado fuera de una variable de entorno",
        )
    return None


def check(normalized: NormalizedDoc | dict[str, Any], dump: dict[str, Any]) -> list[Violation]:
    """Perform grounding checks between normalized document and raw extracted dump."""
    violations: list[Violation] = []

    # Resolve document cases
    if isinstance(normalized, NormalizedDoc):
        cases: list[Case] = normalized.cases
    elif isinstance(normalized, dict):
        raw_cases = normalized.get("cases", [])
        cases = []
        for c in raw_cases:
            if isinstance(c, Case):
                cases.append(c)
            elif isinstance(c, dict):
                cases.append(Case.model_validate(c))
    else:
        cases = []

    dump_strings = _extract_dump_strings(dump)
    dump_urls = _extract_dump_urls(dump, dump_strings)
    # Normalized dump fragments for rule (a) comparison
    normalized_dump_strings = [_normalize_ws_case(s) for s in dump_strings]


    for case in cases:
        case_n = case.n
        known_passwords = _extract_known_passwords(case, dump)

        # --- Regla (f): Check sensitive data in case-level fields ---
        v_title = _check_sensitive_text(case.title, f"Caso {case_n}, title")
        if v_title:
            violations.append(v_title)

        v_obj = _check_sensitive_text(case.objective, f"Caso {case_n}, objective")
        if v_obj:
            violations.append(v_obj)

        if case.url:
            v_url_sens = _check_sensitive_text(case.url, f"Caso {case_n}, url")
            if v_url_sens:
                violations.append(v_url_sens)

        # --- Regla (b): URL exact match check in case.url ---
        if case.url and not _is_url_in_dump(case.url, dump_urls):
            violations.append(
                Violation(
                    type="ungrounded_url",
                    where=f"Caso {case_n}, url",
                    message="URL no encontrada de forma literal en el documento original",
                )
            )

        # --- Regla (d): Case.credentials must be strictly ${VAR} format ---
        # --- Regla (f): Also check credentials keys/values for sensitive data ---
        for cred_key, cred_val in case.credentials.items():
            where_cred = f"Caso {case_n}, credentials[{cred_key}]"
            if not ENV_VAR_PATTERN.match(cred_val):
                violations.append(
                    Violation(
                        type="invalid_credential_format",
                        where=where_cred,
                        message="Credencial debe ser una referencia de entorno ${VAR}",
                    )
                )

            v_cred_sens = _check_sensitive_text(cred_val, where_cred)
            if v_cred_sens:
                violations.append(v_cred_sens)

        # Iterate steps
        for step_idx, step in enumerate(case.steps, start=1):
            where_step = f"Caso {case_n}, paso {step_idx}"

            # --- Regla (a): source_quote must have >= 8 chars, >= 2 words, and be substring in dump ---
            raw_quote = step.source_quote if isinstance(step.source_quote, str) else ""
            words = raw_quote.strip().split()
            if len(raw_quote.strip()) < 8 or len(words) < 2:
                violations.append(
                    Violation(
                        type="invalid_source_quote_length",
                        where=where_step,
                        message="source_quote debe tener al menos 8 caracteres y al menos 2 palabras",
                    )
                )
            else:
                quote_norm = _normalize_ws_case(raw_quote)
                if not quote_norm or not any(quote_norm in s for s in normalized_dump_strings):
                    violations.append(
                        Violation(
                            type="ungrounded_quote",
                            where=where_step,
                            message="source_quote no se encuentra en el texto original del documento",
                        )
                    )

            # --- Regla (b): Check URLs in steps ---
            if step.action == "navigate":
                target_clean = step.target.strip()
                if not (URL_PATTERN.fullmatch(target_clean) and _is_url_in_dump(target_clean, dump_urls)):
                    violations.append(
                        Violation(
                            type="ungrounded_url",
                            where=where_step,
                            message="URL del paso no encontrada en el documento original",
                        )
                    )
            else:
                for u in URL_PATTERN.findall(step.target):
                    if not _is_url_in_dump(u, dump_urls):
                        violations.append(
                            Violation(
                                type="ungrounded_url",
                                where=where_step,
                                message="URL del paso no encontrada en el documento original",
                            )
                        )

            if step.value:
                for u in URL_PATTERN.findall(step.value):
                    if not _is_url_in_dump(u, dump_urls):
                        violations.append(
                            Violation(
                                type="ungrounded_url",
                                where=where_step,
                                message="URL del paso no encontrada en el documento original",
                            )
                        )

            # --- Regla (c): fill value must appear literal in dump or match ${VAR} ---
            if step.action == "fill" and step.value is not None:
                step_val_clean = step.value.strip()
                step_val_unquoted = step_val_clean.strip("\"'")
                is_env_var = bool(ENV_VAR_PATTERN.match(step.value))
                is_cred_target = bool(CREDENTIAL_TARGET_PATTERN.search(step.target))
                is_known_password = (not is_env_var) and (
                    step_val_clean in known_passwords or step_val_unquoted in known_passwords
                )

                if is_cred_target or is_known_password:
                    if not is_env_var:
                        violations.append(
                            Violation(
                                type="literal_credential_in_fill",
                                where=where_step,
                                message="El valor para un campo de credencial en fill debe ser una variable de entorno ${VAR}",
                            )
                        )
                elif not is_env_var and not _appears_literal_in_dump(step.value, dump_strings):
                    violations.append(
                        Violation(
                            type="ungrounded_fill_value",
                            where=where_step,
                            message="Valor de fill no encontrado en texto original ni es variable de entorno",
                        )
                    )

            # --- Regla (e): No 'Usuario:' nor 'Clave:' in target or value ---
            if CRED_IN_STEP_PATTERN.search(step.target):
                violations.append(
                    Violation(
                        type="credentials_in_step",
                        where=where_step,
                        message="El paso no debe contener 'Usuario:' ni 'Clave:' en target",
                    )
                )
            elif step.value and CRED_IN_STEP_PATTERN.search(step.value):
                violations.append(
                    Violation(
                        type="credentials_in_step",
                        where=where_step,
                        message="El paso no debe contener 'Usuario:' ni 'Clave:' en value",
                    )
                )

            # --- Regla (f): Check sensitive data in step target and value ---
            v_step_target = _check_sensitive_text(step.target, f"{where_step}, target")
            if v_step_target:
                violations.append(v_step_target)

            if step.value:
                v_step_val = _check_sensitive_text(step.value, f"{where_step}, value")
                if v_step_val:
                    violations.append(v_step_val)

    return violations
