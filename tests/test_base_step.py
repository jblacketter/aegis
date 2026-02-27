"""Tests for BaseStep helpers (_get, _post, _headers)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aegis_qa.config.models import ServiceEntry
from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.base import BaseStep


class ConcreteStep(BaseStep):
    """Concrete subclass for testing abstract BaseStep."""

    step_type = "test_concrete"

    async def execute(self, context):
        return StepResult(step_type=self.step_type, service=self.service_entry.name, success=True)


class TestBaseStepInit:
    def test_basic_init(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)
        assert step.base_url == "http://localhost:8080"
        assert step._api_key == ""

    def test_url_trailing_slash_stripped(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080/")
        step = ConcreteStep(entry)
        assert step.base_url == "http://localhost:8080"

    def test_api_key_from_env(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080", api_key_env="TEST_API_KEY")
        with patch.dict(os.environ, {"TEST_API_KEY": "secret123"}):
            step = ConcreteStep(entry)
            assert step._api_key == "secret123"

    def test_api_key_missing_env(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080", api_key_env="MISSING_KEY")
        with patch.dict(os.environ, {}, clear=True):
            step = ConcreteStep(entry)
            assert step._api_key == ""


class TestHeaders:
    def test_default_headers(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)
        headers = step._headers()
        assert headers["Content-Type"] == "application/json"
        assert "X-API-Key" not in headers

    def test_headers_with_api_key(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080", api_key_env="TEST_KEY")
        with patch.dict(os.environ, {"TEST_KEY": "mykey"}):
            step = ConcreteStep(entry)
            headers = step._headers()
            assert headers["X-API-Key"] == "mykey"


def _make_mock_response(json_data=None, raise_error=None):
    """Create a MagicMock httpx response (json/raise_for_status are sync in httpx)."""
    resp = MagicMock()
    if json_data is not None:
        resp.json.return_value = json_data
    if raise_error:
        resp.raise_for_status.side_effect = raise_error
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_mock_client(method="get", response=None):
    """Create an AsyncMock httpx client with the given method response."""
    client = AsyncMock()
    getattr(client, method).return_value = response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


class TestGet:
    @pytest.mark.asyncio
    async def test_get_success(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)
        resp = _make_mock_response(json_data={"data": "value"})
        client = _make_mock_client("get", resp)

        with patch("httpx.AsyncClient", return_value=client):
            result = await step._get("/api/test")
            assert result == {"data": "value"}
            client.get.assert_called_once_with(
                "http://localhost:8080/api/test",
                headers=step._headers(),
            )

    @pytest.mark.asyncio
    async def test_get_with_custom_timeout(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)
        resp = _make_mock_response(json_data={})
        client = _make_mock_client("get", resp)

        with patch("httpx.AsyncClient", return_value=client) as mock_cls:
            await step._get("/api/test", timeout=60.0)
            mock_cls.assert_called_once_with(timeout=60.0)

    @pytest.mark.asyncio
    async def test_get_http_error(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)

        mock_request = httpx.Request("GET", "http://localhost:8080/api/missing")
        mock_http_resp = httpx.Response(404, request=mock_request)
        error = httpx.HTTPStatusError("Not Found", request=mock_request, response=mock_http_resp)

        resp = _make_mock_response(raise_error=error)
        client = _make_mock_client("get", resp)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.HTTPStatusError):
                await step._get("/api/missing")


class TestPost:
    @pytest.mark.asyncio
    async def test_post_success(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)
        resp = _make_mock_response(json_data={"id": "123"})
        client = _make_mock_client("post", resp)

        with patch("httpx.AsyncClient", return_value=client):
            result = await step._post("/api/submit", payload={"data": "test"})
            assert result == {"id": "123"}
            client.post.assert_called_once_with(
                "http://localhost:8080/api/submit",
                json={"data": "test"},
                headers=step._headers(),
            )

    @pytest.mark.asyncio
    async def test_post_with_custom_timeout(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)
        resp = _make_mock_response(json_data={})
        client = _make_mock_client("post", resp)

        with patch("httpx.AsyncClient", return_value=client) as mock_cls:
            await step._post("/api/submit", payload={}, timeout=90.0)
            mock_cls.assert_called_once_with(timeout=90.0)

    @pytest.mark.asyncio
    async def test_post_http_error(self):
        entry = ServiceEntry(name="TestSvc", url="http://localhost:8080")
        step = ConcreteStep(entry)

        mock_request = httpx.Request("POST", "http://localhost:8080/api/submit")
        mock_http_resp = httpx.Response(500, request=mock_request)
        error = httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_http_resp)

        resp = _make_mock_response(raise_error=error)
        client = _make_mock_client("post", resp)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.HTTPStatusError):
                await step._post("/api/submit", payload={})
