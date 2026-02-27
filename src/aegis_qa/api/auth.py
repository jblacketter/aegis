"""API key authentication dependency for FastAPI."""

from __future__ import annotations

from fastapi import HTTPException, Request


async def require_api_key(request: Request) -> None:
    """FastAPI dependency that checks X-API-Key header on protected endpoints.

    Auth is disabled when no key is configured (backwards compatible).
    """
    config = request.app.state.config
    if not config.auth.api_key:
        return  # auth disabled
    key = request.headers.get("X-API-Key", "")
    if key != config.auth.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
