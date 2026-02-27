"""Workflow listing, per-workflow history, recent history, and events endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from aegis_qa.config.loader import load_config

router = APIRouter(tags=["workflows"])


@router.get("/workflows")
async def list_workflows() -> list[dict[str, Any]]:
    config = load_config()
    result: list[dict[str, Any]] = []
    for key, wf in config.workflows.items():
        result.append({
            "key": key,
            "name": wf.name,
            "steps": [
                {
                    "type": s.type,
                    "service": s.service,
                    "condition": s.condition,
                    "parallel": s.parallel,
                    "retries": s.retries,
                    "timeout": s.timeout,
                }
                for s in wf.steps
            ],
        })
    return result


@router.get("/workflows/{name}")
async def get_workflow(name: str) -> dict[str, Any]:
    config = load_config()
    wf = config.workflows.get(name)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {name}")
    return {
        "key": name,
        "name": wf.name,
        "steps": [
            {
                "type": s.type,
                "service": s.service,
                "condition": s.condition,
                "parallel": s.parallel,
                "retries": s.retries,
                "retry_delay": s.retry_delay,
                "timeout": s.timeout,
            }
            for s in wf.steps
        ],
    }


@router.get("/workflows/{name}/history")
async def get_workflow_history(request: Request, name: str) -> list[dict[str, Any]]:
    config = load_config()
    if name not in config.workflows:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {name}")
    history = request.app.state.history
    records = await history.get_history(name)
    return [r.to_dict() for r in records]


@router.get("/history")
async def get_recent_history(request: Request, limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent execution records across all workflows."""
    history = request.app.state.history
    records = await history.get_recent(limit)
    return [r.to_dict() for r in records]


@router.get("/events")
async def get_recent_events(
    request: Request, limit: int = 20, event_type: str | None = None
) -> list[dict[str, Any]]:
    """Return recent workflow events from the in-memory log."""
    event_log = request.app.state.event_log
    events = await event_log.get_recent(limit=limit, event_type=event_type)
    return [
        {
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "workflow_name": e.workflow_name,
            "data": e.data,
        }
        for e in events
    ]
