"""Verification step — calls qaagent to re-run tests and confirm fixes."""

from __future__ import annotations

from typing import Any

from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class VerifyStep(BaseStep):
    step_type = "verify"

    async def execute(self, context: dict[str, Any]) -> StepResult:
        try:
            data = await self._post("/api/runs", payload={"verify_only": True})
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
                    "verify_only": True,
                },
            )
        except Exception as exc:
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=False,
                error=str(exc),
            )
