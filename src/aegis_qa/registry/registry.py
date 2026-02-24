"""Service registry — loads services from config and checks health."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from aegis_qa.config.models import AegisConfig, ServiceEntry
from aegis_qa.registry.health import check_all_services, check_health
from aegis_qa.registry.models import HealthResult, ServiceStatus


class ServiceRegistry:
    """Registry of downstream services with health-check support."""

    def __init__(self, config: AegisConfig) -> None:
        self._config = config
        self._services: Dict[str, ServiceEntry] = dict(config.services)

    @property
    def service_keys(self) -> List[str]:
        return list(self._services.keys())

    def get_entry(self, key: str) -> Optional[ServiceEntry]:
        return self._services.get(key)

    async def check_one(self, key: str, timeout: float = 5.0) -> HealthResult:
        entry = self._services.get(key)
        if entry is None:
            return HealthResult(healthy=False, error=f"Unknown service: {key}")
        return await check_health(entry, timeout=timeout)

    async def check_all(self, timeout: float = 5.0) -> Dict[str, HealthResult]:
        return await check_all_services(self._services, timeout=timeout)

    async def get_all_statuses(self, timeout: float = 5.0) -> List[ServiceStatus]:
        health_map = await self.check_all(timeout=timeout)
        statuses: List[ServiceStatus] = []
        for key, entry in self._services.items():
            statuses.append(
                ServiceStatus(
                    key=key,
                    name=entry.name,
                    description=entry.description,
                    url=entry.url,
                    features=list(entry.features),
                    health=health_map.get(key),
                )
            )
        return statuses

    def get_all_statuses_sync(self, timeout: float = 5.0) -> List[ServiceStatus]:
        return asyncio.run(self.get_all_statuses(timeout=timeout))
