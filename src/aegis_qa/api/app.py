"""FastAPI application factory for Aegis."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aegis_qa.api.routes import health, portfolio, workflow_list, workflows
from aegis_qa.config.loader import load_config
from aegis_qa.events.emitter import EventEmitter
from aegis_qa.events.log import EventLog
from aegis_qa.events.webhook import WebhookListener
from aegis_qa.workflows.history import InMemoryHistory


def create_app() -> FastAPI:
    app = FastAPI(title="Aegis", version="0.1.0", description="The AI Quality Control Plane")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Load config and wire shared state
    try:
        config = load_config()
    except (FileNotFoundError, ValueError):
        # Fallback for environments without a config file (e.g. testing)
        from aegis_qa.config.models import AegisConfig

        config = AegisConfig()

    app.state.config = config

    # History backend — use SQLite if a db path is configured, in-memory otherwise
    try:
        from aegis_qa.workflows.history_sqlite import SqliteHistory

        history = SqliteHistory(config.history_db_path, config.history_max_records)
    except Exception:
        history = InMemoryHistory()  # type: ignore[assignment]
    app.state.history = history

    # Event system
    event_log = EventLog(config.event_log_size)
    emitter = EventEmitter()
    emitter.add_listener(event_log)
    if config.webhooks:
        emitter.add_listener(WebhookListener(config.webhooks))
    app.state.event_log = event_log
    app.state.emitter = emitter

    @app.get("/health", tags=["meta"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health.router, prefix="/api")
    app.include_router(workflow_list.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")

    # Serve landing page static files at root
    landing_dir = Path(__file__).parent.parent / "landing"
    if landing_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(landing_dir), html=True), name="landing")

    return app


app = create_app()
