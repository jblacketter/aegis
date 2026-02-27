"""Integration tests — full API lifecycle with mocked downstream services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis_qa.config.models import AegisConfig
from aegis_qa.events.emitter import EventEmitter
from aegis_qa.events.log import EventLog
from aegis_qa.registry.models import HealthResult, ServiceStatus
from aegis_qa.workflows.history import InMemoryHistory
from aegis_qa.workflows.models import StepResult


@pytest.fixture()
def integration_app(sample_config: AegisConfig):
    """Create a full test app with all routes registered."""
    with (
        patch("aegis_qa.api.routes.health.load_config", return_value=sample_config),
        patch("aegis_qa.api.routes.workflows.load_config", return_value=sample_config),
        patch("aegis_qa.api.routes.portfolio.load_config", return_value=sample_config),
        patch("aegis_qa.api.routes.workflow_list.load_config", return_value=sample_config),
    ):
        from aegis_qa.api.routes import health, portfolio, workflow_list, workflows

        app = FastAPI(title="Aegis Integration Test")

        @app.get("/health")
        async def healthcheck():
            return {"status": "ok"}

        app.include_router(health.router, prefix="/api")
        app.include_router(workflow_list.router, prefix="/api")
        app.include_router(workflows.router, prefix="/api")
        app.include_router(portfolio.router, prefix="/api")

        # Wire app.state for the new DI pattern
        event_log = EventLog()
        emitter = EventEmitter()
        emitter.add_listener(event_log)
        app.state.config = sample_config
        app.state.history = InMemoryHistory()
        app.state.event_log = event_log
        app.state.emitter = emitter

        yield app


@pytest.fixture()
def integration_client(integration_app) -> TestClient:
    return TestClient(integration_app)


class TestFullLifecycle:
    """Integration: list services → list workflows → run workflow → check portfolio."""

    def test_health_check(self, integration_client: TestClient):
        resp = integration_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_list_services_then_workflows(self, integration_client: TestClient):
        """List services and workflows in sequence."""
        with patch("aegis_qa.api.routes.health._get_registry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.get_all_statuses = AsyncMock(
                return_value=[
                    ServiceStatus(
                        key="qaagent",
                        name="QA Agent",
                        description="Route discovery",
                        url="http://localhost:8080",
                        features=["Route Discovery"],
                        health=HealthResult(healthy=True, status_code=200, latency_ms=5.0),
                    ),
                ]
            )
            services_resp = integration_client.get("/api/services")
            assert services_resp.status_code == 200
            services = services_resp.json()
            assert len(services) >= 1

        workflows_resp = integration_client.get("/api/workflows")
        assert workflows_resp.status_code == 200
        workflows = workflows_resp.json()
        assert len(workflows) == 1
        assert workflows[0]["key"] == "full_pipeline"

    def test_run_workflow_then_check_portfolio(self, integration_client: TestClient):
        """Run a workflow then verify portfolio still works."""
        mock_discover = StepResult(
            step_type="discover", service="QA Agent", success=True, data={"routes": ["/api/x"], "route_count": 1}
        )
        mock_test = StepResult(
            step_type="test",
            service="QA Agent",
            success=True,
            data={"total": 5, "passed": 5, "failed": 0, "failures": []},
        )
        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", new_callable=AsyncMock) as m_disc,
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", new_callable=AsyncMock) as m_test,
        ):
            m_disc.return_value = mock_discover
            m_test.return_value = mock_test
            run_resp = integration_client.post("/api/workflows/full_pipeline/run")
            assert run_resp.status_code == 200
            data = run_resp.json()
            assert data["success"] is True

        # Portfolio should still work
        portfolio_resp = integration_client.get("/api/portfolio")
        assert portfolio_resp.status_code == 200
        assert portfolio_resp.json()["name"] == "Aegis"

    def test_workflow_detail_endpoint(self, integration_client: TestClient):
        """Get a single workflow definition with full details."""
        resp = integration_client.get("/api/workflows/full_pipeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Full QA Pipeline"
        assert len(data["steps"]) == 3
        # Verify the step fields include retry/parallel config
        step = data["steps"][0]
        assert "parallel" in step
        assert "retries" in step
        assert "timeout" in step

    def test_run_then_history_non_empty(self, integration_app, integration_client: TestClient):
        """History endpoint returns records after a successful workflow run."""
        mock_discover = StepResult(
            step_type="discover", service="QA Agent", success=True, data={"routes": [], "route_count": 0}
        )
        mock_test = StepResult(
            step_type="test", service="QA Agent", success=True,
            data={"total": 1, "passed": 1, "failed": 0, "failures": []},
        )
        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", new_callable=AsyncMock) as m_disc,
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", new_callable=AsyncMock) as m_test,
        ):
            m_disc.return_value = mock_discover
            m_test.return_value = mock_test
            run_resp = integration_client.post("/api/workflows/full_pipeline/run")
            assert run_resp.status_code == 200
            assert run_resp.json()["success"] is True

        # Per-workflow history should contain exactly one record
        hist_resp = integration_client.get("/api/workflows/full_pipeline/history")
        assert hist_resp.status_code == 200
        records = hist_resp.json()
        assert len(records) == 1
        assert records[0]["workflow_name"] == "full_pipeline"
        assert records[0]["success"] is True

        # Recent history (top-level) should also have it
        recent_resp = integration_client.get("/api/history")
        assert recent_resp.status_code == 200
        recent = recent_resp.json()
        assert len(recent) == 1
        assert recent[0]["workflow_name"] == "full_pipeline"

    def test_workflow_not_found(self, integration_client: TestClient):
        resp = integration_client.get("/api/workflows/nonexistent")
        assert resp.status_code == 404

    def test_run_unknown_workflow(self, integration_client: TestClient):
        resp = integration_client.post("/api/workflows/nonexistent/run")
        assert resp.status_code == 404


    def test_run_then_events_non_empty(self, integration_app, integration_client: TestClient):
        """Events endpoint returns events after a successful workflow run."""
        mock_discover = StepResult(
            step_type="discover", service="QA Agent", success=True, data={"routes": [], "route_count": 0}
        )
        mock_test = StepResult(
            step_type="test", service="QA Agent", success=True,
            data={"total": 1, "passed": 1, "failed": 0, "failures": []},
        )
        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", new_callable=AsyncMock) as m_disc,
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", new_callable=AsyncMock) as m_test,
        ):
            m_disc.return_value = mock_discover
            m_test.return_value = mock_test
            run_resp = integration_client.post("/api/workflows/full_pipeline/run")
            assert run_resp.status_code == 200

        # Events should include workflow.started, step.completed, workflow.completed
        events_resp = integration_client.get("/api/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        event_types = [e["event_type"] for e in events]
        assert "workflow.started" in event_types
        assert "workflow.completed" in event_types
        assert "step.completed" in event_types

    def test_events_filter_by_type(self, integration_app, integration_client: TestClient):
        """Events endpoint filters by event_type query param."""
        mock_discover = StepResult(
            step_type="discover", service="QA Agent", success=True, data={"routes": [], "route_count": 0}
        )
        mock_test = StepResult(
            step_type="test", service="QA Agent", success=True,
            data={"total": 1, "passed": 1, "failed": 0, "failures": []},
        )
        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", new_callable=AsyncMock) as m_disc,
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", new_callable=AsyncMock) as m_test,
        ):
            m_disc.return_value = mock_discover
            m_test.return_value = mock_test
            integration_client.post("/api/workflows/full_pipeline/run")

        # Filter for only workflow.completed events
        events_resp = integration_client.get("/api/events?event_type=workflow.completed")
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert all(e["event_type"] == "workflow.completed" for e in events)
        assert len(events) == 1


class TestErrorPaths:
    """Integration tests for error handling."""

    def test_service_health_unknown(self, integration_client: TestClient):
        with patch("aegis_qa.api.routes.health._get_registry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.get_entry.return_value = None
            resp = integration_client.get("/api/services/unknown/health")
            assert resp.status_code == 404

    def test_workflow_history_unknown(self, integration_client: TestClient):
        resp = integration_client.get("/api/workflows/nonexistent/history")
        assert resp.status_code == 404
