"""Tests for both InMemoryHistory and SqliteHistory backends."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aegis_qa.workflows.history import (
    ExecutionHistoryBackend,
    ExecutionRecord,
    InMemoryHistory,
    StepRecord,
)
from aegis_qa.workflows.history_sqlite import SqliteHistory


def _make_record(name: str = "test_wf", success: bool = True) -> ExecutionRecord:
    return ExecutionRecord(
        workflow_name=name,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        success=success,
        steps=[
            StepRecord(step_type="discover", service="qa", success=True),
            StepRecord(step_type="test", service="qa", success=success),
        ],
    )


class TestInMemoryHistory:
    @pytest.mark.asyncio
    async def test_implements_protocol(self):
        assert isinstance(InMemoryHistory(), ExecutionHistoryBackend)

    @pytest.mark.asyncio
    async def test_record_and_get_history(self):
        h = InMemoryHistory()
        rec = _make_record()
        await h.record(rec)
        records = await h.get_history("test_wf")
        assert len(records) == 1
        assert records[0].workflow_name == "test_wf"

    @pytest.mark.asyncio
    async def test_get_history_empty(self):
        h = InMemoryHistory()
        assert await h.get_history("nonexistent") == []

    @pytest.mark.asyncio
    async def test_get_all(self):
        h = InMemoryHistory()
        await h.record(_make_record("wf_a"))
        await h.record(_make_record("wf_b"))
        all_records = await h.get_all()
        assert "wf_a" in all_records
        assert "wf_b" in all_records

    @pytest.mark.asyncio
    async def test_get_recent(self):
        h = InMemoryHistory()
        for i in range(15):
            await h.record(_make_record(f"wf_{i}"))
        recent = await h.get_recent(limit=10)
        assert len(recent) == 10

    @pytest.mark.asyncio
    async def test_to_dict_includes_duration(self):
        h = InMemoryHistory()
        rec = _make_record()
        await h.record(rec)
        records = await h.get_history("test_wf")
        d = records[0].to_dict()
        assert "duration_ms" in d
        assert "step_count" in d
        assert d["step_count"] == 2


class TestSqliteHistory:
    @pytest.mark.asyncio
    async def test_record_and_get_history(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path)
        rec = _make_record()
        await h.record(rec)
        records = await h.get_history("test_wf")
        assert len(records) == 1
        assert records[0].workflow_name == "test_wf"
        assert records[0].success is True
        assert len(records[0].steps) == 2

    @pytest.mark.asyncio
    async def test_get_history_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path)
        assert await h.get_history("nonexistent") == []

    @pytest.mark.asyncio
    async def test_get_all(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path)
        await h.record(_make_record("wf_a"))
        await h.record(_make_record("wf_b"))
        all_records = await h.get_all()
        assert "wf_a" in all_records
        assert "wf_b" in all_records

    @pytest.mark.asyncio
    async def test_get_recent(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path)
        for i in range(15):
            await h.record(_make_record(f"wf_{i}"))
        recent = await h.get_recent(limit=10)
        assert len(recent) == 10

    @pytest.mark.asyncio
    async def test_retention_pruning(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path, max_records=3)
        for _ in range(5):
            await h.record(_make_record("prune_wf"))
        records = await h.get_history("prune_wf")
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_retention_pruning_cascades_step_rows(self, tmp_path):
        """Retention pruning must also delete orphaned step_runs via ON DELETE CASCADE."""
        import aiosqlite

        db_path = str(tmp_path / "cascade.db")
        h = SqliteHistory(db_path=db_path, max_records=1)
        # Record two runs — only the latest should survive
        await h.record(_make_record("cascade_wf"))
        await h.record(_make_record("cascade_wf"))

        records = await h.get_history("cascade_wf")
        assert len(records) == 1

        # Directly query step_runs count — should match the surviving run only
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            rows = list(await db.execute_fetchall("SELECT COUNT(*) FROM step_runs"))
            step_count = int(rows[0][0])
            # Each _make_record has 2 steps; only 1 run survives → 2 step rows
            assert step_count == 2

    @pytest.mark.asyncio
    async def test_retention_no_pruning_when_zero(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path, max_records=0)
        for _ in range(10):
            await h.record(_make_record("no_prune"))
        records = await h.get_history("no_prune")
        assert len(records) == 10

    @pytest.mark.asyncio
    async def test_step_records_persisted(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        h = SqliteHistory(db_path=db_path)
        rec = ExecutionRecord(
            workflow_name="step_test",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            success=True,
            steps=[
                StepRecord(
                    step_type="discover",
                    service="qa",
                    success=True,
                    duration_ms=123.4,
                    attempts=2,
                ),
                StepRecord(
                    step_type="test",
                    service="qa",
                    success=False,
                    error="timeout",
                    skipped=False,
                ),
            ],
        )
        await h.record(rec)
        records = await h.get_history("step_test")
        steps = records[0].steps
        assert len(steps) == 2
        assert steps[0].duration_ms == 123.4
        assert steps[0].attempts == 2
        assert steps[1].error == "timeout"

    @pytest.mark.asyncio
    async def test_persists_across_instances(self, tmp_path):
        """Data survives creating a new SqliteHistory instance."""
        db_path = str(tmp_path / "test.db")
        h1 = SqliteHistory(db_path=db_path)
        await h1.record(_make_record("persist_test"))

        h2 = SqliteHistory(db_path=db_path)
        records = await h2.get_history("persist_test")
        assert len(records) == 1
