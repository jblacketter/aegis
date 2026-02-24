"""Base class for workflow steps."""

from __future__ import annotations

import abc
import os
from typing import Any

from aegis_qa.config.models import ServiceEntry
from aegis_qa.workflows.models import StepResult


class BaseStep(abc.ABC):
    """Abstract base for a workflow step that calls a downstream service."""

    step_type: str = "base"

    def __init__(self, service_entry: ServiceEntry) -> None:
        self.service_entry = service_entry
        self.base_url = service_entry.url.rstrip("/")
        self._api_key = os.environ.get(service_entry.api_key_env, "") if service_entry.api_key_env else ""

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    @abc.abstractmethod
    async def execute(self, context: dict[str, Any]) -> StepResult:
        """Execute this step, returning a StepResult."""

    async def _post(self, path: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        import httpx

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def _get(self, path: str, timeout: float = 30.0) -> dict[str, Any]:
        import httpx

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
