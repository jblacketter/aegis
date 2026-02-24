"""Verification step — placeholder for future implementation."""

from __future__ import annotations

from typing import Any

from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class VerifyStep(BaseStep):
    step_type = "verify"

    async def execute(self, context: dict[str, Any]) -> StepResult:
        return StepResult(
            step_type=self.step_type,
            service=self.service_entry.name,
            success=True,
            data={"message": "Verification step placeholder — not yet implemented"},
            skipped=True,
        )
