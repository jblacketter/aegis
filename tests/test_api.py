"""Tests for FastAPI endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from aegis_qa.api.app import create_app
from aegis_qa.config.models import AegisConfig
from aegis_qa.registry.models import HealthResult, ServiceStatus
from aegis_qa.workflows.models import StepResult, WorkflowResult


@pytest.fixture()
def app(sample_config: AegisConfig):
    """Create a test app with mocked config loading."""
    with patch("aegis_qa.api.routes.health.load_config", return_value=sample_config), \
         patch("aegis_qa.api.routes.workflows.load_config", return_value=sample_config), \
         patch("aegis_qa.api.routes.portfolio.load_config", return_value=sample_config):
        # Create app without static files mount (no landing dir in test)
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from aegis_qa.api.routes import health, workflows, portfolio

        test_app = FastAPI(title="Aegis Test")
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @test_app.get("/health")
        async def healthcheck():
            return {"status": "ok"}

        test_app.include_router(health.router, prefix="/api")
        test_app.include_router(workflows.router, prefix="/api")
        test_app.include_router(portfolio.router, prefix="/api")
        yield test_app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


# ─── Health endpoint ───

class TestHealthEndpoint:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ─── Services endpoints ───

class TestServicesEndpoints:
    def test_list_services(self, client: TestClient, sample_config: AegisConfig):
        with patch("aegis_qa.api.routes.health._get_registry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.get_all_statuses = AsyncMock(return_value=[
                ServiceStatus(
                    key="qaagent", name="QA Agent", description="Test gen",
                    url="http://localhost:8080", features=["Route Discovery"],
                    health=HealthResult(healthy=True, status_code=200, latency_ms=12.5),
                ),
                ServiceStatus(
                    key="bugalizer", name="Bugalizer", description="Bug triage",
                    url="http://localhost:8090", features=["Bug Triage"],
                    health=HealthResult(healthy=False, error="Connection refused: connect"),
                ),
            ])
            resp = client.get("/api/services")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["key"] == "qaagent"
            assert data[0]["status"] == "healthy"
            assert data[1]["status"] == "unreachable"

    def test_service_health_found(self, client: TestClient):
        with patch("aegis_qa.api.routes.health._get_registry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.get_entry.return_value = True  # entry exists
            mock_instance.check_one = AsyncMock(
                return_value=HealthResult(healthy=True, status_code=200, latency_ms=5.0)
            )
            resp = client.get("/api/services/qaagent/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["healthy"] is True

    def test_service_health_not_found(self, client: TestClient):
        with patch("aegis_qa.api.routes.health._get_registry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.get_entry.return_value = None
            resp = client.get("/api/services/unknown/health")
            assert resp.status_code == 404


# ─── Workflow endpoint ───

class TestWorkflowEndpoint:
    def test_run_known_workflow(self, client: TestClient, sample_config: AegisConfig):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[
                StepResult(step_type="discover", service="QA Agent", success=True, data={"route_count": 3}),
            ],
        )
        with patch("aegis_qa.api.routes.workflows.PipelineRunner") as mock_cls:
            mock_runner = mock_cls.return_value
            mock_runner.run = AsyncMock(return_value=mock_result)
            resp = client.post("/api/workflows/full_pipeline/run")
            assert resp.status_code == 200
            data = resp.json()
            assert data["workflow_name"] == "full_pipeline"
            assert data["success"] is True

    def test_run_unknown_workflow(self, client: TestClient):
        resp = client.post("/api/workflows/nonexistent/run")
        assert resp.status_code == 404


# ─── Portfolio endpoint ───

class TestPortfolioEndpoint:
    def test_portfolio(self, client: TestClient):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Aegis"
        assert data["tagline"] == "The AI Quality Control Plane"
        assert len(data["tools"]) == 2
        assert "full_pipeline" in data["workflows"]

    def test_portfolio_includes_repo_urls(self, client: TestClient):
        resp = client.get("/api/portfolio")
        data = resp.json()
        tools_by_key = {t["key"]: t for t in data["tools"]}
        assert tools_by_key["qaagent"]["repo_url"] == "https://github.com/jblacketter/qaagent"
        assert tools_by_key["bugalizer"]["repo_url"] == "https://github.com/jblacketter/bugalizer"
        assert "docs_url" in tools_by_key["qaagent"]
