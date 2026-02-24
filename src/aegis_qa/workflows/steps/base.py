"""Base class for workflow steps."""

from __future__ import annotations

import abc
import os
from typing import Any, Dict, List

from aegis_qa.config.models import ServiceEntry
from aegis_qa.workflows.models import StepResult


class BaseStep(abc.ABC):
    """Abstract base for a workflow step that calls a downstream service."""

    step_type: str = "base"

    def __init__(self, service_entry: ServiceEntry) -> None:
        self.service_entry = service_entry
        self.base_url = service_entry.url.rstrip("/")
        self._api_key = os.environ.get(service_entry.api_key_env, "") if service_entry.api_key_env else ""

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    @abc.abstractmethod
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        """Execute this step, returning a StepResult."""

    async def _post(self, path: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        import httpx

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def _get(self, path: str, timeout: float = 30.0) -> Dict[str, Any]:
        import httpx

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
