"""Unified deterministic masking of sensitive data (PII and secrets) for providers and grounding."""

from __future__ import annotations

import copy
import re
from typing import Any

ENV_VAR_PATTERN = re.compile(r"^\$\{[A-Z0-9_]+\}$")

CREDENTIAL_KEY_PATTERN = re.compile(
    r"(?:clave|contrase[ñn]a|password|pass|pwd|pin|token|secret|credencial|auth)",
    re.IGNORECASE,
)

NARRATIVE_PASSWORD_PATTERN = re.compile(
    r"(?i)\b(?:clave|password|contrase[ñn]a|pass|pwd|pin|token)(?:\s*[:=]\s*|\s+(?:es\s+|de\s+|))\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))"
)

JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")

# Venezuelan RIF: J-12345678-0, G-20000123-4, V-12345678-9, etc.
RIF_PATTERN = re.compile(
    r"\b(?:[JGjg][\s\.-]*\d{1,3}(?:[.\s]\d{3}){1,3}(?:[\s\.-]*\d)?|[JGjg][\s\.-]*\d{8,9}(?:[\s\.-]*\d)?|[VEve][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})[\s\.-]+\d)\b"
)

# Venezuelan Cédula without check digit: V-12.345.678, V-12345678, E-12345678
CEDULA_PATTERN = re.compile(r"\b[VEve][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})\b")

EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")

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
    "user",
    "admin",
}


class MaskMapping(dict):
    """Bidirectional dictionary mapping markers to original values and vice versa."""

    def __init__(self, forward: dict[str, str]) -> None:
        super().__init__(forward)
        self._reverse = {v: k for k, v in forward.items()}

    def __getitem__(self, key: str) -> str:
        if key in self._reverse:
            return self._reverse[key]
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or key in self._reverse

    def get(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        return default


def _collect_texts_in_order(dump: dict[str, Any]) -> list[str]:
    """Collect all strings from dump in deterministic order."""
    texts: list[str] = []

    # 1. Metadata values in sorted key order
    meta = dump.get("meta", {})
    if isinstance(meta, dict):
        for k in sorted(meta.keys()):
            val = meta[k]
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        texts.append(item)

    # 2. Paragraphs in line order
    for p in dump.get("paragraphs", []):
        if isinstance(p, dict) and "text" in p and isinstance(p["text"], str):
            texts.append(p["text"])
        elif isinstance(p, str):
            texts.append(p)

    # 3. Links
    for link in dump.get("links", []):
        if isinstance(link, str):
            texts.append(link)

    # 4. Cases titles
    for c in dump.get("cases", []):
        if isinstance(c, dict) and "title" in c and isinstance(c["title"], str):
            texts.append(c["title"])

    # 5. Top-level text if present
    if "text" in dump and isinstance(dump["text"], str):
        texts.append(dump["text"])

    return texts


def mask_dump_for_provider(dump: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Mask credentials, cédulas, emails, RIF, and JWT into deterministic sequential markers.

    Returns:
        tuple of (masked_dump, mask_mapping)
        where masked_dump is safe for API transmission and grounding checks,
        and mask_mapping maps marker -> original_value (and original_value -> marker).
    """
    masked = copy.deepcopy(dump)
    texts = _collect_texts_in_order(masked)

    # Track discovered secrets in deterministic order
    passwords: list[str] = []
    jwts: list[str] = []
    rifs: list[str] = []
    cedulas: list[str] = []
    emails: list[str] = []

    # 1. Discovered passwords from meta
    meta = masked.get("meta", {})
    if isinstance(meta, dict):
        for k in sorted(meta.keys()):
            if CREDENTIAL_KEY_PATTERN.search(k):
                v = meta[k]
                if isinstance(v, str):
                    clean_v = v.strip().strip("\"'").rstrip(".,;)")
                    if clean_v and not ENV_VAR_PATTERN.match(clean_v) and clean_v not in passwords:
                        passwords.append(clean_v)

    # 2. Scan collected texts in order
    for text in texts:
        # Passwords in narrative
        for m in NARRATIVE_PASSWORD_PATTERN.finditer(text):
            candidate = m.group(1) or m.group(2) or m.group(3) or ""
            clean_cand = candidate.strip().strip("\"'").rstrip(".,;)")
            if (
                clean_cand
                and not ENV_VAR_PATTERN.match(clean_cand)
                and clean_cand.lower() not in NARRATIVE_STOPWORDS
                and clean_cand not in passwords
            ):
                passwords.append(clean_cand)

        # JWTs
        for m in JWT_PATTERN.finditer(text):
            jwt_val = m.group(0).strip()
            if jwt_val and jwt_val not in jwts:
                jwts.append(jwt_val)

        # RIFs
        for m in RIF_PATTERN.finditer(text):
            rif_val = m.group(0).strip()
            if rif_val and rif_val not in rifs:
                rifs.append(rif_val)

        # Cédulas (check that it wasn't already caught as RIF)
        for m in CEDULA_PATTERN.finditer(text):
            ced_val = m.group(0).strip()
            if (
                ced_val
                and ced_val not in cedulas
                and not any(ced_val in r for r in rifs)
            ):
                cedulas.append(ced_val)

        # Emails
        for m in EMAIL_PATTERN.finditer(text):
            email_val = m.group(0).strip()
            if email_val and email_val not in emails:
                emails.append(email_val)

    # Build deterministic marker assignments
    forward_mapping: dict[str, str] = {}
    replacements: list[tuple[str, str]] = []

    for idx, pwd in enumerate(passwords, start=1):
        marker = f"[PASS_{idx}]"
        forward_mapping[marker] = pwd
        replacements.append((pwd, marker))

    for idx, token in enumerate(jwts, start=1):
        marker = f"[JWT_{idx}]"
        forward_mapping[marker] = token
        replacements.append((token, marker))

    for idx, rif in enumerate(rifs, start=1):
        marker = f"[RIF_{idx}]"
        forward_mapping[marker] = rif
        replacements.append((rif, marker))

    for idx, ced in enumerate(cedulas, start=1):
        marker = f"[CEDULA_{idx}]"
        forward_mapping[marker] = ced
        replacements.append((ced, marker))

    for idx, em in enumerate(emails, start=1):
        marker = f"[EMAIL_{idx}]"
        forward_mapping[marker] = em
        replacements.append((em, marker))

    # Sort replacements by length descending to prevent partial match collisions
    replacements.sort(key=lambda item: len(item[0]), reverse=True)

    def _replace_in_string(val: str) -> str:
        res = val
        for orig, marker in replacements:
            if orig in res:
                res = res.replace(orig, marker)
        return res

    def _apply_replacements(obj: Any) -> Any:
        if isinstance(obj, str):
            return _replace_in_string(obj)
        if isinstance(obj, list):
            return [_apply_replacements(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _apply_replacements(v) for k, v in obj.items()}
        return obj

    masked_dump = _apply_replacements(masked)
    return masked_dump, MaskMapping(forward_mapping)
