"""Workflow execution endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from aegis_qa.config.loader import load_config
from aegis_qa.workflows.pipeline import PipelineRunner

router = APIRouter(tags=["workflows"])


@router.post("/workflows/{name}/run")
async def run_workflow(name: str) -> dict[str, Any]:
    config = load_config()
    if name not in config.workflows:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {name}")
    runner = PipelineRunner(config)
    result = await runner.run(name)
    return result.to_dict()
