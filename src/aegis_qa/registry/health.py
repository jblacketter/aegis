"""Async health check utilities."""

from __future__ import annotations

import asyncio
import time
from typing import Dict

import httpx

from aegis_qa.config.models import ServiceEntry
from aegis_qa.registry.models import HealthResult


async def check_health(entry: ServiceEntry, timeout: float = 5.0) -> HealthResult:
    """Check health of a single service via its health endpoint."""
    url = entry.url.rstrip("/") + entry.health_endpoint
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            latency = (time.monotonic() - start) * 1000
            return HealthResult(
                healthy=resp.status_code == 200,
                status_code=resp.status_code,
                latency_ms=round(latency, 1),
            )
    except httpx.ConnectError as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthResult(
            healthy=False,
            latency_ms=round(latency, 1),
            error=f"Connection refused: {exc}",
        )
    except httpx.TimeoutException:
        latency = (time.monotonic() - start) * 1000
        return HealthResult(
            healthy=False,
            latency_ms=round(latency, 1),
            error="Timeout",
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthResult(
            healthy=False,
            latency_ms=round(latency, 1),
            error=str(exc),
        )


async def check_all_services(
    services: Dict[str, ServiceEntry],
    timeout: float = 5.0,
) -> Dict[str, HealthResult]:
    """Run health checks for all services concurrently."""
    tasks = {
        key: check_health(entry, timeout=timeout)
        for key, entry in services.items()
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    out: Dict[str, HealthResult] = {}
    for key, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            out[key] = HealthResult(healthy=False, error=str(result))
        else:
            out[key] = result
    return out
