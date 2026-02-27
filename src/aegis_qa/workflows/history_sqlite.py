"""SQLite-backed execution history backend."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from aegis_qa.workflows.history import ExecutionRecord, StepRecord

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    success INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_type TEXT NOT NULL,
    service TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    duration_ms REAL,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 1
);
"""


class SqliteHistory:
    """SQLite-backed execution history with optional retention pruning."""

    def __init__(self, db_path: str = "aegis_history.db", max_records: int = 0) -> None:
        self._db_path = db_path
        self._max_records = max_records
        self._initialized = False

    async def _init_connection(self, db: aiosqlite.Connection) -> None:
        """Enable foreign keys (must run per-connection) and create tables on first use."""
        await db.execute("PRAGMA foreign_keys = ON")
        if not self._initialized:
            await db.executescript(_CREATE_TABLES)
            self._initialized = True

    async def record(self, execution: ExecutionRecord) -> None:
        """Store an execution record to SQLite."""
        async with aiosqlite.connect(self._db_path) as db:
            await self._init_connection(db)
            cursor = await db.execute(
                "INSERT INTO workflow_runs (workflow_name, started_at, completed_at, success) VALUES (?, ?, ?, ?)",
                (
                    execution.workflow_name,
                    execution.started_at.isoformat(),
                    execution.completed_at.isoformat() if execution.completed_at else None,
                    int(execution.success),
                ),
            )
            run_id = cursor.lastrowid
            for step in execution.steps:
                await db.execute(
                    "INSERT INTO step_runs (run_id, step_type, service, success, skipped, duration_ms, error, attempts)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        step.step_type,
                        step.service,
                        int(step.success),
                        int(step.skipped),
                        step.duration_ms,
                        step.error,
                        step.attempts,
                    ),
                )

            # Retention pruning
            if self._max_records > 0:
                count_rows = list(await db.execute_fetchall(
                    "SELECT COUNT(*) FROM workflow_runs WHERE workflow_name = ?",
                    (execution.workflow_name,),
                ))
                count = int(count_rows[0][0])
                excess = count - self._max_records
                if excess > 0:
                    await db.execute(
                        "DELETE FROM workflow_runs WHERE id IN ("
                        "  SELECT id FROM workflow_runs WHERE workflow_name = ?"
                        "  ORDER BY started_at ASC LIMIT ?"
                        ")",
                        (execution.workflow_name, excess),
                    )

            await db.commit()

    async def _load_steps(self, db: aiosqlite.Connection, run_id: int) -> list[StepRecord]:
        rows = list(await db.execute_fetchall(
            "SELECT step_type, service, success, skipped, duration_ms, error, attempts"
            " FROM step_runs WHERE run_id = ? ORDER BY id",
            (run_id,),
        ))
        return [
            StepRecord(
                step_type=str(r[0]),
                service=str(r[1]),
                success=bool(r[2]),
                skipped=bool(r[3]),
                duration_ms=float(r[4]) if r[4] is not None else None,
                error=str(r[5]) if r[5] is not None else None,
                attempts=int(r[6]),
            )
            for r in rows
        ]

    def _parse_dt(self, val: str | None) -> datetime | None:
        if val is None:
            return None
        return datetime.fromisoformat(val).replace(tzinfo=UTC)

    async def _rows_to_records(self, db: aiosqlite.Connection, rows: list[Any]) -> list[ExecutionRecord]:
        records: list[ExecutionRecord] = []
        for r in rows:
            run_id = int(r[0])
            steps = await self._load_steps(db, run_id)
            started = self._parse_dt(str(r[2])) or datetime.now(UTC)
            completed = self._parse_dt(str(r[3]) if r[3] else None)
            records.append(
                ExecutionRecord(
                    workflow_name=str(r[1]),
                    started_at=started,
                    completed_at=completed,
                    success=bool(r[4]),
                    steps=steps,
                )
            )
        return records

    async def get_history(self, workflow_name: str) -> list[ExecutionRecord]:
        """Get execution history for a specific workflow."""
        async with aiosqlite.connect(self._db_path) as db:
            await self._init_connection(db)
            rows = list(await db.execute_fetchall(
                "SELECT id, workflow_name, started_at, completed_at, success"
                " FROM workflow_runs WHERE workflow_name = ? ORDER BY started_at DESC",
                (workflow_name,),
            ))
            return await self._rows_to_records(db, rows)

    async def get_all(self) -> dict[str, list[ExecutionRecord]]:
        """Get all execution history grouped by workflow name."""
        async with aiosqlite.connect(self._db_path) as db:
            await self._init_connection(db)
            rows = list(await db.execute_fetchall(
                "SELECT id, workflow_name, started_at, completed_at, success"
                " FROM workflow_runs ORDER BY started_at DESC"
            ))
            records = await self._rows_to_records(db, rows)
            result: dict[str, list[ExecutionRecord]] = {}
            for rec in records:
                if rec.workflow_name not in result:
                    result[rec.workflow_name] = []
                result[rec.workflow_name].append(rec)
            return result

    async def get_recent(self, limit: int = 10) -> list[ExecutionRecord]:
        """Get the most recent execution records across all workflows."""
        async with aiosqlite.connect(self._db_path) as db:
            await self._init_connection(db)
            rows = list(await db.execute_fetchall(
                "SELECT id, workflow_name, started_at, completed_at, success"
                " FROM workflow_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ))
            return await self._rows_to_records(db, rows)
