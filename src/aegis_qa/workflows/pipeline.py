"""Pipeline runner for workflow execution with retry, timeout, and parallel support."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from aegis_qa.config.models import AegisConfig, WorkflowStepDef
from aegis_qa.events.emitter import EventEmitter, WorkflowEvent
from aegis_qa.registry.registry import ServiceRegistry
from aegis_qa.workflows.history import ExecutionHistory, ExecutionRecord, StepRecord
from aegis_qa.workflows.models import StepResult, WorkflowResult

logger = logging.getLogger(__name__)

CONDITIONS: dict[str, Callable[[list[StepResult]], bool]] = {
    "has_failures": lambda results: any(r.has_failures for r in results),
    "on_success": lambda results: all(r.success for r in results) if results else True,
    "on_failure": lambda results: any(not r.success for r in results),
    "always": lambda results: True,
}


class PipelineRunner:
    """Executes workflow steps with retry, timeout, parallel batching, and history."""

    def __init__(
        self,
        config: AegisConfig,
        history: ExecutionHistory | None = None,
        emitter: EventEmitter | None = None,
    ) -> None:
        self._config = config
        self._registry = ServiceRegistry(config)
        self._history = history
        self._emitter = emitter

    def _should_skip(self, condition: str | None, context: dict[str, Any]) -> bool:
        """Evaluate a step condition. Returns True if the step should be skipped."""
        if condition is None:
            return False
        step_results = [r for r in context.get("step_results", []) if isinstance(r, StepResult)]
        evaluator = CONDITIONS.get(condition)
        if evaluator is None:
            logger.warning("Unknown condition %r — running step anyway", condition)
            return False
        return not evaluator(step_results)

    async def _execute_with_retry(
        self,
        step: Any,
        step_def: WorkflowStepDef,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute a step with runner-level retry and timeout."""
        attempts: list[dict[str, Any]] = []
        max_attempts = step_def.retries + 1
        last_result: StepResult | None = None

        for attempt in range(max_attempts):
            start = time.monotonic()
            try:
                step_result = await asyncio.wait_for(
                    step.execute(context),
                    timeout=step_def.timeout,
                )
            except TimeoutError:
                elapsed = (time.monotonic() - start) * 1000
                step_result = StepResult(
                    step_type=step_def.type,
                    service=step_def.service,
                    success=False,
                    error=f"Step timed out after {step_def.timeout}s",
                    duration_ms=elapsed,
                )
            else:
                elapsed = (time.monotonic() - start) * 1000
                step_result.duration_ms = elapsed

            attempts.append({
                "attempt": attempt + 1,
                "success": step_result.success,
                "error": step_result.error,
                "duration_ms": step_result.duration_ms,
            })
            last_result = step_result

            if step_result.success or attempt >= max_attempts - 1:
                break

            delay = (2**attempt) * step_def.retry_delay
            logger.info(
                "Step %s/%s failed (attempt %d/%d), retrying in %.1fs",
                step_def.type,
                step_def.service,
                attempt + 1,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)

        assert last_result is not None
        last_result.attempts = attempts
        return last_result

    async def _resolve_and_execute(
        self,
        step_def: WorkflowStepDef,
        context: dict[str, Any],
    ) -> StepResult:
        """Resolve a step definition to a step class, then execute with retry."""
        if self._should_skip(step_def.condition, context):
            return StepResult(
                step_type=step_def.type,
                service=step_def.service,
                success=True,
                skipped=True,
                data={"message": f"Skipped: condition '{step_def.condition}' not met"},
            )

        entry = self._registry.get_entry(step_def.service)
        if entry is None:
            return StepResult(
                step_type=step_def.type,
                service=step_def.service,
                success=False,
                error=f"Unknown service: {step_def.service}",
            )

        from aegis_qa.workflows.steps import STEP_REGISTRY

        step_cls = STEP_REGISTRY.get(step_def.type)
        if step_cls is None:
            return StepResult(
                step_type=step_def.type,
                service=step_def.service,
                success=False,
                error=f"Unknown step type: {step_def.type}",
            )

        step = step_cls(entry)
        return await self._execute_with_retry(step, step_def, context)

    async def _emit(self, event: WorkflowEvent) -> None:
        """Emit an event if an emitter is configured."""
        if self._emitter is not None:
            await self._emitter.emit(event)

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

        started_at = datetime.now(UTC)
        result = WorkflowResult(workflow_name=workflow_name)
        context: dict[str, Any] = {"step_results": []}

        # Emit workflow.started
        await self._emit(WorkflowEvent(
            event_type="workflow.started",
            timestamp=started_at,
            workflow_name=workflow_name,
            data={"step_count": len(workflow.steps)},
        ))

        # Group consecutive parallel steps into batches
        batches: list[tuple[str, list[WorkflowStepDef]]] = []
        current_parallel: list[WorkflowStepDef] = []

        for step_def in workflow.steps:
            if step_def.parallel:
                current_parallel.append(step_def)
            else:
                if current_parallel:
                    batches.append(("parallel", current_parallel))
                    current_parallel = []
                batches.append(("sequential", [step_def]))
        if current_parallel:
            batches.append(("parallel", current_parallel))

        first_failure_emitted = False
        for batch_type, step_defs in batches:
            if batch_type == "sequential":
                step_result = await self._resolve_and_execute(step_defs[0], context)
                result.steps.append(step_result)
                context["step_results"].append(step_result)
                await self._emit_step_events(step_result, workflow_name, first_failure_emitted)
                if not step_result.success and not step_result.skipped and not first_failure_emitted:
                    first_failure_emitted = True
            else:
                # Parallel batch — run all steps concurrently
                tasks = [self._resolve_and_execute(sd, context) for sd in step_defs]
                batch_results = await asyncio.gather(*tasks)
                for step_result in batch_results:
                    result.steps.append(step_result)
                    context["step_results"].append(step_result)
                    await self._emit_step_events(step_result, workflow_name, first_failure_emitted)
                    if not step_result.success and not step_result.skipped and not first_failure_emitted:
                        first_failure_emitted = True

        completed_at = datetime.now(UTC)
        total_duration_ms = (completed_at - started_at).total_seconds() * 1000
        steps_passed = sum(1 for s in result.steps if s.success and not s.skipped)
        steps_failed = sum(1 for s in result.steps if not s.success and not s.skipped)

        # Emit workflow.completed
        await self._emit(WorkflowEvent(
            event_type="workflow.completed",
            timestamp=completed_at,
            workflow_name=workflow_name,
            data={
                "success": result.success,
                "total_duration_ms": total_duration_ms,
                "steps_passed": steps_passed,
                "steps_failed": steps_failed,
            },
        ))

        # Record execution history
        if self._history is not None:
            record = ExecutionRecord(
                workflow_name=workflow_name,
                started_at=started_at,
                completed_at=completed_at,
                success=result.success,
                steps=[
                    StepRecord(
                        step_type=s.step_type,
                        service=s.service,
                        success=s.success,
                        skipped=s.skipped,
                        duration_ms=s.duration_ms,
                        error=s.error,
                        attempts=len(s.attempts) if s.attempts else 1,
                    )
                    for s in result.steps
                ],
            )
            await self._history.record(record)

        return result

    async def _emit_step_events(
        self,
        step_result: StepResult,
        workflow_name: str,
        first_failure_emitted: bool,
    ) -> None:
        """Emit step.completed and optionally failure.detected events."""
        now = datetime.now(UTC)
        await self._emit(WorkflowEvent(
            event_type="step.completed",
            timestamp=now,
            workflow_name=workflow_name,
            data={
                "step_type": step_result.step_type,
                "service": step_result.service,
                "success": step_result.success,
                "duration_ms": step_result.duration_ms,
            },
        ))
        if not step_result.success and not step_result.skipped and not first_failure_emitted:
            await self._emit(WorkflowEvent(
                event_type="failure.detected",
                timestamp=now,
                workflow_name=workflow_name,
                data={
                    "step_type": step_result.step_type,
                    "service": step_result.service,
                    "error": step_result.error or "Unknown error",
                },
            ))
