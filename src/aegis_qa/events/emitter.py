"""Event emitter, listener protocol, and workflow event dataclass."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from aegis_qa.config.models import AegisConfig

logger = logging.getLogger(__name__)


@dataclass
class WorkflowEvent:
    """A typed event emitted during pipeline execution."""

    event_type: str  # "workflow.started", "step.completed", etc.
    timestamp: datetime
    workflow_name: str
    data: dict[str, Any] = field(default_factory=dict)


class EventListener(Protocol):
    """Protocol for consuming workflow events."""

    async def on_event(self, event: WorkflowEvent) -> None: ...


class EventEmitter:
    """Collects events during pipeline execution and dispatches to listeners."""

    def __init__(self) -> None:
        self._listeners: list[EventListener] = []

    def add_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    async def emit(self, event: WorkflowEvent) -> None:
        for listener in self._listeners:
            try:
                await listener.on_event(event)
            except Exception:
                logger.exception("Event listener error")


def create_cli_emitter(config: AegisConfig) -> EventEmitter | None:
    """Create an emitter for CLI usage — webhooks only, no event log."""
    if not config.webhooks:
        return None
    from aegis_qa.events.webhook import WebhookListener

    emitter = EventEmitter()
    emitter.add_listener(WebhookListener(config.webhooks))
    return emitter
