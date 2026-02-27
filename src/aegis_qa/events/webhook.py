"""Fire-and-forget webhook delivery listener."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import TYPE_CHECKING

import httpx

from aegis_qa.events.emitter import WorkflowEvent

if TYPE_CHECKING:
    from aegis_qa.config.models import WebhookConfig

logger = logging.getLogger(__name__)


class WebhookListener:
    """Delivers events to configured webhook URLs. Implements EventListener protocol."""

    def __init__(self, webhooks: list[WebhookConfig]) -> None:
        self._webhooks = webhooks
        self._pending: set[asyncio.Task[None]] = set()

    async def on_event(self, event: WorkflowEvent) -> None:
        for wh in self._webhooks:
            if event.event_type in wh.events or "*" in wh.events:
                task = asyncio.create_task(
                    self._deliver(wh, event),
                    name=f"webhook-{wh.url}",
                )
                self._pending.add(task)
                task.add_done_callback(self._pending.discard)

    async def _deliver(self, wh: WebhookConfig, event: WorkflowEvent) -> None:
        """Fire-and-forget delivery. All exceptions caught and logged."""
        try:
            payload = {
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "workflow_name": event.workflow_name,
                "data": event.data,
            }
            # Serialize once — sign and send the exact same bytes
            body_bytes = json.dumps(payload).encode()
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if wh.secret:
                sig = hmac.new(
                    wh.secret.encode(), body_bytes, hashlib.sha256
                ).hexdigest()
                headers["X-Aegis-Signature"] = sig
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(wh.url, content=body_bytes, headers=headers)
        except Exception:
            logger.exception(
                "Webhook delivery failed for %s (event: %s)",
                wh.url,
                event.event_type,
            )
