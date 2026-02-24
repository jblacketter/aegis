"""Bug submission step — sends failures to bugalizer."""

from __future__ import annotations

from typing import Any, Dict, List

from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class SubmitBugsStep(BaseStep):
    step_type = "submit_bugs"

    async def execute(self, context: Dict[str, Any]) -> StepResult:
        failures = self._collect_failures(context)
        if not failures:
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=True,
                data={"submitted": 0, "message": "No failures to submit"},
            )
        try:
            payload = {"failures": failures}
            data = await self._post("/api/v1/reports", payload=payload)
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=True,
                data={"submitted": len(failures), "response": data},
            )
        except Exception as exc:
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=False,
                error=str(exc),
            )

    def _collect_failures(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gather failures from prior step results stored in context."""
        failures: List[Dict[str, Any]] = []
        for step_result in context.get("step_results", []):
            if isinstance(step_result, StepResult):
                failures.extend(step_result.data.get("failures", []))
        return failures
