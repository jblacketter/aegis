"""Portfolio metadata endpoint for the landing page."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from aegis_qa.config.loader import load_config

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio")
async def portfolio() -> Dict[str, Any]:
    config = load_config()
    tools: List[Dict[str, Any]] = []
    for key, entry in config.services.items():
        tools.append(
            {
                "key": key,
                "name": entry.name,
                "description": entry.description,
                "features": entry.features,
            }
        )
    return {
        "name": config.aegis.name,
        "tagline": "The AI Quality Control Plane",
        "version": config.aegis.version,
        "tools": tools,
        "workflows": list(config.workflows.keys()),
    }
