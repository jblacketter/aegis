"""Execution history protocol and in-memory implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class StepRecord:
    """Record of a single step execution within a workflow run."""

    step_type: str
    service: str
    success: bool
    skipped: bool = False
    duration_ms: float | None = None
    error: str | None = None
    attempts: int = 1


@dataclass
class ExecutionRecord:
    """Record of a single workflow execution."""

    workflow_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    steps: list[StepRecord] = field(default_factory=list)
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        duration_ms: float | None = None
        if self.completed_at and self.started_at:
            duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

        return {
            "workflow_name": self.workflow_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "duration_ms": duration_ms,
            "step_count": len(self.steps),
            "steps": [
                {
                    "step_type": s.step_type,
                    "service": s.service,
                    "success": s.success,
                    "skipped": s.skipped,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                    "attempts": s.attempts,
                }
                for s in self.steps
            ],
        }


@runtime_checkable
class ExecutionHistoryBackend(Protocol):
    """Protocol for execution history backends."""

    async def record(self, execution: ExecutionRecord) -> None: ...
    async def get_history(self, workflow_name: str) -> list[ExecutionRecord]: ...
    async def get_all(self) -> dict[str, list[ExecutionRecord]]: ...
    async def get_recent(self, limit: int = 10) -> list[ExecutionRecord]: ...


class InMemoryHistory:
    """In-memory execution log. Thread-safe via asyncio lock."""

    def __init__(self) -> None:
        self._records: dict[str, list[ExecutionRecord]] = {}
        self._lock = asyncio.Lock()

    async def record(self, execution: ExecutionRecord) -> None:
        """Store an execution record."""
        async with self._lock:
            if execution.workflow_name not in self._records:
                self._records[execution.workflow_name] = []
            self._records[execution.workflow_name].append(execution)

    async def get_history(self, workflow_name: str) -> list[ExecutionRecord]:
        """Get execution history for a workflow."""
        async with self._lock:
            return list(self._records.get(workflow_name, []))

    async def get_all(self) -> dict[str, list[ExecutionRecord]]:
        """Get all execution history."""
        async with self._lock:
            return {k: list(v) for k, v in self._records.items()}

    async def get_recent(self, limit: int = 10) -> list[ExecutionRecord]:
        """Get the most recent execution records across all workflows."""
        async with self._lock:
            all_records: list[ExecutionRecord] = []
            for records in self._records.values():
                all_records.extend(records)
            all_records.sort(key=lambda r: r.started_at, reverse=True)
            return all_records[:limit]


# Backwards-compatible alias
ExecutionHistory = InMemoryHistory
