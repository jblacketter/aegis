"""Tests for service registry and health checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from aegis_qa.config.models import AegisConfig, ServiceEntry
from aegis_qa.registry.health import check_all_services, check_health
from aegis_qa.registry.models import HealthResult, ServiceStatus
from aegis_qa.registry.registry import ServiceRegistry

# ─── HealthResult tests ───


class TestHealthResult:
    def test_healthy(self):
        r = HealthResult(healthy=True, status_code=200, latency_ms=15.3)
        assert r.healthy
        assert r.error is None

    def test_unhealthy(self):
        r = HealthResult(healthy=False, error="Connection refused: ...")
        assert not r.healthy


class TestServiceStatus:
    def test_status_label_healthy(self):
        s = ServiceStatus(
            key="qa",
            name="QA",
            description="",
            url="http://x",
            health=HealthResult(healthy=True, status_code=200),
        )
        assert s.status_label == "healthy"

    def test_status_label_unreachable(self):
        s = ServiceStatus(
            key="qa",
            name="QA",
            description="",
            url="http://x",
            health=HealthResult(healthy=False, error="Connection refused: connect error"),
        )
        assert s.status_label == "unreachable"

    def test_status_label_unhealthy(self):
        s = ServiceStatus(
            key="qa",
            name="QA",
            description="",
            url="http://x",
            health=HealthResult(healthy=False, status_code=500, error="Server error"),
        )
        assert s.status_label == "unhealthy"

    def test_status_label_unknown(self):
        s = ServiceStatus(key="qa", name="QA", description="", url="http://x")
        assert s.status_label == "unknown"


# ─── check_health tests ───


class TestCheckHealth:
    @pytest.mark.asyncio
    async def test_healthy_service(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        mock_response = httpx.Response(200, json={"status": "ok"})
        with patch("aegis_qa.registry.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_health(entry)
            assert result.healthy
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_unhealthy_service(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        mock_response = httpx.Response(500)
        with patch("aegis_qa.registry.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_health(entry)
            assert not result.healthy
            assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_connection_error(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        with patch("aegis_qa.registry.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_health(entry)
            assert not result.healthy
            assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_timeout(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        with patch("aegis_qa.registry.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_health(entry)
            assert not result.healthy
            assert result.error == "Timeout"


# ─── check_all_services tests ───


class TestCheckAllServices:
    @pytest.mark.asyncio
    async def test_concurrent_checks(self):
        services = {
            "qa": ServiceEntry(name="QA", url="http://localhost:8080"),
            "bug": ServiceEntry(name="Bug", url="http://localhost:8090"),
        }
        with patch("aegis_qa.registry.health.check_health") as mock_check:
            mock_check.return_value = HealthResult(healthy=True, status_code=200)
            results = await check_all_services(services)
            assert len(results) == 2
            assert results["qa"].healthy
            assert results["bug"].healthy


# ─── ServiceRegistry tests ───


class TestServiceRegistry:
    def test_service_keys(self, sample_config: AegisConfig):
        reg = ServiceRegistry(sample_config)
        assert set(reg.service_keys) == {"qaagent", "bugalizer"}

    def test_get_entry(self, sample_config: AegisConfig):
        reg = ServiceRegistry(sample_config)
        entry = reg.get_entry("qaagent")
        assert entry is not None
        assert entry.name == "QA Agent"

    def test_get_entry_unknown(self, sample_config: AegisConfig):
        reg = ServiceRegistry(sample_config)
        assert reg.get_entry("unknown") is None

    @pytest.mark.asyncio
    async def test_check_one_unknown(self, sample_config: AegisConfig):
        reg = ServiceRegistry(sample_config)
        result = await reg.check_one("nonexistent")
        assert not result.healthy
        assert "Unknown service" in result.error

    @pytest.mark.asyncio
    async def test_get_all_statuses(self, sample_config: AegisConfig):
        reg = ServiceRegistry(sample_config)
        with patch.object(reg, "check_all") as mock_all:
            mock_all.return_value = {
                "qaagent": HealthResult(healthy=True, status_code=200),
                "bugalizer": HealthResult(healthy=False, error="Connection refused: connect"),
            }
            statuses = await reg.get_all_statuses()
            assert len(statuses) == 2
            names = {s.name for s in statuses}
            assert names == {"QA Agent", "Bugalizer"}
