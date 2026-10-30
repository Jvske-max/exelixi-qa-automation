"""Data models for document-driven testing and execution reporting."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepDefinition:
    """Represents a discrete test action parsed from documentation."""

    step_num: int
    raw_text: str
    action: str
    target: str
    value: str | None = None
    timestamp: str | None = None


@dataclass
class TestCase:
    """Represents a test scenario definition extracted from specification files."""

    __test__ = False

    case_id: str
    module: str
    title: str
    objective: str
    credentials: dict[str, str]
    steps: list[StepDefinition]
    source_file: str | None = None
    environment: str = "QA"
    developer: str = "Exelixi QA"
    url: str | None = None
    normalization_status: str | None = None
    manual_steps: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    """Telemetry and execution result for an individual step."""

    step_num: int
    action: str
    target: str
    status: str
    duration_ms: float = 0.0
    screenshot_path: str | None = None
    error_message: str | None = None


@dataclass
class ExecutionReport:
    """Aggregated execution report for a test case scenario."""

    case_id: str
    module: str
    title: str
    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    steps: list[StepResult] = field(default_factory=list)
    environment: str = "QA"
    summary_notes: str | None = None

    @property
    def passed_count(self) -> int:
        """Count of steps with PASSED status."""
        return sum(1 for step in self.steps if step.status.upper() == "PASSED")

    @property
    def failed_count(self) -> int:
        """Count of steps with FAILED status."""
        return sum(1 for step in self.steps if step.status.upper() == "FAILED")

    @property
    def manual_count(self) -> int:
        """Count of steps with MANUAL status."""
        return sum(1 for step in self.steps if step.status.upper() == "MANUAL")

    @property
    def total_steps(self) -> int:
        """Total number of executed steps."""
        return len(self.steps)
