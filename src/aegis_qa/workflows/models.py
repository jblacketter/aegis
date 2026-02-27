"""Data models for workflow execution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepResult:
    """Result of a single workflow step."""

    step_type: str
    service: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    skipped: bool = False
    duration_ms: float | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        """Check if this step's data contains test failures."""
        if not self.success:
            return True
        failures = self.data.get("failures", [])
        return len(failures) > 0


@dataclass
class WorkflowResult:
    """Result of a full workflow execution."""

    workflow_name: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(s.success or s.skipped for s in self.steps)

    @property
    def has_failures(self) -> bool:
        return any(s.has_failures for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "success": self.success,
            "steps": [
                {
                    "step_type": s.step_type,
                    "service": s.service,
                    "success": s.success,
                    "skipped": s.skipped,
                    "data": s.data,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                    "attempts": s.attempts,
                }
                for s in self.steps
            ],
        }
