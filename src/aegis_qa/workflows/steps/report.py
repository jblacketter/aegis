"""Report step — aggregates prior step results into a structured summary."""

from __future__ import annotations

from typing import Any

from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class ReportStep(BaseStep):
    """Generates a structured JSON execution report from workflow context."""

    step_type = "report"

    async def execute(self, context: dict[str, Any]) -> StepResult:
        step_results: list[StepResult] = context.get("step_results", [])
        total = len(step_results)
        passed = sum(1 for r in step_results if r.success and not r.skipped)
        failed = sum(1 for r in step_results if not r.success and not r.skipped)
        skipped = sum(1 for r in step_results if r.skipped)
        total_duration = sum(r.duration_ms or 0 for r in step_results)

        report: dict[str, Any] = {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            },
            "total_duration_ms": total_duration,
            "steps": [
                {
                    "step_type": r.step_type,
                    "service": r.service,
                    "success": r.success,
                    "skipped": r.skipped,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in step_results
            ],
        }
        return StepResult(
            step_type="report",
            service=self.service_entry.name,
            success=True,
            data=report,
        )
