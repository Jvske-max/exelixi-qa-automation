"""Unit tests for static type checking configuration and quality gate."""

import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def validate_mypy_toml_config(config: dict) -> bool:
    """Validate that tool.mypy section contains required quality gate settings."""
    tool = config.get("tool", {})
    if "mypy" not in tool:
        return False
    mypy_cfg = tool["mypy"]
    required_keys = {
        "python_version": "3.13",
        "explicit_package_bases": True,
        "check_untyped_defs": True,
    }
    for key, expected_val in required_keys.items():
        if mypy_cfg.get(key) != expected_val:
            return False
    return True


def validate_openspec_type_checker_config(config: dict) -> bool:
    """Validate that openspec/config.yaml has quality type checker enabled."""
    quality = config.get("testing", {}).get("quality", {})
    type_checker = quality.get("type_checker", {})
    if type_checker.get("available") is not True:
        return False
    command = type_checker.get("command")
    return bool(command and "mypy" in command)


def test_mypy_configured_in_pyproject_toml() -> None:
    """Positive test: pyproject.toml exists and contains [tool.mypy] with proper settings."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    assert "tool" in data, "pyproject.toml must contain [tool] table"
    assert "mypy" in data["tool"], "pyproject.toml must configure [tool.mypy]"
    assert validate_mypy_toml_config(data) is True, (
        "tool.mypy must contain required quality settings"
    )

    mypy_cfg = data["tool"]["mypy"]
    assert mypy_cfg.get("python_version") == "3.13"
    assert mypy_cfg.get("explicit_package_bases") is True
    assert mypy_cfg.get("check_untyped_defs") is True


def test_mypy_config_validation_rejects_missing_or_invalid() -> None:
    """Negative test: validate_mypy_toml_config returns False for missing or incomplete configuration."""
    assert validate_mypy_toml_config({}) is False
    assert validate_mypy_toml_config({"tool": {}}) is False
    assert validate_mypy_toml_config({"tool": {"mypy": {"python_version": "3.11"}}}) is False
    assert (
        validate_mypy_toml_config(
            {"tool": {"mypy": {"python_version": "3.13", "explicit_package_bases": False}}}
        )
        is False
    )


def test_mypy_reports_failure_on_type_error(tmp_path: Path) -> None:
    """Negative test: mypy detects type violation in synthetic snippet and exits with non-zero code."""
    invalid_file = tmp_path / "type_error_snippet.py"
    invalid_file.write_text('x: int = "string"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-error-summary", str(invalid_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, (
        f"mypy should fail on invalid snippet, got returncode 0. Output:\n{result.stdout}"
    )
    assert "Incompatible types in assignment" in result.stdout or "error" in result.stdout.lower()


def test_mypy_succeeds_on_valid_snippet(tmp_path: Path) -> None:
    """Positive test: mypy passes cleanly on valid typed snippet and exits with code 0."""
    valid_file = tmp_path / "valid_snippet.py"
    valid_file.write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\nx: int = add(1, 2)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "mypy", str(valid_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"mypy should succeed on valid snippet. Stderr:\n{result.stderr}\nStdout:\n{result.stdout}"
    )


def test_openspec_type_checker_configured() -> None:
    """Positive test: openspec/config.yaml enables type_checker quality gate with mypy command."""
    config_path = REPO_ROOT / "openspec" / "config.yaml"
    assert config_path.exists(), "openspec/config.yaml must exist"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert validate_openspec_type_checker_config(data) is True, (
        "openspec/config.yaml must configure testing.quality.type_checker with available: true and mypy command"
    )
    quality = data["testing"]["quality"]["type_checker"]
    assert quality["available"] is True
    assert "mypy" in quality["command"]


def test_openspec_type_checker_validation_rejects_disabled() -> None:
    """Negative test: validate_openspec_type_checker_config returns False when type checker is disabled or missing."""
    assert validate_openspec_type_checker_config({}) is False
    assert (
        validate_openspec_type_checker_config(
            {"testing": {"quality": {"type_checker": {"available": False, "command": None}}}}
        )
        is False
    )
    assert (
        validate_openspec_type_checker_config(
            {"testing": {"quality": {"type_checker": {"available": True, "command": None}}}}
        )
        is False
    )
