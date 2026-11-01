"""Allure 2 execution reporter and lifecycle telemetry manager."""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Any, cast

from allure_commons.logger import INDENT, AllureFileLogger
from allure_commons.model2 import (
    Attachment,
    Label,
    Status,
    StatusDetails,
    TestResult,
    TestResultContainer,
    TestStepResult,
)
from attrs import asdict

from parsers.models import ExecutionReport, StepDefinition, StepResult, TestCase

PASSWORD_MASK_PATTERN = re.compile(
    r"(?i)\b(clave|contrase[ñn]a|password|secret|token|pin)\b\s*[:=]\s*(?!\[REDACTED\]|['\"]\[REDACTED\]['\"])(?:(['\"])(.*?)\2|([^\s'\"]+))"
)
TARGET_SENSITIVE_PARAM_PATTERN = re.compile(
    r"(?i)(?:[?&;]|\b)(clave|contrase[ñn]a|password|secret|token|pin)\s*[:=]\s*([^&\s'\"]+)"
)
URL_CREDENTIAL_PATTERN = re.compile(r"(https?://[^:\s]+):(?!\[REDACTED\])([^@\s]+)@")
CEDULA_PATTERN = re.compile(
    r"\b[VEve][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})(?!-\d)\b"
)
RIF_PATTERN = re.compile(
    r"\b(?:[JjGg][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{8,9})(?:[\s\.-]*\d)?|[VvEePp][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})[\s\.-]*\d)\b"
)
EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
JWT_PATTERN = re.compile(
    r"\beyJ[a-zA-Z0-9_=-]{10,}\.[a-zA-Z0-9_=-]{10,}\.[a-zA-Z0-9_=-]{10,}\b"
)


class _StandardAllureFileLogger(AllureFileLogger):
    """File logger preserving standard Allure 2 keys such as steps and attachments."""

    def _report_item(self, item: Any) -> None:
        import json
        import os

        indent = INDENT if os.environ.get("ALLURE_INDENT_OUTPUT") else None
        file_pattern = getattr(item, "file_pattern", "{prefix}-result.json")
        filename = file_pattern.format(prefix=uuid.uuid4())
        data = asdict(
            cast(Any, item),
            filter=lambda f, v: (
                v
                or v is False
                or (
                    f is not None
                    and getattr(f, "name", None) in ("steps", "attachments")
                )
            ),
        )

        tmp_filepath = self._report_dir / f"{filename}.tmp"
        final_filepath = self._report_dir / filename

        with open(tmp_filepath, "w", encoding="utf8") as json_file:
            json.dump(data, json_file, indent=indent, ensure_ascii=False)

        os.replace(tmp_filepath, final_filepath)


def _map_status(status_str: str | None) -> str:
    """Map string test status representation to Allure 2 Status enum."""
    if not status_str:
        return Status.UNKNOWN

    normalized = status_str.strip().upper()
    if normalized in ("PASSED", "PASS"):
        return Status.PASSED
    if normalized in ("FAILED", "FAIL"):
        return Status.FAILED
    if normalized in ("BROKEN", "ERROR", "BLOCKED"):
        return Status.BROKEN
    if normalized in ("SKIPPED", "SKIP", "MANUAL"):
        return Status.SKIPPED
    return Status.BROKEN


class AllureReporter:
    """Manages Allure lifecycle events and generates Allure v2 JSON execution reports."""

    def __init__(self, results_dir: Path | str, clean: bool = False) -> None:
        """Initialize the Allure reporter and create output directory."""
        self._results_dir = Path(results_dir).resolve()
        if self._results_dir.exists() and not self._results_dir.is_dir():
            raise NotADirectoryError(
                f"Target path '{self._results_dir}' exists and is not a directory."
            )

        self._results_dir.mkdir(parents=True, exist_ok=True)
        self._file_logger = _StandardAllureFileLogger(self._results_dir, clean=clean)

        self._current_test_case: TestCase | None = None
        self._current_test_result: TestResult | None = None
        self._current_container: TestResultContainer | None = None
        self._current_step_result: TestStepResult | None = None
        self._current_step_def: StepDefinition | None = None

    @property
    def results_dir(self) -> Path:
        """Return absolute path to results directory."""
        return self._results_dir

    def mask_text(self, text: str, step: StepDefinition | None = None) -> str:
        """Redact passwords, credentials, tokens, and PII from text."""
        if not text:
            return ""

        masked = text

        # 1. Mask known credentials from active test case
        if self._current_test_case and self._current_test_case.credentials:
            for val in self._current_test_case.credentials.values():
                if (
                    isinstance(val, str)
                    and len(val.strip()) > 0
                    and not val.startswith("${")
                ):
                    masked = masked.replace(val, "[REDACTED]")

        # 2. Mask step value if provided, avoiding over-masking short non-sensitive values
        active_step = step or self._current_step_def
        if active_step and active_step.value and not active_step.value.startswith("${"):
            val_trimmed = active_step.value.strip()
            if len(val_trimmed) > 0:
                is_sensitive_action = False
                target_lower = (active_step.target or "").lower()
                action_lower = (active_step.action or "").lower()
                sensitive_keywords = (
                    "clave",
                    "contraseñ",
                    "contrasen",
                    "password",
                    "secret",
                    "token",
                    "pin",
                )
                if any(k in target_lower for k in sensitive_keywords) or any(
                    k in action_lower for k in sensitive_keywords
                ):
                    is_sensitive_action = True

                if is_sensitive_action or len(val_trimmed) >= 3:
                    masked = masked.replace(active_step.value, "[REDACTED]")

        # 3. Mask embedded target credentials
        if active_step and active_step.target:
            for match in TARGET_SENSITIVE_PARAM_PATTERN.finditer(active_step.target):
                val = match.group(2).strip(" '\"")
                if val and val != "[REDACTED]":
                    masked = masked.replace(val, "[REDACTED]")
            for match in URL_CREDENTIAL_PATTERN.finditer(active_step.target):
                val = match.group(2).strip()
                if val and val != "[REDACTED]":
                    masked = masked.replace(val, "[REDACTED]")

        # 4. Pattern-based redactions (URL credentials, passwords, tokens, PII)
        masked = URL_CREDENTIAL_PATTERN.sub(r"\1:[REDACTED]@", masked)
        masked = PASSWORD_MASK_PATTERN.sub(r"\1: [REDACTED]", masked)
        masked = JWT_PATTERN.sub("[REDACTED]", masked)
        masked = RIF_PATTERN.sub("[REDACTED]", masked)
        masked = CEDULA_PATTERN.sub("[REDACTED]", masked)
        masked = EMAIL_PATTERN.sub("[REDACTED]", masked)

        return masked

    def start_test_case(self, test_case: TestCase) -> None:
        """Initialize Allure TestResult and Container for a test case scenario."""
        self._current_test_case = test_case
        test_uuid = str(uuid.uuid4())
        container_uuid = str(uuid.uuid4())
        start_time_ms = int(time.time() * 1000)

        masked_title = self.mask_text(test_case.title) if test_case.title else ""
        masked_objective = (
            self.mask_text(test_case.objective)
            if test_case.objective
            else test_case.objective
        )

        self._current_container = TestResultContainer(
            uuid=container_uuid,
            name=masked_title,
            children=[test_uuid],
            start=start_time_ms,
        )

        labels = [
            Label(name="feature", value=test_case.module),
            Label(name="suite", value=test_case.module),
            Label(name="tag", value=test_case.environment),
            Label(name="framework", value="doc-runner"),
        ]

        self._current_test_result = TestResult(
            uuid=test_uuid,
            name=masked_title,
            description=masked_objective,
            status=Status.PASSED,
            start=start_time_ms,
            labels=labels,
            steps=[],
            attachments=[],
        )

    def start_step(self, step: StepDefinition, step_num: int | None = None) -> None:
        """Start a test step within the active test scenario."""
        if self._current_test_result is None:
            raise RuntimeError("Cannot start_step without an active test case.")

        num = step_num if step_num is not None else step.step_num
        step_name = f"Paso {num}: {step.action} {step.target}".strip()
        if step.value:
            masked_val = self.mask_text(step.value, step=step)
            step_name += f" = {masked_val}"

        masked_step_name = self.mask_text(step_name, step=step)

        self._current_step_def = step
        self._current_step_result = TestStepResult(
            name=masked_step_name,
            status=Status.PASSED,
            start=int(time.time() * 1000),
            steps=[],
            attachments=[],
        )

    def stop_step(
        self,
        step: StepDefinition | StepResult,
        result: StepResult | None = None,
    ) -> None:
        """Complete the current step, record status, attach screenshots, and mask errors."""
        if self._current_test_result is None:
            raise RuntimeError("Cannot stop_step without an active test case.")

        if result is None and isinstance(step, StepResult):
            step_result = step
            step_def = self._current_step_def
        elif isinstance(result, StepResult):
            step_result = result
            step_def = (
                step if isinstance(step, StepDefinition) else self._current_step_def
            )
        else:
            raise ValueError("A valid StepResult must be provided to stop_step.")

        if self._current_step_result is None:
            step_name = f"Paso {step_result.step_num}: {step_result.action} {step_result.target}".strip()
            masked_step_name = self.mask_text(step_name, step=step_def)
            self._current_step_result = TestStepResult(
                name=masked_step_name,
                status=Status.PASSED,
                start=int(time.time() * 1000),
                steps=[],
                attachments=[],
            )
        else:
            self._current_step_result.name = self.mask_text(
                self._current_step_result.name, step=step_def
            )

        step_status = _map_status(step_result.status)
        self._current_step_result.status = step_status

        duration_ms = step_result.duration_ms or 0.0
        self._current_step_result.stop = self._current_step_result.start + int(
            duration_ms
        )

        # Attach screenshot if file exists
        if step_result.screenshot_path:
            screenshot_file = Path(step_result.screenshot_path)
            if screenshot_file.is_file():
                attachment_filename = f"{uuid.uuid4()}-attachment.png"
                self._file_logger.report_attached_file(
                    str(screenshot_file), attachment_filename
                )
                attachment = Attachment(
                    name=f"Screenshot Paso {step_result.step_num}",
                    source=attachment_filename,
                    type="image/png",
                )
                self._current_step_result.attachments.append(attachment)

        # Redact and record error details
        if step_result.error_message:
            masked_error = self.mask_text(step_result.error_message, step=step_def)
            self._current_step_result.statusDetails = StatusDetails(
                message=masked_error,
                trace=masked_error,
            )

        self._current_test_result.steps.append(self._current_step_result)
        self._current_step_result = None
        self._current_step_def = None

    def stop_test_case(self, report: ExecutionReport) -> Path:
        """Complete the scenario, serialize Allure v2 JSON result and container, and persist to disk."""
        if self._current_test_result is None:
            raise RuntimeError(
                "Cannot stop_test_case without a prior start_test_case call."
            )

        test_status = _map_status(report.status)
        self._current_test_result.status = test_status

        stop_time_ms = int(time.time() * 1000)
        if report.duration_seconds and report.duration_seconds > 0:
            stop_time_ms = max(
                stop_time_ms,
                self._current_test_result.start + int(report.duration_seconds * 1000),
            )

        self._current_test_result.stop = stop_time_ms
        if self._current_container:
            self._current_container.stop = stop_time_ms

        # Propagate first failed step details to test level if not already set
        if (
            test_status in (Status.FAILED, Status.BROKEN)
            and not self._current_test_result.statusDetails
        ):
            for step_item in self._current_test_result.steps:
                if step_item.statusDetails:
                    self._current_test_result.statusDetails = step_item.statusDetails
                    break

        # Emit Allure v2 JSON files
        self._file_logger.report_result(self._current_test_result)
        if self._current_container:
            self._file_logger.report_container(self._current_container)

        result_path = (
            self._results_dir / f"{self._current_test_result.uuid}-result.json"
        )

        # Reset active state
        self._current_test_result = None
        self._current_container = None
        self._current_test_case = None

        return result_path
