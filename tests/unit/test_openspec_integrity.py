"""Unit tests for OpenSpec directory structure, canonical specs, and verification reports integrity.

Validates:
1. Verification reports in unarchived/completed changes adhere to required section headers.
2. Canonical specifications in openspec/specs/ adhere to Markdown headings and RFC 2119 keywords.
3. Archived change directories follow ISO date prefix convention (YYYY-MM-DD-<change-name>).
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPENSPEC_DIR = REPO_ROOT / "openspec"
CHANGES_DIR = OPENSPEC_DIR / "changes"
SPECS_DIR = OPENSPEC_DIR / "specs"
ARCHIVE_DIR = CHANGES_DIR / "archive"

REQUIRED_VERIFY_HEADINGS = [
    "## Verification Summary",
    "## Test Evidence",
    "## Quality Gates",
    "## Conclusion",
]

COMPLETED_CHANGES = [
    "vertical-slice-automation",
    "doc-driven-testing",
    "ai-test-normalizer",
    "unified-runner-reporting",
    "static-type-checking-gate",
]

CANONICAL_SPEC_NAMES = [
    "page-object-architecture",
    "doc-runner-engine",
    "canonical-test-format",
    "allure-runner-reporting",
    "static-type-checking-gate",
]

RFC_2119_KEYWORDS = ["MUST", "SHALL", "SHOULD"]

ARCHIVE_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")


REQUIRED_SECTION_PATTERNS = {
    "Summary": re.compile(r"^##\s+.*Summary", re.MULTILINE | re.IGNORECASE),
    "Evidence": re.compile(r"^##\s+.*Evidence", re.MULTILINE | re.IGNORECASE),
    "Quality": re.compile(r"^##\s+.*Quality", re.MULTILINE | re.IGNORECASE),
    "Conclusion/Verdict": re.compile(r"^##\s+.*(Verdict|Conclusion)", re.MULTILINE | re.IGNORECASE),
}

def validate_verify_report_content(content: str) -> tuple[bool, list[str]]:
    """Validate that verify report content includes all required conceptual sections."""
    missing = [name for name, pattern in REQUIRED_SECTION_PATTERNS.items() if not pattern.search(content)]
    return (len(missing) == 0, missing)


def validate_canonical_spec_content(content: str) -> tuple[bool, list[str]]:
    """Validate canonical spec heading structure and RFC 2119 keyword presence."""
    errors: list[str] = []
    if not re.search(r"^#\s+Specification:\s+.+", content, re.MULTILINE):
        errors.append("Missing '# Specification: <Title>' top-level header")
    if not re.search(r"^##\s+Overview\b", content, re.MULTILINE):
        errors.append("Missing '## Overview' section header")
    if not re.search(r"^##\s+Requirements\b", content, re.MULTILINE):
        errors.append("Missing '## Requirements' section header")

    found_keywords = [kw for kw in RFC_2119_KEYWORDS if re.search(rf"\b{kw}\b", content)]
    if not found_keywords:
        errors.append(f"No RFC 2119 keywords ({', '.join(RFC_2119_KEYWORDS)}) found in requirements")

    return (len(errors) == 0, errors)


def validate_archive_folder_name(folder_name: str) -> bool:
    """Validate that an archive folder name matches ISO date prefixed naming format."""
    return bool(ARCHIVE_FOLDER_PATTERN.match(folder_name))


# ---------------------------------------------------------------------------
# Test Verification Reports
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_verify_reports_exist_and_valid_positive():
    """Verify that all target completed changes contain a valid verify-report.md (active or archived)."""
    for change_name in COMPLETED_CHANGES:
        active_path = CHANGES_DIR / change_name / "verify-report.md"
        matching_archived = list(ARCHIVE_DIR.glob(f"*{change_name}/verify-report.md"))
        report_path = active_path if active_path.exists() else (matching_archived[0] if matching_archived else None)
        assert report_path is not None and report_path.exists(), f"Missing verify-report.md in {change_name}"
        content = report_path.read_text(encoding="utf-8")
        is_valid, missing = validate_verify_report_content(content)
        assert is_valid, f"{report_path} missing required headings: {missing}"


def test_verify_report_validation_fails_on_missing_headings_negative():
    """Verify that validator detects missing required headings in report markdown."""
    incomplete_content = """# Verification Report
## Verification Summary
Some summary.
## Test Evidence
Evidence details.
"""
    is_valid, missing = validate_verify_report_content(incomplete_content)
    assert not is_valid
    assert "Quality" in missing
    assert "Conclusion/Verdict" in missing


# ---------------------------------------------------------------------------
# Test Canonical Specifications
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_canonical_specs_exist_and_valid_positive():
    """Verify that all 5 canonical specifications exist under openspec/specs/ with required format."""
    for spec_name in CANONICAL_SPEC_NAMES:
        spec_path = SPECS_DIR / spec_name / "spec.md"
        assert spec_path.exists(), f"Missing canonical specification: {spec_path}"
        content = spec_path.read_text(encoding="utf-8")
        is_valid, errors = validate_canonical_spec_content(content)
        assert is_valid, f"Canonical spec {spec_name} failed validation: {errors}"


def test_canonical_spec_validation_fails_on_invalid_markdown_negative():
    """Verify that validator rejects specs missing required headers or RFC 2119 keywords."""
    invalid_spec = """# Some Document
This is just notes without proper specification structure.
"""
    is_valid, errors = validate_canonical_spec_content(invalid_spec)
    assert not is_valid
    assert any("Missing '# Specification:" in err for err in errors)
    assert any("Missing '## Overview'" in err for err in errors)
    assert any("Missing '## Requirements'" in err for err in errors)
    assert any("No RFC 2119 keywords" in err for err in errors)


# ---------------------------------------------------------------------------
# Test Archive Directory Structure
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_archive_directory_structure_positive():
    """Verify that any directories in openspec/changes/archive follow ISO date prefix format."""
    assert ARCHIVE_DIR.exists(), f"Archive directory does not exist: {ARCHIVE_DIR}"

    valid_sample_names = [
        "2026-10-12-vertical-slice-automation",
        "2026-10-12-doc-driven-testing",
        "2026-10-30-ai-test-normalizer",
        "2026-10-30-unified-runner-reporting",
        "2026-10-30-static-type-checking-gate",
    ]
    for name in valid_sample_names:
        assert validate_archive_folder_name(name), f"Expected valid name: {name}"

    # Also check actual existing subdirectories (ignoring hidden files like .gitkeep)
    for entry in ARCHIVE_DIR.iterdir():
        if entry.is_dir():
            assert validate_archive_folder_name(entry.name), (
                f"Archived directory '{entry.name}' does not follow ISO date prefix pattern "
                "YYYY-MM-DD-<change-name>"
            )

    # All 5 completed changes must be archived under ARCHIVE_DIR
    for change_name in COMPLETED_CHANGES:
        matches = [d for d in ARCHIVE_DIR.iterdir() if d.is_dir() and d.name.endswith(f"-{change_name}")]
        assert len(matches) == 1, f"Expected change '{change_name}' to be archived under {ARCHIVE_DIR}"


def test_archive_directory_structure_rejects_invalid_names_negative():
    """Verify that invalid folder naming patterns are rejected by the validator."""
    invalid_names = [
        "vertical-slice-automation",
        "2026_10_12_doc_driven_testing",
        "10-12-2026-bad-date-order",
        "2026-1-1-short-date",
        "2026-10-12-INVALID_UPPERCASE",
    ]
    for name in invalid_names:
        assert not validate_archive_folder_name(name), f"Expected invalid name to fail: {name}"
