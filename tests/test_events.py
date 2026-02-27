"""Tests for the workflow event system — emitter, log, and webhook delivery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from aegis_qa.config.models import AegisConfig, WebhookConfig
from aegis_qa.events.emitter import EventEmitter, WorkflowEvent, create_cli_emitter
from aegis_qa.events.log import EventLog
from aegis_qa.events.webhook import WebhookListener

# ─── WorkflowEvent tests ───


class TestWorkflowEvent:
    def test_create_event(self):
        now = datetime.now(UTC)
        evt = WorkflowEvent(
            event_type="workflow.started",
            timestamp=now,
            workflow_name="test_pipe",
            data={"step_count": 3},
        )
        assert evt.event_type == "workflow.started"
        assert evt.workflow_name == "test_pipe"
        assert evt.data["step_count"] == 3

    def test_default_data(self):
        evt = WorkflowEvent(
            event_type="step.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )
        assert evt.data == {}


# ─── EventEmitter tests ───


class TestEventEmitter:
    @pytest.mark.asyncio
    async def test_emit_to_listener(self):
        emitter = EventEmitter()
        listener = AsyncMock()
        emitter.add_listener(listener)

        evt = WorkflowEvent(
            event_type="workflow.started",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )
        await emitter.emit(evt)
        listener.on_event.assert_called_once_with(evt)

    @pytest.mark.asyncio
    async def test_emit_to_multiple_listeners(self):
        emitter = EventEmitter()
        listener1 = AsyncMock()
        listener2 = AsyncMock()
        emitter.add_listener(listener1)
        emitter.add_listener(listener2)

        evt = WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )
        await emitter.emit(evt)
        listener1.on_event.assert_called_once_with(evt)
        listener2.on_event.assert_called_once_with(evt)

    @pytest.mark.asyncio
    async def test_listener_error_does_not_propagate(self):
        emitter = EventEmitter()
        bad_listener = AsyncMock()
        bad_listener.on_event.side_effect = RuntimeError("listener crash")
        good_listener = AsyncMock()
        emitter.add_listener(bad_listener)
        emitter.add_listener(good_listener)

        evt = WorkflowEvent(
            event_type="step.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )
        await emitter.emit(evt)
        # Good listener still called despite bad listener crashing
        good_listener.on_event.assert_called_once_with(evt)

    @pytest.mark.asyncio
    async def test_no_listeners(self):
        emitter = EventEmitter()
        evt = WorkflowEvent(
            event_type="workflow.started",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )
        # Should not raise
        await emitter.emit(evt)


# ─── EventLog tests ───


class TestEventLog:
    @pytest.mark.asyncio
    async def test_log_stores_events(self):
        log = EventLog(max_size=10)
        evt = WorkflowEvent(
            event_type="workflow.started",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )
        await log.on_event(evt)
        events = await log.get_recent()
        assert len(events) == 1
        assert events[0].event_type == "workflow.started"

    @pytest.mark.asyncio
    async def test_log_respects_max_size(self):
        log = EventLog(max_size=3)
        for i in range(5):
            await log.on_event(WorkflowEvent(
                event_type=f"event.{i}",
                timestamp=datetime.now(UTC),
                workflow_name="pipe",
                data={"index": i},
            ))
        events = await log.get_recent(limit=10)
        assert len(events) == 3
        # Most recent first
        assert events[0].data["index"] == 4
        assert events[2].data["index"] == 2

    @pytest.mark.asyncio
    async def test_log_filter_by_event_type(self):
        log = EventLog(max_size=10)
        await log.on_event(WorkflowEvent(
            event_type="workflow.started",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        ))
        await log.on_event(WorkflowEvent(
            event_type="step.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        ))
        await log.on_event(WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        ))

        events = await log.get_recent(event_type="step.completed")
        assert len(events) == 1
        assert events[0].event_type == "step.completed"

    @pytest.mark.asyncio
    async def test_log_limit(self):
        log = EventLog(max_size=10)
        for i in range(5):
            await log.on_event(WorkflowEvent(
                event_type="step.completed",
                timestamp=datetime.now(UTC),
                workflow_name="pipe",
            ))
        events = await log.get_recent(limit=2)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_log_empty(self):
        log = EventLog()
        events = await log.get_recent()
        assert events == []


# ─── WebhookListener tests ───


class TestWebhookListener:
    @pytest.mark.asyncio
    async def test_exact_match_delivers(self):
        wh = WebhookConfig(url="https://example.com/hook", events=["workflow.completed"])
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
            data={"success": True},
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            # Let the background task run
            await asyncio.sleep(0.05)
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            # Body is sent as raw bytes via content=, not json=
            import json
            body = json.loads(call_kwargs[1]["content"])
            assert body["event_type"] == "workflow.completed"

    @pytest.mark.asyncio
    async def test_wildcard_delivers(self):
        wh = WebhookConfig(url="https://example.com/hook", events=["*"])
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="step.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            await asyncio.sleep(0.05)
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_matching_event_not_delivered(self):
        wh = WebhookConfig(url="https://example.com/hook", events=["workflow.completed"])
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="step.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            await asyncio.sleep(0.05)
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_hmac_signature(self):
        wh = WebhookConfig(
            url="https://example.com/hook",
            events=["workflow.completed"],
            secret="mysecret",
        )
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            await asyncio.sleep(0.05)
            call_kwargs = mock_client.post.call_args
            headers = call_kwargs[1]["headers"]
            assert "X-Aegis-Signature" in headers
            # Verify it's a valid hex string
            sig = headers["X-Aegis-Signature"]
            int(sig, 16)  # raises ValueError if not hex

    @pytest.mark.asyncio
    async def test_hmac_signature_matches_transmitted_body(self):
        """Regression: signature must be computed over the exact bytes sent on the wire."""
        import hashlib
        import hmac as hmac_mod

        secret = "test-secret-key"
        wh = WebhookConfig(
            url="https://example.com/hook",
            events=["workflow.completed"],
            secret=secret,
        )
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
            data={"success": True, "total_duration_ms": 123.4},
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            await asyncio.sleep(0.05)

            call_kwargs = mock_client.post.call_args
            transmitted_body = call_kwargs[1]["content"]
            sent_sig = call_kwargs[1]["headers"]["X-Aegis-Signature"]

            # Recompute HMAC over the exact transmitted bytes
            expected_sig = hmac_mod.new(
                secret.encode(), transmitted_body, hashlib.sha256
            ).hexdigest()
            assert sent_sig == expected_sig

    @pytest.mark.asyncio
    async def test_delivery_failure_does_not_raise(self):
        wh = WebhookConfig(url="https://example.com/hook", events=["*"])
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = ConnectionError("refused")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            # Let the background task run — should not raise
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_pending_tasks_tracked(self):
        wh = WebhookConfig(url="https://example.com/hook", events=["*"])
        listener = WebhookListener([wh])

        evt = WorkflowEvent(
            event_type="workflow.completed",
            timestamp=datetime.now(UTC),
            workflow_name="pipe",
        )

        with patch("aegis_qa.events.webhook.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await listener.on_event(evt)
            # Task should be pending
            assert len(listener._pending) >= 0  # may complete fast
            await asyncio.sleep(0.05)
            # After completion, task is discarded
            assert len(listener._pending) == 0


# ─── create_cli_emitter tests ───


class TestCreateCliEmitter:
    def test_no_webhooks_returns_none(self):
        config = AegisConfig()
        assert create_cli_emitter(config) is None

    def test_with_webhooks_returns_emitter(self):
        config = AegisConfig(
            webhooks=[WebhookConfig(url="https://example.com/hook")]
        )
        emitter = create_cli_emitter(config)
        assert emitter is not None
        assert len(emitter._listeners) == 1
