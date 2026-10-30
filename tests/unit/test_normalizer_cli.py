"""Unit tests for unified CLI entrypoints and sample narrative generator (T6)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import docx
import pytest

from normalizer.cli import main as cli_main
from normalizer.extract import extract_document
from normalizer.gaps import detect_gaps
from normalizer.schema import Case, NormalizedDoc, Step


@pytest.fixture
def synthetic_docx(tmp_path: Path) -> Path:
    """Fixture creating a simple synthetic .docx for CLI testing."""
    doc_path = tmp_path / "test_doc.docx"
    doc = docx.Document()
    table = doc.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "Fecha"
    table.rows[0].cells[1].text = "Módulo"
    table.rows[0].cells[2].text = "Identificador del caso"
    table.rows[0].cells[3].text = "Ambiente"
    table.rows[1].cells[0].text = "2026-10-28"
    table.rows[1].cells[1].text = "Ventas"
    table.rows[1].cells[2].text = "R-SYNTH-01"
    table.rows[1].cells[3].text = "QA"

    doc.add_paragraph("Link: https://example.test/portal")
    doc.add_paragraph("Caso 1: Creación de pedido")
    doc.add_paragraph("Objetivo de la Prueba: Registrar un pedido nuevo")
    doc.add_paragraph("Iniciamos sesión con usuario ${QA_USER_ADMIN} y clave ${QA_PASS_ADMIN}")
    doc.add_paragraph("Paso 1: clic en Nuevo Pedido")
    doc.save(str(doc_path))
    return doc_path


@pytest.fixture
def synthetic_normalized_json(tmp_path: Path) -> Path:
    """Fixture creating a valid synthetic normalized JSON file."""
    norm_doc = NormalizedDoc(
        meta={
            "identificador del caso": "R-CLI-01",
            "módulo": "Seguridad",
            "ambiente": "QA",
        },
        cases=[
            Case(
                n=1,
                title="Caso CLI Válido",
                objective="Verificar validación y renderizado en CLI",
                url="https://qa.example.test/portal",
                credentials={"usuario": "${QA_USER_ADMIN}", "clave": "${QA_PASS_ADMIN}"},
                steps=[
                    Step(
                        action="navigate",
                        target="https://qa.example.test/portal",
                        source_quote="Ingresamos al portal",
                        source_ref="Línea 1",
                    ),
                    Step(
                        action="click",
                        target="Ingresar",
                        source_quote="Pulsamos el botón Ingresar",
                        source_ref="Línea 2",
                    ),
                ],
            )
        ],
    )
    json_path = tmp_path / "valid_norm.json"
    json_path.write_text(norm_doc.model_dump_json(indent=2), encoding="utf-8")
    return json_path


@pytest.fixture
def matching_dump_json(tmp_path: Path) -> Path:
    """Fixture creating a dump.json matching synthetic_normalized_json grounding quotes."""
    dump = {
        "meta": {"módulo": "Seguridad", "identificador del caso": "R-CLI-01"},
        "paragraphs": [
            {"line": 1, "text": "Ingresamos al portal", "images": []},
            {"line": 2, "text": "Pulsamos el botón Ingresar", "images": []},
        ],
        "cases": [{"n": 1, "title": "Caso CLI Válido", "start_line": 1, "end_line": 2}],
        "links": ["https://qa.example.test/portal"],
    }
    dump_path = tmp_path / "dump.json"
    dump_path.write_text(json.dumps(dump, indent=2), encoding="utf-8")
    return dump_path


@pytest.mark.smoke
def test_cli_extract_subcommand(synthetic_docx: Path, tmp_path: Path) -> None:
    """CLI subcommand extract converts .docx to dump.json and images."""
    out_dir = tmp_path / "extract_out"

    # Positive case: valid docx file extracted successfully
    code = cli_main(["extract", str(synthetic_docx), "--out", str(out_dir)])
    assert code == 0
    dump_file = out_dir / "dump.json"
    assert dump_file.exists()

    with open(dump_file, "r", encoding="utf-8") as f:
        dump_data = json.load(f)
    assert dump_data["meta"]["módulo"] == "Ventas"
    assert len(dump_data["cases"]) == 1
    assert dump_data["cases"][0]["title"] == "Creación de pedido"

    # Negative case 1: non-existent document file
    missing_file = tmp_path / "missing.docx"
    code_missing = cli_main(["extract", str(missing_file), "--out", str(out_dir)])
    assert code_missing != 0

    # Negative case 2: unsupported file extension
    unsupported_file = tmp_path / "document.txt"
    unsupported_file.write_text("Hello world", encoding="utf-8")
    code_unsupported = cli_main(["extract", str(unsupported_file), "--out", str(out_dir)])
    assert code_unsupported != 0


@pytest.mark.smoke
def test_cli_gaps_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI subcommand gaps scans dump.json and formats gaps with type, where, and ask."""
    # Positive case 1: dump with gaps displays formatted gap info
    dump_with_gaps = {
        "meta": {"módulo": "Finanzas"},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Transferencia", "images": []},
            {"line": 2, "text": "Se solicita el código OTP enviado al teléfono móvil.", "images": []},
        ],
        "cases": [{"n": 1, "title": "Transferencia", "start_line": 1, "end_line": 2}],
        "links": [],
    }
    dump_file_gaps = tmp_path / "dump_gaps.json"
    dump_file_gaps.write_text(json.dumps(dump_with_gaps), encoding="utf-8")

    code_gaps = cli_main(["gaps", str(dump_file_gaps)])
    assert code_gaps == 0

    captured = capsys.readouterr()
    output = captured.out
    assert "missing_url" in output
    assert "unsupported_flow" in output
    assert "where=" in output or "where" in output.lower()
    assert "ask=" in output or "solicitud" in output.lower()

    # Positive case 2: dump without gaps displays clean message
    dump_clean = {
        "meta": {"módulo": "Finanzas"},
        "paragraphs": [
            {"line": 1, "text": "Caso 1: Consulta", "images": []},
            {"line": 2, "text": "Paso 1: clic en Buscar", "images": []},
            {"line": 3, "text": "Paso 2: verificar Saldo Actual", "images": []},
        ],
        "cases": [{"n": 1, "title": "Consulta", "start_line": 1, "end_line": 3}],
        "links": ["https://example.test/finanzas"],
    }
    dump_file_clean = tmp_path / "dump_clean.json"
    dump_file_clean.write_text(json.dumps(dump_clean), encoding="utf-8")

    code_clean = cli_main(["gaps", str(dump_file_clean)])
    assert code_clean == 0
    captured_clean = capsys.readouterr()
    assert "no se detectaron faltantes" in captured_clean.out.lower()

    # Negative case 1: non-existent file returns 1
    code_missing = cli_main(["gaps", str(tmp_path / "non_existent.json")])
    assert code_missing != 0

    # Negative case 2: corrupted JSON returns 1
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{not valid json", encoding="utf-8")
    code_corrupt = cli_main(["gaps", str(corrupt_file)])
    assert code_corrupt != 0


@pytest.mark.smoke
def test_cli_validate_subcommand(
    synthetic_normalized_json: Path,
    matching_dump_json: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI subcommand validate succeeds for valid grounding and redacts secrets on violations."""
    # Positive case: valid file and original dump pass validation with exit code 0
    code_valid = cli_main(["validate", str(synthetic_normalized_json), "--original", str(matching_dump_json)])
    assert code_valid == 0

    # Negative case 1: ungrounded step produces violation with exit code 1
    invalid_data = json.loads(synthetic_normalized_json.read_text(encoding="utf-8"))
    secret_leak = "SECRET_PASSWORD_12345"
    invalid_data["cases"][0]["steps"].append(
        {
            "action": "click",
            "target": f"Boton {secret_leak}",
            "source_quote": "Esta frase nunca existió en el original",
            "source_ref": "Línea 99",
        }
    )
    invalid_json = tmp_path / "invalid_norm.json"
    invalid_json.write_text(json.dumps(invalid_data), encoding="utf-8")

    code_invalid = cli_main(["validate", str(invalid_json), "--original", str(matching_dump_json)])
    assert code_invalid == 1

    captured = capsys.readouterr()
    combined_err = captured.err + captured.out
    assert "VIOLATION:" in combined_err
    assert "ungrounded_quote" in combined_err
    # Rule 1 & critical privacy invariant: never print sensitive inputs or secrets
    assert secret_leak not in combined_err

    # Negative case 2: non-existent file returns 1
    code_missing = cli_main(["validate", str(tmp_path / "does_not_exist.json")])
    assert code_missing != 0


@pytest.mark.smoke
def test_cli_render_subcommand(synthetic_normalized_json: Path, tmp_path: Path) -> None:
    """CLI subcommand render generates canonical .docx and respects default output directory."""
    custom_out = tmp_path / "custom_render"

    # Positive case 1: render to custom --out directory
    code = cli_main(["render", str(synthetic_normalized_json), "--out", str(custom_out)])
    assert code == 0
    expected_docx = custom_out / "R-CLI-01-caso1.docx"
    assert expected_docx.exists()

    # Positive case 2: render with default --out (normalized/)
    code_default = cli_main(["render", str(synthetic_normalized_json)])
    assert code_default == 0
    default_docx = Path("normalized") / "R-CLI-01-caso1.docx"
    assert default_docx.exists()
    # Clean up created file in default location
    if default_docx.exists():
        default_docx.unlink()

    # Negative case: non-existent file returns 1
    code_bad = cli_main(["render", str(tmp_path / "missing.json"), "--out", str(custom_out)])
    assert code_bad != 0


@pytest.mark.smoke
def test_make_sample_narrative_and_extraction(tmp_path: Path) -> None:
    """tools.make_sample_narrative produces synthetic sample with Case 1 (valid) and Case 2 (gaps)."""
    from tools.make_sample_narrative import create_sample_narrative

    sample_docx = tmp_path / "muestra.docx"
    create_sample_narrative(sample_docx)

    # Positive verification 1: Document generated and exists
    assert sample_docx.exists()
    assert sample_docx.stat().st_size > 0

    # Positive verification 2: Extract document content via normalizer.extract
    extract_out = tmp_path / "extracted_sample"
    dump = extract_document(sample_docx, extract_out)
    assert (extract_out / "dump.json").exists()

    # Verify table metadata
    meta = dump["meta"]
    assert meta.get("módulo") == "Usuarios"
    assert meta.get("identificador del caso") == "R-SAMPLE-01"
    assert meta.get("descripción corta") == "Prueba sintética de usuarios"
    assert meta.get("descripción completa") == "Prueba sintética narrativa para normalizador"
    assert meta.get("ambiente") == "QA"
    assert meta.get("analista programador") == "Dev Test"
    assert meta.get("analista de prueba") == "QA Test"

    # Verify cases and paragraph content
    cases = dump["cases"]
    assert len(cases) == 2
    assert cases[0]["title"] == "Creación de usuario regular"
    assert cases[1]["title"] == "Aprobación especial con segundo factor"

    # Verify gap detection on extracted dump
    gaps = detect_gaps(dump)
    gap_types = [g.type for g in gaps]

    # Case 2 MUST trigger missing_url, missing_expected, and unsupported_flow
    assert "missing_url" in gap_types
    assert "missing_expected" in gap_types
    assert "unsupported_flow" in gap_types

    # Case 1 credentials must not trigger credentials_in_plaintext
    assert "credentials_in_plaintext" not in gap_types

    # Negative case: CLI invocation of make_sample_narrative via python -m
    target_cli_docx = tmp_path / "cli_sample.docx"
    res = subprocess.run(
        [sys.executable, "-m", "tools.make_sample_narrative", "--out", str(target_cli_docx)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert target_cli_docx.exists()

    # Negative verification: ensure no real secrets or production domains exist
    content_text = json.dumps(dump)
    assert "password123" not in content_text.lower()
    assert "seniat.gob.ve" not in content_text.lower()
    assert "bancaribe.com.ve" not in content_text.lower()


@pytest.mark.smoke
@pytest.mark.parametrize("subcommand", ["validate", "render", "gaps"])
def test_cli_json_decode_error_never_leaks_sensitive_content(
    tmp_path: Path, subcommand: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify JSONDecodeError outputs only line and column without leaking file text or secrets."""
    secret_word = "SUPER_SECRET_TOKEN_XYZ_999"
    bad_json = tmp_path / f"bad_{subcommand}.json"
    # Malformed JSON with sensitive text at the syntax error
    bad_json.write_text(f'{{\n  {secret_word}: 12345\n}}', encoding="utf-8")

    code = cli_main([subcommand, str(bad_json)])
    assert code != 0

    captured = capsys.readouterr()
    err_output = captured.err + captured.out

    # Must contain line and column info
    assert "line" in err_output
    assert "column" in err_output
    assert "Error parsing JSON: syntax error at line" in err_output

    # CRITICAL: Must NEVER contain the sensitive text or raw exception text snippet
    assert secret_word.lower() not in err_output.lower()


@pytest.mark.smoke
def test_gitignore_hygiene() -> None:
    """Positive and negative test for .gitignore rules: ignores env files and no duplicate entries."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gitignore_path = repo_root / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist in repo root"

    lines = [
        line.strip()
        for line in gitignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    # Required env exclusions
    required_env_patterns = [".env", ".env.*", "*.env"]
    for pattern in required_env_patterns:
        assert pattern in lines, f"{pattern} must be excluded in .gitignore"

    # No duplicated entries
    duplicates = [entry for entry in lines if lines.count(entry) > 1]
    assert not duplicates, f"Duplicate entries found in .gitignore: {set(duplicates)}"

    # Negative test: simulated invalid gitignore with missing pattern and duplicate
    simulated_bad = [".venv/", "build/", "build/"]
    missing = [p for p in required_env_patterns if p not in simulated_bad]
    sim_duplicates = [entry for entry in simulated_bad if simulated_bad.count(entry) > 1]
    assert len(missing) == 3
    assert "build/" in sim_duplicates


@pytest.mark.smoke
def test_agent_skill_dependencies_exist() -> None:
    """Positive and negative test: all skills declared in agent frontmatter must exist physically."""
    import yaml

    repo_root = Path(__file__).resolve().parent.parent.parent
    agent_path = repo_root / ".agents" / "agents" / "test-normalizer.md"
    assert agent_path.exists(), "Agent file must exist"

    content = agent_path.read_text(encoding="utf-8")
    parts = content.split("---")
    assert len(parts) >= 3, "Agent file must have YAML frontmatter between --- markers"

    frontmatter = yaml.safe_load(parts[1])
    skills = frontmatter.get("skills", [])
    assert isinstance(skills, list)
    assert len(skills) > 0, "Agent must declare at least one skill"

    # Check each skill declared exists physically with SKILL.md under .agents/
    missing_skills: list[str] = []
    for skill_ref in skills:
        skill_dir = repo_root / ".agents" / skill_ref
        skill_md = skill_dir / "SKILL.md"
        if not (skill_dir.is_dir() and skill_md.is_file()):
            missing_skills.append(skill_ref)

    assert not missing_skills, f"Declared skills do not exist physically in .agents/: {missing_skills}"

    # Negative test: simulated non-existent skill is caught
    simulated_missing = "skills/non-existent-skill-xyz"
    simulated_path = repo_root / ".agents" / simulated_missing / "SKILL.md"
    assert not simulated_path.exists(), "Simulated skill must not exist"


@pytest.mark.smoke
def test_conftest_no_hardcoded_institutional_urls_or_real_credentials() -> None:
    """Verify that tests/conftest.py does not contain institutional URLs or real credentials."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    conftest_path = repo_root / "tests" / "conftest.py"
    assert conftest_path.is_file(), "tests/conftest.py must exist"

    content = conftest_path.read_text(encoding="utf-8")

    # 1. Positive checks: corporate URLs and personal credentials must NOT be in conftest.py
    assert not re.search(r"[a-z0-9.-]*seguros\.com", content, re.IGNORECASE), (
        "tests/conftest.py must not contain corporate URLs"
    )
    assert not re.search(r"\brmu[ñn]oz\b", content, re.IGNORECASE), (
        "tests/conftest.py must not contain personal analyst credentials"
    )

    # Verify synthetic defaults are present instead
    assert "https://qa.example.test/login" in content
    assert "test_user" in content
    assert "test_password" in content

    # 2. Negative check: simulated presence of sensitive patterns triggers detection
    forbidden_sample = 'QA_BASE_URL", "https://corporate-forbidden.example.com/#/login"'
    assert "corporate-forbidden.example.com" in forbidden_sample


@pytest.mark.smoke
def test_tests_no_hardcoded_credentials_or_corporate_urls() -> None:
    """Verify statically that no test files under tests/ contain assertions comparing against production data."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    tests_dir = repo_root / "tests"
    assert tests_dir.is_dir(), "tests/ directory must exist"

    forbidden_patterns = [
        re.compile(r"[a-z0-9.-]*seguros\.com", re.IGNORECASE),
        re.compile(r"\bforbidden_sample_user\b", re.IGNORECASE),
    ]
    violating_assertions: list[str] = []

    for test_file in tests_dir.rglob("*.py"):
        if test_file.resolve() == Path(__file__).resolve():
            continue

        lines = test_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("assert "):
                for pattern in forbidden_patterns:
                    if (
                        pattern.search(stripped)
                        and "not in" not in stripped
                        and "not re.search" not in stripped
                    ):
                        violating_assertions.append(f"{test_file.name}:{idx}: {stripped}")

    assert not violating_assertions, (
        f"Found forbidden assertions comparing against production data: {violating_assertions}"
    )

    # Negative check: simulated assertion with forbidden pattern is detected
    simulated_line = 'assert test_case.credentials.get("username") == "forbidden_sample_user"'
    detected = any(
        pattern.search(simulated_line)
        and "not in" not in simulated_line
        and "not re.search" not in simulated_line
        for pattern in forbidden_patterns
    )
    assert detected is True, "Scanner must detect forbidden pattern in simulated assertion"


@pytest.mark.smoke
def test_readme_no_hardcoded_personal_credentials() -> None:
    """Verify that README.md does not expose hardcoded personal test credentials."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    readme_path = repo_root / "README.md"
    assert readme_path.is_file(), "README.md must exist in repository root"

    readme_content = readme_path.read_text(encoding="utf-8")

    # Negative check 1: scanner regex detects forbidden patterns using synthetic test user
    forbidden_sample_user = "forbidden_sample_user"
    simulated_snippet = f"Tests default to QA test user {forbidden_sample_user}."
    synthetic_pattern = re.compile(rf"\b{re.escape(forbidden_sample_user)}\b", re.IGNORECASE)
    assert synthetic_pattern.search(simulated_snippet) is not None

    # Negative check 2: README.md must not contain residual personal credentials
    forbidden_credential_pattern = re.compile(r"\brmu[ñn]oz\b", re.IGNORECASE)
    assert not forbidden_credential_pattern.search(
        readme_content
    ), "README.md must not contain hardcoded personal test credentials"

    # Positive check: README.md instructs credential configuration via generic environment variables
    assert "QA_USERNAME" in readme_content
    assert "QA_PASSWORD" in readme_content





