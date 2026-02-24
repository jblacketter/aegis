"""Test execution step — calls qaagent to run tests."""

from __future__ import annotations

from typing import Any

from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class RunTestsStep(BaseStep):
    step_type = "test"

    async def execute(self, context: dict[str, Any]) -> StepResult:
        try:
            data = await self._post("/api/runs", payload={})
            failures = data.get("failures", [])
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=True,
                data={
                    "total": data.get("total", 0),
                    "passed": data.get("passed", 0),
                    "failed": data.get("failed", 0),
                    "failures": failures,
                },
            )
        except Exception as exc:
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=False,
                error=str(exc),
            )
