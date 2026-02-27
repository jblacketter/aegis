"""In-memory ring buffer for recent workflow events."""

from __future__ import annotations

import asyncio
from collections import deque

from aegis_qa.events.emitter import WorkflowEvent


class EventLog:
    """Bounded in-memory event log. Implements EventListener protocol."""

    def __init__(self, max_size: int = 100) -> None:
        self._events: deque[WorkflowEvent] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()

    async def on_event(self, event: WorkflowEvent) -> None:
        async with self._lock:
            self._events.append(event)

    async def get_recent(
        self, limit: int = 20, event_type: str | None = None
    ) -> list[WorkflowEvent]:
        async with self._lock:
            events: list[WorkflowEvent]
            if event_type:
                events = [e for e in self._events if e.event_type == event_type]
            else:
                events = list(self._events)
            # Most recent first
            events.reverse()
            return events[:limit]
