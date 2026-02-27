"""Tests for the Aegis CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from aegis_qa.cli import app
from aegis_qa.config.models import AegisConfig
from aegis_qa.registry.models import HealthResult, ServiceStatus
from aegis_qa.workflows.models import StepResult, WorkflowResult

runner = CliRunner()


class TestStatusCommand:
    def test_status_success(self, sample_config: AegisConfig):
        mock_statuses = [
            ServiceStatus(
                key="qaagent",
                name="QA Agent",
                description="Test gen",
                url="http://localhost:8080",
                features=[],
                health=HealthResult(healthy=True, status_code=200, latency_ms=10.0),
            ),
            ServiceStatus(
                key="bugalizer",
                name="Bugalizer",
                description="Bug triage",
                url="http://localhost:8090",
                features=[],
                health=HealthResult(healthy=False, error="Connection refused"),
            ),
        ]
        with (
            patch("aegis_qa.config.loader.load_config", return_value=sample_config),
            patch("aegis_qa.registry.registry.ServiceRegistry.get_all_statuses_sync", return_value=mock_statuses),
        ):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "QA Agent" in result.output
            assert "Bugalizer" in result.output

    def test_status_no_config(self):
        with patch("aegis_qa.config.loader.load_config", side_effect=FileNotFoundError("No config")):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 1
            assert "No config" in result.output


class TestServeCommand:
    def test_serve(self):
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "9000"])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                "aegis_qa.api.app:app", host="127.0.0.1", port=9000, reload=False
            )

    def test_serve_default_args(self):
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(app, ["serve"])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                "aegis_qa.api.app:app", host="0.0.0.0", port=8000, reload=False
            )


class TestRunCommand:
    def test_run_success(self, sample_config: AegisConfig):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[
                StepResult(step_type="discover", service="QA Agent", success=True, data={"route_count": 3}),
                StepResult(step_type="test", service="QA Agent", success=True, data={"failures": []}),
            ],
        )
        with (
            patch("aegis_qa.config.loader.load_config", return_value=sample_config),
            patch("aegis_qa.workflows.pipeline.PipelineRunner.run", new_callable=AsyncMock, return_value=mock_result),
        ):
            result = runner.invoke(app, ["run", "full_pipeline"])
            assert result.exit_code == 0
            assert "Pipeline completed successfully" in result.output

    def test_run_with_failures(self, sample_config: AegisConfig):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[
                StepResult(step_type="discover", service="QA Agent", success=False, error="down"),
            ],
        )
        with (
            patch("aegis_qa.config.loader.load_config", return_value=sample_config),
            patch("aegis_qa.workflows.pipeline.PipelineRunner.run", new_callable=AsyncMock, return_value=mock_result),
        ):
            result = runner.invoke(app, ["run", "full_pipeline"])
            assert result.exit_code == 1
            assert "Pipeline completed with errors" in result.output

    def test_run_unknown_workflow(self, sample_config: AegisConfig):
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["run", "nonexistent"])
            assert result.exit_code == 1
            assert "Unknown workflow" in result.output

    def test_run_no_config(self):
        with patch("aegis_qa.config.loader.load_config", side_effect=FileNotFoundError("No config")):
            result = runner.invoke(app, ["run", "full_pipeline"])
            assert result.exit_code == 1
            assert "No config" in result.output

    def test_run_skipped_step(self, sample_config: AegisConfig):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[
                StepResult(
                    step_type="submit_bugs",
                    service="Bug",
                    success=True,
                    skipped=True,
                    data={"message": "Skipped: condition not met"},
                ),
            ],
        )
        with (
            patch("aegis_qa.config.loader.load_config", return_value=sample_config),
            patch("aegis_qa.workflows.pipeline.PipelineRunner.run", new_callable=AsyncMock, return_value=mock_result),
        ):
            result = runner.invoke(app, ["run", "full_pipeline"])
            assert result.exit_code == 0
            assert "Skipped" in result.output

    def test_run_error_step(self, sample_config: AegisConfig):
        mock_result = WorkflowResult(
            workflow_name="full_pipeline",
            steps=[
                StepResult(step_type="test", service="QA", success=False, error="Connection timed out"),
            ],
        )
        with (
            patch("aegis_qa.config.loader.load_config", return_value=sample_config),
            patch("aegis_qa.workflows.pipeline.PipelineRunner.run", new_callable=AsyncMock, return_value=mock_result),
        ):
            result = runner.invoke(app, ["run", "full_pipeline"])
            assert result.exit_code == 1
            assert "Connection timed out" in result.output


class TestConfigValidateCommand:
    def test_validate_valid_config(self, sample_config: AegisConfig):
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 0
            assert "Configuration is valid" in result.output

    def test_validate_no_config(self):
        with patch("aegis_qa.config.loader.load_config", side_effect=FileNotFoundError("No config")):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1
            assert "No config" in result.output

    def test_validate_invalid_config(self):
        with patch("aegis_qa.config.loader.load_config", side_effect=ValueError("Invalid config")):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1
            assert "Pydantic validation failed" in result.output

    def test_validate_malformed_yaml(self, tmp_path: Path):
        """Malformed YAML should produce a clean error, not a raw traceback."""
        bad_yaml = tmp_path / ".aegis.yaml"
        bad_yaml.write_text(":\n  - :\n  bad: [unclosed")
        result = runner.invoke(app, ["config", "validate", "--path", str(bad_yaml)])
        assert result.exit_code == 1
        assert "YAML parsing failed" in result.output

    def test_validate_unknown_service(self, sample_config: AegisConfig):
        from aegis_qa.config.models import WorkflowDef, WorkflowStepDef

        sample_config.workflows["bad"] = WorkflowDef(
            name="Bad Workflow",
            steps=[WorkflowStepDef(type="discover", service="nonexistent")],
        )
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1
            assert "unknown service" in result.output

    def test_validate_unknown_step_type(self, sample_config: AegisConfig):
        from aegis_qa.config.models import WorkflowDef, WorkflowStepDef

        sample_config.workflows["bad"] = WorkflowDef(
            name="Bad Workflow",
            steps=[WorkflowStepDef(type="magic", service="qaagent")],
        )
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1
            assert "unknown step type" in result.output

    def test_validate_invalid_url(self, sample_config: AegisConfig):
        sample_config.services["qaagent"].url = "not-a-url"
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1
            assert "invalid URL" in result.output

    def test_validate_webhook_invalid_url(self, sample_config: AegisConfig):
        from aegis_qa.config.models import WebhookConfig

        sample_config.webhooks = [WebhookConfig(url="not-a-url", events=["workflow.completed"])]
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1
            assert "invalid URL" in result.output

    def test_validate_webhook_unrecognized_event(self, sample_config: AegisConfig):
        from aegis_qa.config.models import WebhookConfig

        sample_config.webhooks = [WebhookConfig(url="https://example.com/hook", events=["unknown.event"])]
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 0  # warning, not error
            assert "unrecognized event type" in result.output

    def test_validate_webhook_valid(self, sample_config: AegisConfig):
        from aegis_qa.config.models import WebhookConfig

        sample_config.webhooks = [WebhookConfig(url="https://example.com/hook", events=["workflow.completed"])]
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 0
            assert "webhook(s) configured" in result.output

    def test_validate_with_path(self, sample_config: AegisConfig, tmp_path: Path):
        config_path = tmp_path / ".aegis.yaml"
        config_path.touch()
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config) as mock_load:
            result = runner.invoke(app, ["config", "validate", "--path", str(config_path)])
            assert result.exit_code == 0
            mock_load.assert_called_once_with(path=config_path)


class TestConfigShowCommand:
    def test_config_show(self, sample_config: AegisConfig):
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config):
            result = runner.invoke(app, ["config", "show"])
            assert result.exit_code == 0
            assert "Aegis" in result.output
            assert "QA Agent" in result.output
            assert "full_pipeline" in result.output

    def test_config_show_no_config(self):
        with patch("aegis_qa.config.loader.load_config", side_effect=FileNotFoundError("No config")):
            result = runner.invoke(app, ["config", "show"])
            assert result.exit_code == 1
            assert "No config" in result.output

    def test_config_show_invalid_config(self):
        with patch("aegis_qa.config.loader.load_config", side_effect=ValueError("Invalid config")):
            result = runner.invoke(app, ["config", "show"])
            assert result.exit_code == 1
            assert "Invalid config" in result.output

    def test_config_show_with_path(self, sample_config: AegisConfig, tmp_path: Path):
        config_path = tmp_path / ".aegis.yaml"
        config_path.touch()
        with patch("aegis_qa.config.loader.load_config", return_value=sample_config) as mock_load:
            result = runner.invoke(app, ["config", "show", "--path", str(config_path)])
            assert result.exit_code == 0
            mock_load.assert_called_once_with(path=config_path)
