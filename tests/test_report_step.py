"""Tests for the ReportStep workflow step."""

from __future__ import annotations

import pytest

from aegis_qa.config.models import ServiceEntry
from aegis_qa.workflows.models import StepResult
from aegis_qa.workflows.steps.report import ReportStep


class TestReportStep:
    @pytest.mark.asyncio
    async def test_empty_context(self):
        entry = ServiceEntry(name="Aegis", url="http://localhost:8000")
        step = ReportStep(entry)
        result = await step.execute({"step_results": []})
        assert result.success
        assert result.step_type == "report"
        assert result.data["summary"]["total"] == 0
        assert result.data["summary"]["passed"] == 0
        assert result.data["summary"]["failed"] == 0
        assert result.data["summary"]["skipped"] == 0
        assert result.data["total_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_mixed_results(self):
        entry = ServiceEntry(name="Aegis", url="http://localhost:8000")
        step = ReportStep(entry)

        prior_results = [
            StepResult(step_type="discover", service="QA", success=True, duration_ms=100.0),
            StepResult(step_type="test", service="QA", success=False, error="timeout", duration_ms=200.0),
            StepResult(step_type="submit_bugs", service="Bug", success=True, skipped=True, duration_ms=0.0),
        ]
        result = await step.execute({"step_results": prior_results})

        assert result.success
        assert result.data["summary"]["total"] == 3
        assert result.data["summary"]["passed"] == 1
        assert result.data["summary"]["failed"] == 1
        assert result.data["summary"]["skipped"] == 1
        assert result.data["total_duration_ms"] == 300.0
        assert len(result.data["steps"]) == 3

    @pytest.mark.asyncio
    async def test_all_passed(self):
        entry = ServiceEntry(name="Aegis", url="http://localhost:8000")
        step = ReportStep(entry)

        prior_results = [
            StepResult(step_type="discover", service="QA", success=True, duration_ms=50.0),
            StepResult(step_type="test", service="QA", success=True, duration_ms=150.0),
        ]
        result = await step.execute({"step_results": prior_results})

        assert result.success
        assert result.data["summary"]["passed"] == 2
        assert result.data["summary"]["failed"] == 0
        assert result.data["total_duration_ms"] == 200.0

    @pytest.mark.asyncio
    async def test_no_step_results_key(self):
        entry = ServiceEntry(name="Aegis", url="http://localhost:8000")
        step = ReportStep(entry)
        result = await step.execute({})
        assert result.success
        assert result.data["summary"]["total"] == 0

    @pytest.mark.asyncio
    async def test_step_type_is_report(self):
        assert ReportStep.step_type == "report"

    @pytest.mark.asyncio
    async def test_report_step_data_structure(self):
        entry = ServiceEntry(name="Aegis", url="http://localhost:8000")
        step = ReportStep(entry)
        prior = [
            StepResult(step_type="discover", service="QA", success=True, duration_ms=10.0),
        ]
        result = await step.execute({"step_results": prior})
        step_detail = result.data["steps"][0]
        assert "step_type" in step_detail
        assert "service" in step_detail
        assert "success" in step_detail
        assert "skipped" in step_detail
        assert "duration_ms" in step_detail
        assert "error" in step_detail
