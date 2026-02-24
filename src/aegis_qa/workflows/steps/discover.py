"""Route discovery step — calls qaagent to discover routes."""

from __future__ import annotations

from typing import Any, Dict

from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class DiscoverStep(BaseStep):
    step_type = "discover"

    async def execute(self, context: Dict[str, Any]) -> StepResult:
        try:
            data = await self._get("/api/routes")
            routes = data.get("routes", [])
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=True,
                data={"routes": routes, "route_count": len(routes)},
            )
        except Exception as exc:
            return StepResult(
                step_type=self.step_type,
                service=self.service_entry.name,
                success=False,
                error=str(exc),
            )
