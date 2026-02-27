"""Tests for API key authentication middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis_qa.config.models import AegisConfig, AuthConfig
from aegis_qa.workflows.history import InMemoryHistory
from aegis_qa.workflows.models import StepResult, WorkflowResult


@pytest.fixture()
def auth_config(sample_config: AegisConfig) -> AegisConfig:
    """Sample config with API key auth enabled."""
    sample_config.auth = AuthConfig(api_key="test-secret-key")
    return sample_config


@pytest.fixture()
def auth_app(auth_config: AegisConfig):
    """Create a test app with auth enabled."""
    with (
        patch("aegis_qa.api.routes.health.load_config", return_value=auth_config),
        patch("aegis_qa.api.routes.workflows.load_config", return_value=auth_config),
        patch("aegis_qa.api.routes.portfolio.load_config", return_value=auth_config),
        patch("aegis_qa.api.routes.workflow_list.load_config", return_value=auth_config),
    ):
        from aegis_qa.api.routes import health, portfolio, workflow_list, workflows

        app = FastAPI(title="Aegis Auth Test")

        @app.get("/health")
        async def healthcheck():
            return {"status": "ok"}

        app.include_router(health.router, prefix="/api")
        app.include_router(workflow_list.router, prefix="/api")
        app.include_router(workflows.router, prefix="/api")
        app.include_router(portfolio.router, prefix="/api")

        app.state.config = auth_config
        app.state.history = InMemoryHistory()

        yield app


@pytest.fixture()
def auth_client(auth_app) -> TestClient:
    return TestClient(auth_app)


@pytest.fixture()
def noauth_app(sample_config: AegisConfig):
    """Create a test app with auth disabled (no API key)."""
    with (
        patch("aegis_qa.api.routes.health.load_config", return_value=sample_config),
        patch("aegis_qa.api.routes.workflows.load_config", return_value=sample_config),
        patch("aegis_qa.api.routes.portfolio.load_config", return_value=sample_config),
        patch("aegis_qa.api.routes.workflow_list.load_config", return_value=sample_config),
    ):
        from aegis_qa.api.routes import health, portfolio, workflow_list, workflows

        app = FastAPI(title="Aegis NoAuth Test")

        @app.get("/health")
        async def healthcheck():
            return {"status": "ok"}

        app.include_router(health.router, prefix="/api")
        app.include_router(workflow_list.router, prefix="/api")
        app.include_router(workflows.router, prefix="/api")
        app.include_router(portfolio.router, prefix="/api")

        app.state.config = sample_config
        app.state.history = InMemoryHistory()

        yield app


@pytest.fixture()
def noauth_client(noauth_app) -> TestClient:
    return TestClient(noauth_app)


class TestAuthEnabled:
    def test_run_without_key_returns_401(self, auth_client: TestClient):
        resp = auth_client.post("/api/workflows/full_pipeline/run")
        assert resp.status_code == 401

    def test_run_with_wrong_key_returns_401(self, auth_client: TestClient):
        resp = auth_client.post(
            "/api/workflows/full_pipeline/run",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_run_with_correct_key_succeeds(self, auth_client: TestClient, auth_config: AegisConfig):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[StepResult(step_type="discover", service="QA Agent", success=True)],
        )
        with patch("aegis_qa.api.routes.workflows.PipelineRunner") as mock_cls:
            mock_runner = mock_cls.return_value
            mock_runner.run = AsyncMock(return_value=mock_result)
            resp = auth_client.post(
                "/api/workflows/full_pipeline/run",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_read_endpoints_dont_require_auth(self, auth_client: TestClient):
        """GET endpoints should work without API key even when auth is enabled."""
        resp = auth_client.get("/api/workflows")
        assert resp.status_code == 200

        resp = auth_client.get("/api/workflows/full_pipeline")
        assert resp.status_code == 200

        resp = auth_client.get("/api/portfolio")
        assert resp.status_code == 200


class TestAuthDisabled:
    def test_run_without_key_succeeds(self, noauth_client: TestClient):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[StepResult(step_type="discover", service="QA Agent", success=True)],
        )
        with patch("aegis_qa.api.routes.workflows.PipelineRunner") as mock_cls:
            mock_runner = mock_cls.return_value
            mock_runner.run = AsyncMock(return_value=mock_result)
            resp = noauth_client.post("/api/workflows/full_pipeline/run")
            assert resp.status_code == 200
