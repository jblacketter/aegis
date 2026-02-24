"""Tests for workflow engine — pipeline runner and steps."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aegis_qa.config.models import AegisConfig, ServiceEntry, WorkflowDef, WorkflowStepDef
from aegis_qa.workflows.models import StepResult, WorkflowResult
from aegis_qa.workflows.pipeline import PipelineRunner
from aegis_qa.workflows.steps.discover import DiscoverStep
from aegis_qa.workflows.steps.submit_bugs import SubmitBugsStep
from aegis_qa.workflows.steps.test import RunTestsStep
from aegis_qa.workflows.steps.verify import VerifyStep

# ─── StepResult / WorkflowResult tests ───


class TestStepResult:
    def test_success_no_failures(self):
        r = StepResult(step_type="test", service="qa", success=True, data={"failures": []})
        assert not r.has_failures

    def test_success_with_failures(self):
        r = StepResult(step_type="test", service="qa", success=True, data={"failures": [{"msg": "fail"}]})
        assert r.has_failures

    def test_failed_step(self):
        r = StepResult(step_type="test", service="qa", success=False, error="crash")
        assert r.has_failures


class TestWorkflowResult:
    def test_all_success(self):
        wr = WorkflowResult(
            workflow_name="pipe",
            steps=[
                StepResult(step_type="a", service="s", success=True),
                StepResult(step_type="b", service="s", success=True, skipped=True),
            ],
        )
        assert wr.success

    def test_has_failure(self):
        wr = WorkflowResult(
            workflow_name="pipe",
            steps=[
                StepResult(step_type="a", service="s", success=True),
                StepResult(step_type="b", service="s", success=False, error="boom"),
            ],
        )
        assert not wr.success

    def test_to_dict(self):
        wr = WorkflowResult(
            workflow_name="pipe",
            steps=[StepResult(step_type="a", service="s", success=True)],
        )
        d = wr.to_dict()
        assert d["workflow_name"] == "pipe"
        assert d["success"] is True
        assert len(d["steps"]) == 1


# ─── Step tests ───


class TestDiscoverStep:
    @pytest.mark.asyncio
    async def test_success(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = DiscoverStep(entry)
        with patch.object(step, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"routes": ["/api/users", "/api/items"]}
            result = await step.execute({})
            assert result.success
            assert result.data["route_count"] == 2

    @pytest.mark.asyncio
    async def test_failure(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = DiscoverStep(entry)
        with patch.object(step, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            result = await step.execute({})
            assert not result.success
            assert "Connection refused" in result.error


class TestRunTestsStep:
    @pytest.mark.asyncio
    async def test_success_with_failures(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = RunTestsStep(entry)
        with patch.object(step, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "total": 10,
                "passed": 8,
                "failed": 2,
                "failures": [{"test": "test_a"}, {"test": "test_b"}],
            }
            result = await step.execute({})
            assert result.success
            assert result.data["failed"] == 2
            assert len(result.data["failures"]) == 2

    @pytest.mark.asyncio
    async def test_error(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = RunTestsStep(entry)
        with patch.object(step, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Timeout")
            result = await step.execute({})
            assert not result.success


class TestSubmitBugsStep:
    @pytest.mark.asyncio
    async def test_no_failures(self):
        entry = ServiceEntry(name="Bug", url="http://localhost:8090")
        step = SubmitBugsStep(entry)
        result = await step.execute({"step_results": []})
        assert result.success
        assert result.data["submitted"] == 0

    @pytest.mark.asyncio
    async def test_with_failures(self):
        entry = ServiceEntry(name="Bug", url="http://localhost:8090")
        step = SubmitBugsStep(entry)
        prior = StepResult(
            step_type="test",
            service="QA",
            success=True,
            data={"failures": [{"test": "test_a"}]},
        )
        with patch.object(step, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"id": "bug-1"}
            result = await step.execute({"step_results": [prior]})
            assert result.success
            assert result.data["submitted"] == 1


class TestVerifyStep:
    @pytest.mark.asyncio
    async def test_placeholder(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = VerifyStep(entry)
        result = await step.execute({})
        assert result.success
        assert result.skipped


# ─── PipelineRunner tests ───


class TestPipelineRunner:
    @pytest.mark.asyncio
    async def test_unknown_workflow(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        result = await runner.run("nonexistent")
        assert not result.success
        assert "Unknown workflow" in result.steps[0].error

    @pytest.mark.asyncio
    async def test_full_pipeline_no_failures(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", new_callable=AsyncMock) as mock_disc,
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", new_callable=AsyncMock) as mock_test,
        ):
            mock_disc.return_value = StepResult(
                step_type="discover",
                service="QA Agent",
                success=True,
                data={"routes": ["/api/x"], "route_count": 1},
            )
            mock_test.return_value = StepResult(
                step_type="test",
                service="QA Agent",
                success=True,
                data={"total": 5, "passed": 5, "failed": 0, "failures": []},
            )
            result = await runner.run("full_pipeline")
            assert len(result.steps) == 3
            # discover + test ran, submit_bugs skipped (no failures)
            assert result.steps[0].step_type == "discover"
            assert result.steps[1].step_type == "test"
            assert result.steps[2].skipped  # submit_bugs skipped

    @pytest.mark.asyncio
    async def test_full_pipeline_with_failures(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", new_callable=AsyncMock) as mock_disc,
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", new_callable=AsyncMock) as mock_test,
            patch("aegis_qa.workflows.steps.submit_bugs.SubmitBugsStep.execute", new_callable=AsyncMock) as mock_sub,
        ):
            mock_disc.return_value = StepResult(
                step_type="discover",
                service="QA Agent",
                success=True,
                data={"routes": ["/api/x"], "route_count": 1},
            )
            mock_test.return_value = StepResult(
                step_type="test",
                service="QA Agent",
                success=True,
                data={"total": 5, "passed": 3, "failed": 2, "failures": [{"t": "a"}, {"t": "b"}]},
            )
            mock_sub.return_value = StepResult(
                step_type="submit_bugs",
                service="Bugalizer",
                success=True,
                data={"submitted": 2},
            )
            result = await runner.run("full_pipeline")
            assert len(result.steps) == 3
            assert not result.steps[2].skipped  # submit_bugs ran

    @pytest.mark.asyncio
    async def test_unknown_service_in_step(self):
        config = AegisConfig(
            workflows={
                "bad": WorkflowDef(
                    name="Bad",
                    steps=[WorkflowStepDef(type="discover", service="nonexistent")],
                )
            }
        )
        runner = PipelineRunner(config)
        result = await runner.run("bad")
        assert not result.success
        assert "Unknown service" in result.steps[0].error

    @pytest.mark.asyncio
    async def test_unknown_step_type(self, sample_config: AegisConfig):
        # Add a workflow with unknown step type
        sample_config.workflows["custom"] = WorkflowDef(
            name="Custom",
            steps=[WorkflowStepDef(type="magic", service="qaagent")],
        )
        runner = PipelineRunner(sample_config)
        result = await runner.run("custom")
        assert "Unknown step type" in result.steps[0].error


class TestConditionEvaluation:
    def test_no_condition(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        assert not runner._should_skip(None, {})

    def test_has_failures_true(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        ctx = {
            "step_results": [StepResult(step_type="test", service="qa", success=True, data={"failures": [{"x": 1}]})]
        }
        assert not runner._should_skip("has_failures", ctx)

    def test_has_failures_false(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        ctx = {"step_results": [StepResult(step_type="test", service="qa", success=True, data={"failures": []})]}
        assert runner._should_skip("has_failures", ctx)

    def test_unknown_condition(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        assert not runner._should_skip("something_else", {})
