"""Sequential pipeline runner for workflow execution."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from aegis_qa.config.models import AegisConfig, WorkflowDef
from aegis_qa.registry.registry import ServiceRegistry
from aegis_qa.workflows.models import StepResult, WorkflowResult

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Executes workflow steps sequentially with conditional logic."""

    def __init__(self, config: AegisConfig) -> None:
        self._config = config
        self._registry = ServiceRegistry(config)

    def _should_skip(self, condition: Optional[str], context: Dict[str, Any]) -> bool:
        """Evaluate a step condition. Returns True if the step should be skipped."""
        if condition is None:
            return False
        if condition == "has_failures":
            step_results = context.get("step_results", [])
            return not any(
                isinstance(sr, StepResult) and sr.has_failures
                for sr in step_results
            )
        logger.warning("Unknown condition %r — running step anyway", condition)
        return False

    async def run(self, workflow_name: str) -> WorkflowResult:
        """Execute a named workflow, returning structured results."""
        workflow = self._config.workflows.get(workflow_name)
        if workflow is None:
            return WorkflowResult(
                workflow_name=workflow_name,
                steps=[
                    StepResult(
                        step_type="error",
                        service="aegis",
                        success=False,
                        error=f"Unknown workflow: {workflow_name}",
                    )
                ],
            )

        result = WorkflowResult(workflow_name=workflow_name)
        context: Dict[str, Any] = {"step_results": []}

        for step_def in workflow.steps:
            if self._should_skip(step_def.condition, context):
                result.steps.append(
                    StepResult(
                        step_type=step_def.type,
                        service=step_def.service,
                        success=True,
                        skipped=True,
                        data={"message": f"Skipped: condition '{step_def.condition}' not met"},
                    )
                )
                continue

            entry = self._registry.get_entry(step_def.service)
            if entry is None:
                result.steps.append(
                    StepResult(
                        step_type=step_def.type,
                        service=step_def.service,
                        success=False,
                        error=f"Unknown service: {step_def.service}",
                    )
                )
                continue

            from aegis_qa.workflows.steps import STEP_REGISTRY

            step_cls = STEP_REGISTRY.get(step_def.type)
            if step_cls is None:
                result.steps.append(
                    StepResult(
                        step_type=step_def.type,
                        service=step_def.service,
                        success=False,
                        error=f"Unknown step type: {step_def.type}",
                    )
                )
                continue

            step = step_cls(entry)
            step_result = await step.execute(context)
            result.steps.append(step_result)
            context["step_results"].append(step_result)

        return result
