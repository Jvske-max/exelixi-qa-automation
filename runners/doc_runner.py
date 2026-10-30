"""Playwright-based test dispatcher and execution engine for document-driven QA."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error, Page, TimeoutError, expect, sync_playwright

from pageobjects.login_page import LoginPage
from pageobjects.user_management_page import UserManagementPage
from parsers.doc_parser import DocParser
from parsers.models import ExecutionReport, StepDefinition, StepResult, TestCase
from reporting.pdf_reporter import PDFReporter


def _expand_env_vars(text: str) -> str:
    """Expand ${VAR} references using os.environ.

    Raises:
        ValueError: If a referenced environment variable is not defined, naming the variable.
    """
    pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")
    matches = pattern.findall(text)
    for var_name in matches:
        if var_name not in os.environ:
            raise ValueError(f"Missing required environment variable: ${{{var_name}}}")

    return pattern.sub(lambda m: os.environ[m.group(1)], text)


PASSWORD_MASK_PATTERN = re.compile(
    r"(?i)\b(clave|contrase[ñn]a|password|secret|token|pin)\b\s*[:=]\s*(?!\[REDACTED\])(\S+)"
)
TARGET_SENSITIVE_PARAM_PATTERN = re.compile(
    r"(?i)(?:[?&;]|\b)(clave|contrase[ñn]a|password|secret|token|pin)\s*[:=]\s*([^&\s'\"]+)"
)
URL_CREDENTIAL_PATTERN = re.compile(r"https?://([^:]+):([^@\s]+)@")
CEDULA_PATTERN = re.compile(r"\b[VEve][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})(?!-\d)\b")
RIF_PATTERN = re.compile(
    r"\b(?:[JjGg][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{8,9})(?:[\s\.-]*\d)?|[VvEePp][\s\.-]*(?:\d{1,3}(?:[.\s]\d{3}){1,3}|\d{6,9})[\s\.-]*\d)\b"
)
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_=-]{10,}\.[a-zA-Z0-9_=-]{10,}\.[a-zA-Z0-9_=-]{10,}\b")


def _mask_error_message(error_msg: str, step: StepDefinition, test_case: TestCase) -> str:
    """Mask step.value, step.target credentials, PII patterns, and credential patterns in error message."""
    if step.value and len(step.value.strip()) > 0:
        error_msg = error_msg.replace(step.value, "[REDACTED]")

    if test_case.credentials:
        for val in test_case.credentials.values():
            if isinstance(val, str) and len(val.strip()) > 0:
                error_msg = error_msg.replace(val, "[REDACTED]")

    if step.target:
        for m in TARGET_SENSITIVE_PARAM_PATTERN.finditer(step.target):
            sensitive_val = m.group(2).strip(" '\"")
            if sensitive_val and sensitive_val != "[REDACTED]":
                error_msg = error_msg.replace(sensitive_val, "[REDACTED]")

        for m in URL_CREDENTIAL_PATTERN.finditer(step.target):
            sensitive_val = m.group(2).strip()
            if sensitive_val and sensitive_val != "[REDACTED]":
                error_msg = error_msg.replace(sensitive_val, "[REDACTED]")

        for m in PASSWORD_MASK_PATTERN.finditer(step.target):
            sensitive_val = m.group(2).strip(" '\"")
            if sensitive_val and sensitive_val != "[REDACTED]":
                error_msg = error_msg.replace(sensitive_val, "[REDACTED]")

    error_msg = PASSWORD_MASK_PATTERN.sub(r"\1: [REDACTED]", error_msg)
    error_msg = JWT_PATTERN.sub("[REDACTED]", error_msg)
    error_msg = RIF_PATTERN.sub("[REDACTED]", error_msg)
    error_msg = CEDULA_PATTERN.sub("[REDACTED]", error_msg)
    error_msg = EMAIL_PATTERN.sub("[REDACTED]", error_msg)
    return error_msg


class DocRunner:
    """Dispatches document-defined test cases using Playwright and Page Objects."""

    def __init__(
        self,
        headless: bool = True,
        screenshots_dir: str | Path | None = None,
        default_timeout: int = 15000,
        stop_on_failure: bool = True,
    ) -> None:
        """Initialize the document test runner.

        Args:
            headless: Whether to run the browser in headless mode.
            screenshots_dir: Directory where step screenshots will be saved.
            default_timeout: Default action/navigation timeout in milliseconds.
            stop_on_failure: Whether to halt step execution on first failure.
        """
        self.headless = headless
        self.default_timeout = default_timeout
        self.stop_on_failure = stop_on_failure

        if screenshots_dir:
            self.screenshots_dir = Path(screenshots_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.screenshots_dir = Path("artifacts") / "screenshots" / timestamp

        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def _check_normalization_gate(self, test_case: TestCase) -> None:
        """Check normalization status before opening browser or executing steps.

        If status is NEEDS_INFO or UNSUPPORTED, prints path to <stem>.gaps.md if present
        and terminates immediately with exit code 2.
        """
        status = (test_case.normalization_status or "").strip().upper()
        if status in ("NEEDS_INFO", "UNSUPPORTED"):
            if test_case.source_file:
                source_p = Path(test_case.source_file)
                gaps_p = source_p.with_name(f"{source_p.stem}.gaps.md")
                if gaps_p.is_file():
                    print(str(gaps_p.resolve()))
            sys.exit(2)

    def _expand_environment_variables(self, test_case: TestCase) -> None:
        """Expand ${VAR} references in credentials and fill step values using os.environ."""
        if test_case.credentials:
            expanded_creds: dict[str, str] = {}
            for k, v in test_case.credentials.items():
                if isinstance(v, str) and "${" in v:
                    expanded_creds[k] = _expand_env_vars(v)
                else:
                    expanded_creds[k] = v
            test_case.credentials = expanded_creds

        for step in test_case.steps:
            if step.action.lower() in ("fill", "input", "type", "keyboard") and step.value and "${" in step.value:
                step.value = _expand_env_vars(step.value)

    def _launch_and_execute(
        self,
        test_case: TestCase,
        base_url: str | None = None,
    ) -> ExecutionReport:
        """Launch Playwright browser context and execute test case."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context()
            new_page = context.new_page()
            new_page.set_default_timeout(self.default_timeout)
            try:
                return self._execute_test_case(test_case=test_case, page=new_page, base_url=base_url)
            finally:
                context.close()
                browser.close()

    def run_test_case(
        self,
        test_case: TestCase,
        base_url: str | None = None,
        page: Page | None = None,
    ) -> ExecutionReport:
        """Execute a parsed TestCase against a browser instance.

        If `page` is provided, execution reuses that page; otherwise a fresh
        Playwright browser context is created and managed.

        Args:
            test_case: The TestCase model containing steps and metadata.
            base_url: Optional base application URL overriding the test case default.
            page: Optional existing Playwright Page object.

        Returns:
            Populated ExecutionReport model with step results and telemetry.
        """
        # 1. Pre-flight Gate
        self._check_normalization_gate(test_case)

        # 2. Expand ${VAR} in credentials and fill values
        self._expand_environment_variables(test_case)

        if page is not None:
            return self._execute_test_case(test_case=test_case, page=page, base_url=base_url)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(self._launch_and_execute, test_case, base_url).result()

        return self._launch_and_execute(test_case, base_url)

    def run_document(
        self,
        doc_path: str | Path,
        output_report_path: str | Path | None = None,
        base_url: str | None = None,
    ) -> ExecutionReport:
        """Ingest a test specification document, execute steps, and optionally generate a PDF report.

        Args:
            doc_path: Path to the .docx or .pdf specification document.
            output_report_path: Optional path where executive PDF report will be saved.
            base_url: Optional base application URL override.

        Returns:
            ExecutionReport containing execution telemetry and step verdicts.
        """
        test_case = DocParser.parse(doc_path)
        self._check_normalization_gate(test_case)
        report = self.run_test_case(test_case=test_case, base_url=base_url)

        if output_report_path:
            reporter = PDFReporter()
            reporter.generate_report(report, str(output_report_path))

        return report

    def _execute_test_case(
        self,
        test_case: TestCase,
        page: Page,
        base_url: str | None = None,
    ) -> ExecutionReport:
        """Internal execution loop iterating through steps, capturing telemetry and screenshots."""
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = time.perf_counter()
        step_results: list[StepResult] = []

        if test_case.normalization_status is not None:
            resolved_base_url = base_url or test_case.url or ""
        else:
            resolved_base_url = (
                base_url
                or test_case.url
                or os.getenv("QA_BASE_URL", "")
            )

        for step in test_case.steps:
            step_start = time.perf_counter()
            screenshot_path: str | None = None
            error_msg: str | None = None
            passed = False

            try:
                self._dispatch_step(page, step, test_case, resolved_base_url)
                passed = True
                screenshot_path = self._capture_screenshot(page, f"step_{step.step_num}.png")
            except Exception as exc:  # noqa: BLE001
                passed = False
                raw_error = f"{type(exc).__name__}: {exc}"
                error_msg = _mask_error_message(raw_error, step, test_case)
                screenshot_path = self._capture_screenshot(page, f"step_{step.step_num}_failed.png")

            duration_ms = (time.perf_counter() - step_start) * 1000.0
            step_results.append(
                StepResult(
                    step_num=step.step_num,
                    action=step.action,
                    target=step.target,
                    status="PASSED" if passed else "FAILED",
                    duration_ms=round(duration_ms, 2),
                    screenshot_path=screenshot_path,
                    error_message=error_msg,
                )
            )

            if not passed and self.stop_on_failure:
                break

        # Append manual steps
        next_step_num = len(step_results) + 1
        for manual_text in test_case.manual_steps:
            step_results.append(
                StepResult(
                    step_num=next_step_num,
                    action="manual",
                    target=manual_text,
                    status="MANUAL",
                    duration_ms=0.0,
                    screenshot_path=None,
                    error_message=None,
                )
            )
            next_step_num += 1

        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_duration = time.perf_counter() - start_time

        has_failed = any(s.status.upper() == "FAILED" for s in step_results)
        if has_failed:
            overall_status = "FAILED"
        elif test_case.manual_steps:
            overall_status = "PARTIAL"
        else:
            overall_status = "PASSED"

        return ExecutionReport(
            case_id=test_case.case_id,
            module=test_case.module,
            title=test_case.title,
            status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(total_duration, 2),
            steps=step_results,
            environment=test_case.environment,
            summary_notes=test_case.objective,
        )

    def _dispatch_step(
        self,
        page: Page,
        step: StepDefinition,
        test_case: TestCase,
        base_url: str,
    ) -> None:
        """Route a step to a Page Object or generic action fallback."""
        route = self._detect_step_route(step)

        # Ensure page is navigated away from blank if executing non-navigation steps
        current_url = getattr(page, "url", None)
        if (
            isinstance(current_url, str)
            and (not current_url or current_url.startswith("about:"))
            and route != "navigate"
        ):
            if test_case.normalization_status is not None and not base_url:
                raise ValueError("Missing base URL for normalized test case with interactive steps")
            if base_url:
                login_page = LoginPage(page)
                login_page.navigate(base_url)

        # 1. Navigation / Login route
        if route == "navigate":
            target_url = (
                step.target
                if step.target.startswith(("http://", "https://", "file://", "about:"))
                else base_url
            )
            if test_case.normalization_status is not None and not target_url:
                raise ValueError("Missing target URL for navigation step in normalized test case")
            login_page = LoginPage(page)
            if target_url:
                login_page.navigate(target_url)
            return

        if route == "login":
            if test_case.normalization_status is not None:
                username = (
                    test_case.credentials.get("username")
                    or test_case.credentials.get("usuario")
                    or ""
                )
                password = (
                    test_case.credentials.get("password")
                    or test_case.credentials.get("clave")
                    or ""
                )
                if not username or not password:
                    raise ValueError("Missing login credentials for normalized test case")
            else:
                username = (
                    test_case.credentials.get("username")
                    or test_case.credentials.get("usuario")
                    or os.getenv("QA_USERNAME", "")
                )
                password = (
                    test_case.credentials.get("password")
                    or test_case.credentials.get("clave")
                    or os.getenv("QA_PASSWORD", "")
                )
            login_page = LoginPage(page)
            login_page.login(username, password)
            return

        # 2. User Management route
        if route == "user_mgmt_all":
            user_mgmt = UserManagementPage(page)
            user_mgmt.navigate_to_user_management()
            return

        if route == "user_mgmt_mantenimiento":
            user_mgmt = UserManagementPage(page)
            user_mgmt.click_mantenimiento(timeout=self.default_timeout)
            return

        if route == "user_mgmt_seguridad":
            user_mgmt = UserManagementPage(page)
            user_mgmt.click_seguridad(timeout=self.default_timeout)
            return

        if route == "user_mgmt_add_user":
            user_mgmt = UserManagementPage(page)
            user_mgmt.open_add_user_form()
            return

        if route == "user_mgmt_save":
            user_mgmt = UserManagementPage(page)
            user_mgmt.save_user()
            return

        # 3. Generic Action Fallback
        self._dispatch_generic_action(page, step, test_case, base_url)

    def _detect_step_route(self, step: StepDefinition) -> str:
        """Detect which specialized route (login, navigation, user management) applies."""
        raw = step.raw_text.lower()
        target = step.target.lower()
        action = step.action.lower()
        clean_target = re.sub(r"\s*\([^)]*\)$", "", target).strip()

        # Navigation detection
        if action in ("navigate", "goto", "open"):
            return "navigate"
        if target.startswith(("http://", "https://")):
            return "navigate"
        if any(kw in raw for kw in ("navigate to", "navegar a", "ir a", "abrir enlace", "abrir link")):
            return "navigate"

        # Login detection
        if action == "login":
            return "login"
        if any(kw in raw for kw in ("login", "iniciar sesión", "iniciar sesion", "inicie sesión", "ingresar al sistema")):
            return "login"
        if any(kw in target for kw in ("login", "iniciar sesión", "iniciar sesion")):
            return "login"
        if ("tabulacion" in (step.value or "").lower() or "tabulacion" in raw) and (
            "entrar" in (step.value or "").lower() or "ctrl-v" in (step.value or "").lower()
        ):
            return "login"

        # User Management detection
        if "agregar usuario" in clean_target or "agregar usuario" in raw or "add user" in clean_target:
            return "user_mgmt_add_user"
        if ("mantenimiento" in clean_target and "seguridad" in clean_target) or (
            any(kw in raw for kw in ("gestión de usuarios", "gestion de usuarios", "mantenimiento de usuarios"))
        ):
            return "user_mgmt_all"
        if "mantenimiento" in clean_target or ("mantenimiento" in raw and "click" in action):
            return "user_mgmt_mantenimiento"
        if "seguridad" in clean_target or ("seguridad" in raw and "click" in action):
            return "user_mgmt_seguridad"
        if "guardar" in clean_target and ("usuario" in raw or "form" in raw):
            return "user_mgmt_save"

        return "generic"

    def _dispatch_generic_action(
        self,
        page: Page,
        step: StepDefinition,
        test_case: TestCase,
        base_url: str,
    ) -> None:
        """Execute generic interaction fallback using element heuristics and Playwright locators."""
        action = step.action.lower()
        clean_target = re.sub(r"\s*\([^)]*\)$", "", step.target).strip()
        role_match = re.search(r"\(([^)]+)\)$", step.target)
        role_tag = role_match.group(1).lower().strip() if role_match else ""

        if action in ("click", "double_click", "dblclick"):
            # Ignore noise window/document background clicks from Steps Recorder
            if clean_target.lower() in ("document", "window", "desktop", ""):
                with contextlib.suppress(Error, TimeoutError):
                    page.locator("body").click(timeout=1000)
                return

            locator = self._locate_for_click(page, clean_target, role_tag)
            if action in ("double_click", "dblclick"):
                locator.dblclick(timeout=self.default_timeout)
            else:
                locator.click(timeout=self.default_timeout)

        elif action in ("fill", "input", "type", "keyboard"):
            val = step.value or ""
            target_lower = clean_target.lower()
            if not val:
                if "usuario" in target_lower or "user" in target_lower:
                    val = (
                        test_case.credentials.get("username")
                        or test_case.credentials.get("usuario")
                        or ""
                    )
                elif any(k in target_lower for k in ("clave", "password", "contraseña", "contrasena")):
                    val = (
                        test_case.credentials.get("password")
                        or test_case.credentials.get("clave")
                        or ""
                    )

            if (
                test_case.normalization_status is not None
                and not val
                and any(
                    k in target_lower
                    for k in ("usuario", "user", "clave", "password", "contraseña", "contrasena")
                )
            ):
                raise ValueError("Missing credential value for normalized test case step")

            locator = self._locate_for_fill(page, clean_target)
            locator.fill(val, timeout=self.default_timeout)

        elif action in ("goto", "navigate"):
            target_url = (
                step.target
                if step.target.startswith(("http://", "https://", "file://", "about:"))
                else base_url
            )
            if target_url:
                page.goto(target_url, timeout=self.default_timeout)
                page.wait_for_load_state("networkidle")

        elif action in ("verify", "assert"):
            loc = page.get_by_text(clean_target, exact=False).first
            expect(loc).to_be_visible(timeout=self.default_timeout)

        elif action == "scroll":
            page.evaluate("window.scrollBy(0, 300)")

        else:
            # Fallback attempt to click target
            locator = self._locate_for_click(page, clean_target, role_tag)
            locator.click(timeout=self.default_timeout)

    def _locate_for_click(self, page: Page, clean_target: str, role_tag: str):
        """Locate element for click actions using CSS, role-based, or text matching."""
        # 1. Selector check
        if any(clean_target.startswith(p) for p in ("#", ".", "//", "xpath=", "css=")) or any(
            c in clean_target for c in ("[", ">")
        ):
            return page.locator(clean_target).first

        # 2. Explicit role from hint
        if "button" in role_tag:
            btn = page.get_by_role("button", name=clean_target)
            if btn.count() > 0:
                return btn.first
        elif "link" in role_tag:
            lnk = page.get_by_role("link", name=clean_target)
            if lnk.count() > 0:
                return lnk.first

        # 3. Tag-specific heuristics
        btn_loc = page.locator(f"button:has-text({clean_target!r})")
        if btn_loc.count() > 0:
            return btn_loc.first

        lnk_loc = page.locator(f"a:has-text({clean_target!r})")
        if lnk_loc.count() > 0:
            return lnk_loc.first

        by_role_btn = page.get_by_role("button", name=clean_target)
        if by_role_btn.count() > 0:
            return by_role_btn.first

        by_role_lnk = page.get_by_role("link", name=clean_target)
        if by_role_lnk.count() > 0:
            return by_role_lnk.first

        # 4. Text match
        exact_text = page.get_by_text(clean_target, exact=True)
        if exact_text.count() > 0:
            return exact_text.first

        partial_text = page.get_by_text(clean_target, exact=False)
        if partial_text.count() > 0:
            return partial_text.first

        # 5. Default fallback locator
        return page.locator(f":has-text({clean_target!r})").first

    def _locate_for_fill(self, page: Page, clean_target: str):
        """Locate element for text input actions using placeholder, label, role, or attribute matching."""
        if any(clean_target.startswith(p) for p in ("#", ".", "//", "xpath=", "css=")) or any(
            c in clean_target for c in ("[", ">")
        ):
            return page.locator(clean_target).first

        by_ph = page.get_by_placeholder(clean_target)
        if by_ph.count() > 0:
            return by_ph.first

        by_lbl = page.get_by_label(clean_target)
        if by_lbl.count() > 0:
            return by_lbl.first

        by_tb = page.get_by_role("textbox", name=clean_target)
        if by_tb.count() > 0:
            return by_tb.first

        by_attr = page.locator(
            f"input[name='{clean_target}'], input[id='{clean_target}'], "
            f"input[placeholder*='{clean_target}'], textarea[name='{clean_target}']"
        )
        if by_attr.count() > 0:
            return by_attr.first

        return page.locator(f"input[name*='{clean_target}'], #{clean_target}").first

    def _capture_screenshot(self, page: Page, filename: str) -> str | None:
        """Capture screenshot safely, returning absolute path or None if screenshot fails."""
        try:
            target_path = self.screenshots_dir / filename
            page.screenshot(path=str(target_path))
            return str(target_path.resolve())
        except (Error, TimeoutError, OSError):
            return None


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the document test runner CLI."""
    parser = argparse.ArgumentParser(
        description="Document-Driven Test Dispatcher & Execution Engine CLI"
    )
    parser.add_argument(
        "--doc",
        required=True,
        help="Path to specification file (.docx or .pdf)",
    )
    parser.add_argument(
        "--output-report",
        default=None,
        help="Path to output executive PDF report",
    )
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default)",
    )
    headless_group.add_argument(
        "--headed",
        dest="headless",
        action="store_false",
        help="Run browser in headed mode",
    )
    parser.add_argument(
        "--screenshots-dir",
        default=None,
        help="Directory to store step screenshot artifacts",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Target base URL override",
    )
    parser.add_argument(
        "--default-timeout",
        type=int,
        default=15000,
        help="Default timeout in milliseconds (default: 15000)",
    )
    parser.add_argument(
        "--stop-on-failure",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop execution on first step failure (default: True)",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """CLI execution entrypoint."""
    parsed = parse_args(args)
    runner = DocRunner(
        headless=parsed.headless,
        screenshots_dir=parsed.screenshots_dir,
        default_timeout=parsed.default_timeout,
        stop_on_failure=parsed.stop_on_failure,
    )
    report = runner.run_document(
        doc_path=parsed.doc,
        output_report_path=parsed.output_report,
        base_url=parsed.base_url,
    )
    print(
        f"Execution Report [{report.case_id}]: {report.status} "
        f"({report.passed_count}/{report.total_steps} passed in {report.duration_seconds:.2f}s)"
    )
    if parsed.output_report:
        print(f"Executive PDF Report saved to: {parsed.output_report}")
    return 0 if report.status.upper() in ("PASSED", "PARTIAL") else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
