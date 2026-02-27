"""Tests for workflow engine — pipeline runner, steps, retry, parallel, conditions, history."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from aegis_qa.config.models import AegisConfig, ServiceEntry, WorkflowDef, WorkflowStepDef
from aegis_qa.workflows.history import ExecutionHistory
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

    def test_duration_ms_default(self):
        r = StepResult(step_type="test", service="qa", success=True)
        assert r.duration_ms is None

    def test_attempts_default(self):
        r = StepResult(step_type="test", service="qa", success=True)
        assert r.attempts == []


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
            steps=[StepResult(step_type="a", service="s", success=True, duration_ms=12.5)],
        )
        d = wr.to_dict()
        assert d["workflow_name"] == "pipe"
        assert d["success"] is True
        assert len(d["steps"]) == 1
        assert d["steps"][0]["duration_ms"] == 12.5
        assert d["steps"][0]["attempts"] == []


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
    async def test_success(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = VerifyStep(entry)
        with patch.object(step, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "total": 5,
                "passed": 5,
                "failed": 0,
                "failures": [],
            }
            result = await step.execute({})
            assert result.success
            assert result.data["verify_only"] is True
            assert result.data["failed"] == 0
            mock_post.assert_called_once_with("/api/runs", payload={"verify_only": True})

    @pytest.mark.asyncio
    async def test_failure(self):
        entry = ServiceEntry(name="QA", url="http://localhost:8080")
        step = VerifyStep(entry)
        with patch.object(step, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Connection refused")
            result = await step.execute({})
            assert not result.success
            assert "Connection refused" in result.error


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


# ─── Condition evaluator tests ───


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

    def test_on_success_true(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        ctx = {"step_results": [StepResult(step_type="test", service="qa", success=True)]}
        assert not runner._should_skip("on_success", ctx)

    def test_on_success_false(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        ctx = {"step_results": [StepResult(step_type="test", service="qa", success=False, error="err")]}
        assert runner._should_skip("on_success", ctx)

    def test_on_failure_true(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        ctx = {"step_results": [StepResult(step_type="test", service="qa", success=False, error="err")]}
        assert not runner._should_skip("on_failure", ctx)

    def test_on_failure_false(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        ctx = {"step_results": [StepResult(step_type="test", service="qa", success=True)]}
        assert runner._should_skip("on_failure", ctx)

    def test_always(self, sample_config: AegisConfig):
        runner = PipelineRunner(sample_config)
        assert not runner._should_skip("always", {})
        ctx = {"step_results": [StepResult(step_type="test", service="qa", success=True)]}
        assert not runner._should_skip("always", ctx)


# ─── Retry tests ───


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Step retries the configured number of times on failure."""
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "retry_test": WorkflowDef(
                    name="Retry Test",
                    steps=[WorkflowStepDef(type="discover", service="qaagent", retries=2, retry_delay=0.01)],
                )
            },
        )
        runner = PipelineRunner(config)

        call_count = 0

        async def mock_execute(context):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return StepResult(step_type="discover", service="QA", success=False, error="fail")
            return StepResult(step_type="discover", service="QA", success=True, data={"routes": []})

        with patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", side_effect=mock_execute):
            result = await runner.run("retry_test")
            assert result.success
            assert call_count == 3
            assert len(result.steps[0].attempts) == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """Step does not retry when it succeeds on first attempt."""
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "no_retry": WorkflowDef(
                    name="No Retry",
                    steps=[WorkflowStepDef(type="discover", service="qaagent", retries=3, retry_delay=0.01)],
                )
            },
        )
        runner = PipelineRunner(config)
        with patch(
            "aegis_qa.workflows.steps.discover.DiscoverStep.execute",
            new_callable=AsyncMock,
            return_value=StepResult(step_type="discover", service="QA", success=True),
        ):
            result = await runner.run("no_retry")
            assert result.success
            assert len(result.steps[0].attempts) == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Step fails after exhausting all retries."""
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "exhaust": WorkflowDef(
                    name="Exhaust",
                    steps=[WorkflowStepDef(type="discover", service="qaagent", retries=1, retry_delay=0.01)],
                )
            },
        )
        runner = PipelineRunner(config)
        with patch(
            "aegis_qa.workflows.steps.discover.DiscoverStep.execute",
            new_callable=AsyncMock,
            return_value=StepResult(step_type="discover", service="QA", success=False, error="down"),
        ):
            result = await runner.run("exhaust")
            assert not result.success
            assert len(result.steps[0].attempts) == 2  # 1 initial + 1 retry


# ─── Timeout tests ───


class TestTimeout:
    @pytest.mark.asyncio
    async def test_step_timeout(self):
        """Step that exceeds timeout gets a timeout error."""
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "timeout_test": WorkflowDef(
                    name="Timeout Test",
                    steps=[WorkflowStepDef(type="discover", service="qaagent", timeout=0.05)],
                )
            },
        )
        runner = PipelineRunner(config)

        async def slow_execute(context):
            await asyncio.sleep(1.0)
            return StepResult(step_type="discover", service="QA", success=True)

        with patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", side_effect=slow_execute):
            result = await runner.run("timeout_test")
            assert not result.success
            assert "timed out" in result.steps[0].error


# ─── Parallel execution tests ───


class TestParallel:
    @pytest.mark.asyncio
    async def test_parallel_steps_run_concurrently(self):
        """Consecutive parallel steps execute concurrently via asyncio.gather()."""
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "parallel_test": WorkflowDef(
                    name="Parallel Test",
                    steps=[
                        WorkflowStepDef(type="discover", service="qaagent", parallel=True),
                        WorkflowStepDef(type="test", service="qaagent", parallel=True),
                    ],
                )
            },
        )
        runner = PipelineRunner(config)

        async def mock_discover(context):
            await asyncio.sleep(0.05)
            return StepResult(step_type="discover", service="QA", success=True, data={"routes": []})

        async def mock_test(context):
            await asyncio.sleep(0.05)
            return StepResult(step_type="test", service="QA", success=True, data={"failures": []})

        with (
            patch("aegis_qa.workflows.steps.discover.DiscoverStep.execute", side_effect=mock_discover),
            patch("aegis_qa.workflows.steps.test.RunTestsStep.execute", side_effect=mock_test),
        ):
            result = await runner.run("parallel_test")
            assert result.success
            assert len(result.steps) == 2
            # Both steps should have duration_ms set
            assert all(s.duration_ms is not None for s in result.steps)

    @pytest.mark.asyncio
    async def test_mixed_sequential_and_parallel(self):
        """Sequential steps flush parallel batches."""
        config = AegisConfig(
            services={
                "qaagent": ServiceEntry(name="QA", url="http://localhost:8080"),
                "bugalizer": ServiceEntry(name="Bug", url="http://localhost:8090"),
            },
            workflows={
                "mixed": WorkflowDef(
                    name="Mixed",
                    steps=[
                        WorkflowStepDef(type="discover", service="qaagent", parallel=True),
                        WorkflowStepDef(type="test", service="qaagent", parallel=True),
                        WorkflowStepDef(type="submit_bugs", service="bugalizer"),  # sequential — flushes batch
                    ],
                )
            },
        )
        runner = PipelineRunner(config)
        with (
            patch(
                "aegis_qa.workflows.steps.discover.DiscoverStep.execute",
                new_callable=AsyncMock,
                return_value=StepResult(step_type="discover", service="QA", success=True),
            ),
            patch(
                "aegis_qa.workflows.steps.test.RunTestsStep.execute",
                new_callable=AsyncMock,
                return_value=StepResult(step_type="test", service="QA", success=True, data={"failures": []}),
            ),
            patch(
                "aegis_qa.workflows.steps.submit_bugs.SubmitBugsStep.execute",
                new_callable=AsyncMock,
                return_value=StepResult(step_type="submit_bugs", service="Bug", success=True, data={"submitted": 0}),
            ),
        ):
            result = await runner.run("mixed")
            assert result.success
            assert len(result.steps) == 3
            assert result.steps[0].step_type == "discover"
            assert result.steps[1].step_type == "test"
            assert result.steps[2].step_type == "submit_bugs"


# ─── Execution history tests ───


class TestExecutionHistory:
    @pytest.mark.asyncio
    async def test_history_recorded(self):
        """PipelineRunner records execution to history when provided."""
        history = ExecutionHistory()
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "hist_test": WorkflowDef(
                    name="History Test",
                    steps=[WorkflowStepDef(type="discover", service="qaagent")],
                )
            },
        )
        runner = PipelineRunner(config, history=history)
        with patch(
            "aegis_qa.workflows.steps.discover.DiscoverStep.execute",
            new_callable=AsyncMock,
            return_value=StepResult(step_type="discover", service="QA", success=True),
        ):
            await runner.run("hist_test")

        records = await history.get_history("hist_test")
        assert len(records) == 1
        assert records[0].workflow_name == "hist_test"
        assert records[0].success is True
        assert records[0].completed_at is not None
        assert len(records[0].steps) == 1

    @pytest.mark.asyncio
    async def test_no_history_when_not_provided(self):
        """PipelineRunner works fine without a history instance."""
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "no_hist": WorkflowDef(
                    name="No History",
                    steps=[WorkflowStepDef(type="discover", service="qaagent")],
                )
            },
        )
        runner = PipelineRunner(config)
        with patch(
            "aegis_qa.workflows.steps.discover.DiscoverStep.execute",
            new_callable=AsyncMock,
            return_value=StepResult(step_type="discover", service="QA", success=True),
        ):
            result = await runner.run("no_hist")
            assert result.success

    @pytest.mark.asyncio
    async def test_history_to_dict(self):
        """ExecutionRecord.to_dict() produces valid serialization."""
        history = ExecutionHistory()
        config = AegisConfig(
            services={"qaagent": ServiceEntry(name="QA", url="http://localhost:8080")},
            workflows={
                "dict_test": WorkflowDef(
                    name="Dict Test",
                    steps=[WorkflowStepDef(type="discover", service="qaagent")],
                )
            },
        )
        runner = PipelineRunner(config, history=history)
        with patch(
            "aegis_qa.workflows.steps.discover.DiscoverStep.execute",
            new_callable=AsyncMock,
            return_value=StepResult(step_type="discover", service="QA", success=True),
        ):
            await runner.run("dict_test")

        records = await history.get_history("dict_test")
        d = records[0].to_dict()
        assert "workflow_name" in d
        assert "started_at" in d
        assert "completed_at" in d
        assert "steps" in d
        assert d["steps"][0]["step_type"] == "discover"
