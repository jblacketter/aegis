"""Service health and listing endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from aegis_qa.config.loader import load_config
from aegis_qa.registry.registry import ServiceRegistry

router = APIRouter(tags=["services"])


def _get_registry() -> ServiceRegistry:
    config = load_config()
    return ServiceRegistry(config)


@router.get("/services")
async def list_services() -> List[Dict[str, Any]]:
    registry = _get_registry()
    statuses = await registry.get_all_statuses(timeout=5.0)
    return [
        {
            "key": s.key,
            "name": s.name,
            "description": s.description,
            "url": s.url,
            "features": s.features,
            "status": s.status_label,
            "latency_ms": s.health.latency_ms if s.health else None,
        }
        for s in statuses
    ]


@router.get("/services/{name}/health")
async def service_health(name: str) -> Dict[str, Any]:
    registry = _get_registry()
    entry = registry.get_entry(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown service: {name}")
    result = await registry.check_one(name, timeout=5.0)
    return {
        "service": name,
        "healthy": result.healthy,
        "status_code": result.status_code,
        "latency_ms": result.latency_ms,
        "error": result.error,
    }
