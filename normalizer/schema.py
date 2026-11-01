"""Canonical Pydantic v2 schemas for normalized QA specifications."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Step(BaseModel):
    """Represents a single atomic action within a test case."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["navigate", "fill", "click", "verify", "manual"]
    target: str
    value: str | None = None
    source_quote: str
    source_ref: str
    confidence: Literal["high", "low"] = "high"


class Case(BaseModel):
    """Represents an individual QA test scenario."""

    model_config = ConfigDict(extra="ignore")

    n: int
    title: str
    objective: str
    url: str | None = None
    credentials: dict[str, str] = Field(default_factory=dict)
    steps: list[Step] = Field(default_factory=list)
    gaps: list[Any] = Field(default_factory=list)
    status: str = ""

    @model_validator(mode="after")
    def _compute_status(self) -> Self:
        """Determine normalization status: NEEDS_INFO, UNSUPPORTED, or READY."""
        if not self.status:
            for gap in self.gaps:
                sev = getattr(gap, "severity", None) if not isinstance(gap, dict) else gap.get("severity")
                if sev == "blocking":
                    self.status = "NEEDS_INFO"
                    return self

            if not self.steps or all(s.action == "manual" for s in self.steps):
                self.status = "UNSUPPORTED"
            else:
                self.status = "READY"
        return self


class NormalizedDoc(BaseModel):
    """Root model for canonical normalized QA specifications."""

    model_config = ConfigDict(extra="ignore")

    meta: dict[str, Any] = Field(default_factory=dict)
    cases: list[Case] = Field(default_factory=list)
