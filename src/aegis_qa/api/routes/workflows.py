"""Workflow execution endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from aegis_qa.api.auth import require_api_key
from aegis_qa.config.loader import load_config
from aegis_qa.workflows.pipeline import PipelineRunner

router = APIRouter(tags=["workflows"])


@router.post("/workflows/{name}/run", dependencies=[Depends(require_api_key)])
async def run_workflow(request: Request, name: str) -> dict[str, Any]:
    config = load_config()
    if name not in config.workflows:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {name}")
    history = request.app.state.history
    emitter = getattr(request.app.state, "emitter", None)
    runner = PipelineRunner(config, history=history, emitter=emitter)
    result = await runner.run(name)
    return result.to_dict()
