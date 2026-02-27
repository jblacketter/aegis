"""Aegis CLI entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="aegis",
    help="Aegis — The AI Quality Control Plane",
    no_args_is_help=True,
)
console = Console()


@app.command()
def status() -> None:
    """Show all registered services and their health status."""
    from aegis_qa.config.loader import load_config
    from aegis_qa.registry.registry import ServiceRegistry

    try:
        config = load_config()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    registry = ServiceRegistry(config)
    statuses = registry.get_all_statuses_sync(timeout=5.0)

    table = Table(title="Aegis Service Status")
    table.add_column("Service", style="bold")
    table.add_column("URL")
    table.add_column("Status")
    table.add_column("Latency")

    for s in statuses:
        label = s.status_label
        if label == "healthy":
            style = "green"
        elif label == "unreachable":
            style = "yellow"
        else:
            style = "red"
        latency = f"{s.health.latency_ms:.0f}ms" if s.health and s.health.latency_ms else "—"
        table.add_row(s.name, s.url, f"[{style}]{label}[/{style}]", latency)

    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
) -> None:
    """Start the Aegis API server and serve the landing page."""
    import uvicorn

    console.print(f"[bold]Aegis[/bold] starting on http://{host}:{port}")
    uvicorn.run("aegis_qa.api.app:app", host=host, port=port, reload=False)


@app.command("run")
def run_workflow(
    workflow: str = typer.Argument(help="Name of the workflow to execute"),
) -> None:
    """Execute a named workflow pipeline."""
    from aegis_qa.config.loader import load_config
    from aegis_qa.events.emitter import create_cli_emitter
    from aegis_qa.workflows.pipeline import PipelineRunner

    try:
        config = load_config()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if workflow not in config.workflows:
        console.print(f"[red]Unknown workflow: {workflow}[/red]")
        console.print(f"Available: {', '.join(config.workflows.keys()) or 'none'}")
        raise typer.Exit(1)

    emitter = create_cli_emitter(config)
    runner = PipelineRunner(config, emitter=emitter)
    result = asyncio.run(runner.run(workflow))

    console.print(f"\n[bold]Workflow:[/bold] {result.workflow_name}")
    for step in result.steps:
        if step.skipped:
            icon = "[dim]⊘[/dim]"
        elif step.success:
            icon = "[green]✓[/green]"
        else:
            icon = "[red]✗[/red]"
        console.print(f"  {icon} {step.step_type} ({step.service})")
        if step.error:
            console.print(f"    [red]{step.error}[/red]")
        if step.skipped and step.data.get("message"):
            console.print(f"    [dim]{step.data['message']}[/dim]")

    if result.success:
        console.print("\n[green bold]Pipeline completed successfully.[/green bold]")
    else:
        console.print("\n[red bold]Pipeline completed with errors.[/red bold]")
        raise typer.Exit(1)


config_app = typer.Typer(name="config", help="Configuration commands")
app.add_typer(config_app)


@config_app.command("validate")
def config_validate(
    path: Path | None = typer.Option(None, "--path", "-p", help="Path to .aegis.yaml"),
) -> None:
    """Validate configuration file."""
    from urllib.parse import urlparse

    import yaml

    from aegis_qa.config.loader import load_config
    from aegis_qa.workflows.steps import STEP_REGISTRY

    errors: list[str] = []
    try:
        config = load_config(path=path)
        console.print("[green]\u2713[/green] YAML parses correctly")
        console.print("[green]\u2713[/green] Pydantic validation passes")
    except FileNotFoundError as exc:
        console.print(f"[red]\u2717 {exc}[/red]")
        raise typer.Exit(1)
    except yaml.YAMLError as exc:
        console.print(f"[red]\u2717 YAML parsing failed: {exc}[/red]")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print("[green]\u2713[/green] YAML parses correctly")
        console.print(f"[red]\u2717 Pydantic validation failed: {exc}[/red]")
        raise typer.Exit(1)

    # Check service URLs are valid
    for key, entry in config.services.items():
        parsed = urlparse(entry.url)
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"Service '{key}': invalid URL '{entry.url}'")
        else:
            console.print(f"[green]\u2713[/green] Service '{key}' URL is valid")

    # Check workflow step services exist
    for wf_key, wf in config.workflows.items():
        for i, step in enumerate(wf.steps):
            if step.service not in config.services:
                errors.append(f"Workflow '{wf_key}' step {i} references unknown service '{step.service}'")

            if step.type not in STEP_REGISTRY:
                errors.append(f"Workflow '{wf_key}' step {i} references unknown step type '{step.type}'")

    # Check webhook config
    known_event_types = {"workflow.started", "step.completed", "workflow.completed", "failure.detected", "*"}
    warnings: list[str] = []
    for i, wh in enumerate(config.webhooks):
        parsed = urlparse(wh.url)
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"Webhook {i}: invalid URL '{wh.url}'")
        for evt in wh.events:
            if evt not in known_event_types:
                warnings.append(f"Webhook {i}: unrecognized event type '{evt}'")

    if not errors:
        console.print("[green]\u2713[/green] All workflow step services exist")
        console.print("[green]\u2713[/green] All workflow step types exist")
        if config.webhooks:
            console.print(f"[green]\u2713[/green] {len(config.webhooks)} webhook(s) configured")
        for w in warnings:
            console.print(f"[yellow]! {w}[/yellow]")
        console.print("\n[green bold]Configuration is valid.[/green bold]")
    else:
        for err in errors:
            console.print(f"[red]\u2717 {err}[/red]")
        console.print(f"\n[red bold]{len(errors)} validation error(s) found.[/red bold]")
        raise typer.Exit(1)


@config_app.command("show")
def config_show(
    path: Path | None = typer.Option(None, "--path", "-p", help="Path to .aegis.yaml"),
) -> None:
    """Print resolved configuration."""
    from aegis_qa.config.loader import load_config

    try:
        config = load_config(path=path)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Aegis[/bold] {config.aegis.name} v{config.aegis.version}\n")

    console.print("[bold]LLM:[/bold]")
    console.print(f"  Ollama URL: {config.llm.ollama_base_url}")
    console.print(f"  Model: {config.llm.default_model}")
    console.print(f"  Timeout: {config.llm.timeout}s\n")

    console.print("[bold]Services:[/bold]")
    for key, entry in config.services.items():
        console.print(f"  {key}: {entry.name} @ {entry.url}")
        if entry.features:
            console.print(f"    Features: {', '.join(entry.features)}")

    console.print("\n[bold]Workflows:[/bold]")
    for key, wf in config.workflows.items():
        steps = " → ".join(s.type for s in wf.steps)
        console.print(f"  {key}: {wf.name} [{steps}]")


def main() -> None:
    app()
