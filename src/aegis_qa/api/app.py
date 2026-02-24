"""FastAPI application factory for Aegis."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aegis_qa.api.routes import health, workflows, portfolio


def create_app() -> FastAPI:
    app = FastAPI(title="Aegis", version="0.1.0", description="The AI Quality Control Plane")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")

    # Serve landing page static files at root
    landing_dir = Path(__file__).parent.parent / "landing"
    if landing_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(landing_dir), html=True), name="landing")

    return app


app = create_app()
