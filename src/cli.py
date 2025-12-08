"""
TriArchitect CLI - Command-line interface for the migration framework.

Provides commands for analyzing, planning, and migrating Java codebases.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src import __version__
from src.orchestrator import MigrationEngine
from src.shared.config import get_settings
from src.shared.logger import setup_logging

console = Console()


def print_banner() -> None:
    """Print the TriArchitect banner."""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║                       TriArchitect                             ║
║     Shared-State Multi-Agent Framework for Safe Migration      ║
╚════════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


@click.group()
@click.version_option(version=__version__, prog_name="triarchitect")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--log-format", type=click.Choice(["console", "json"]), default="console")
@click.pass_context
def main(ctx: click.Context, verbose: bool, log_format: str) -> None:
    """
    TriArchitect - Safe Legacy Code Migration Framework
    
    A multi-agent system for migrating Java 8 codebases to Java 17
    using the Typed Migration Graph (TMG) and Cyclic Consensus Protocol.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level=log_level, log_format=log_format)


@main.command()
@click.argument("repository", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory for results")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def analyze(
    ctx: click.Context,
    repository: str,
    output: Optional[str],
    output_format: str,
) -> None:
    """
    Analyze a Java repository without migrating.
    
    Runs the Archeologist agent to parse and analyze the codebase,
    populating the Typed Migration Graph (TMG).
    
    REPOSITORY: Path to the Java repository to analyze.
    """
    print_banner()
    
    console.print(f"\n[bold]Analyzing repository:[/bold] {repository}\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running analysis...", total=None)
        
        engine = MigrationEngine()
        result = engine.analyze_only(repository)
        
        progress.update(task, completed=True)
    
    if result["success"]:
        report = result["report"]
        stats = result["tmg_stats"]
        
        if output_format == "json":
            console.print_json(json.dumps(result, indent=2))
        else:
            # Print summary table
            table = Table(title="Analysis Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Files Analyzed", str(report["files_analyzed"]))
            table.add_row("Total Nodes", str(report["total_nodes"]))
            table.add_row("Total Edges", str(report["total_edges"]))
            table.add_row("Deprecated APIs", str(report["deprecated_apis"]))
            table.add_row("Parse Errors", str(len(report["parse_errors"])))
            table.add_row("Is DAG", "Yes" if stats.get("is_dag", False) else "No")
            table.add_row("Cycles Detected", str(stats.get("cycle_count", 0)))
            
            console.print(table)
            
            # State distribution
            if stats.get("state_distribution"):
                state_table = Table(title="State Distribution")
                state_table.add_column("State", style="cyan")
                state_table.add_column("Count", style="green")
                for state, count in stats["state_distribution"].items():
                    state_table.add_row(state, str(count))
                console.print(state_table)
        
        # Save output if specified
        if output:
            output_path = Path(output)
            output_path.mkdir(parents=True, exist_ok=True)
            with open(output_path / "analysis.json", "w") as f:
                json.dump(result, f, indent=2)
            console.print(f"\n[green]Results saved to:[/green] {output_path}")
        
        console.print("\n[bold green]✓ Analysis complete![/bold green]")
    else:
        console.print(f"\n[bold red]✗ Analysis failed:[/bold red] {result['error']}")
        sys.exit(1)


@main.command()
@click.argument("repository", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--dry-run", is_flag=True, help="Don't apply changes")
@click.option("--max-proposals", default=10, help="Maximum proposals to process")
@click.option("--source-version", default="8", help="Source Java version")
@click.option("--target-version", default="17", help="Target Java version")
@click.option("--no-docker", is_flag=True, help="Don't use Docker for validation")
@click.pass_context
def migrate(
    ctx: click.Context,
    repository: str,
    output: Optional[str],
    dry_run: bool,
    max_proposals: int,
    source_version: str,
    target_version: str,
    no_docker: bool,
) -> None:
    """
    Run full migration on a Java repository.
    
    Executes the complete TriArchitect pipeline:
    1. Discovery (Archeologist)
    2. Planning (Architect)
    3. Proposal generation (Architect)
    4. Validation (Validator)
    5. Consensus (All agents)
    6. Application (if not dry-run)
    
    REPOSITORY: Path to the Java repository to migrate.
    """
    print_banner()
    
    console.print(f"\n[bold]Migrating repository:[/bold] {repository}")
    console.print(f"[dim]Java {source_version} → Java {target_version}[/dim]")
    if dry_run:
        console.print("[yellow]Dry-run mode: changes will not be applied[/yellow]")
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)
        
        engine = MigrationEngine(
            source_version=source_version,
            target_version=target_version,
            use_docker=not no_docker,
        )
        
        progress.update(task, description="Running migration pipeline...")
        
        result = engine.run(
            repository_path=repository,
            output_dir=output,
            dry_run=dry_run,
            max_proposals=max_proposals,
        )
        
        progress.update(task, completed=True)
    
    # Print results
    if result.success:
        console.print(Panel(
            f"[bold green]Migration Successful![/bold green]\n\n"
            f"Nodes migrated: {result.nodes_migrated}\n"
            f"Proposals approved: {result.proposals_approved}\n"
            f"Execution time: {result.execution_time_seconds}s",
            title="Results",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]Migration Failed[/bold red]\n\n"
            f"Errors: {len(result.errors)}\n"
            f"Stages completed: {len(result.stages_completed)}",
            title="Results",
            border_style="red",
        ))
        for error in result.errors:
            console.print(f"  [red]• {error}[/red]")
    
    # Show stages
    stage_table = Table(title="Pipeline Stages")
    stage_table.add_column("Stage", style="cyan")
    stage_table.add_column("Status", style="green")
    for stage in result.stages_completed:
        stage_table.add_row(stage, "✓ Complete")
    console.print(stage_table)
    
    if result.report_path:
        console.print(f"\n[dim]Report saved to:[/dim] {result.report_path}")
    
    if not result.success:
        sys.exit(1)


@main.command()
@click.argument("repository", type=click.Path(exists=True))
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def validate(
    ctx: click.Context,
    repository: str,
    output_format: str,
) -> None:
    """
    Validate a Java repository by running tests.
    
    Runs the Validator agent to execute Maven tests and
    check for compilation and test errors.
    
    REPOSITORY: Path to the Maven project to validate.
    """
    print_banner()
    
    console.print(f"\n[bold]Validating repository:[/bold] {repository}\n")
    
    from src.agents.validator import ValidatorAgent
    from src.tmg import TypedMigrationGraph
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running validation...", total=None)
        
        tmg = TypedMigrationGraph(name="validation")
        validator = ValidatorAgent(tmg=tmg)
        result = validator.execute(project_path=repository)
        
        progress.update(task, completed=True)
    
    if result.success:
        report = result.data
        test_result = report.test_result
        
        if output_format == "json":
            console.print_json(json.dumps(report.to_dict(), indent=2))
        else:
            table = Table(title="Validation Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            if test_result:
                table.add_row("Compilation", "✓ Success" if report.compilation_success else "✗ Failed")
                table.add_row("Tests Run", str(test_result.test_count))
                table.add_row("Tests Passed", str(test_result.passed_count))
                table.add_row("Tests Failed", str(test_result.failed_count))
                table.add_row("Tests Skipped", str(test_result.skipped_count))
                table.add_row("Duration", f"{test_result.duration_seconds}s")
                table.add_row("Recommendation", report.approval_recommendation.upper())
            
            console.print(table)
            
            if report.issues:
                console.print("\n[yellow]Issues:[/yellow]")
                for issue in report.issues:
                    console.print(f"  • {issue}")
        
        console.print("\n[bold green]✓ Validation complete![/bold green]")
    else:
        console.print(f"\n[bold red]✗ Validation failed:[/bold red] {result.error}")
        sys.exit(1)


@main.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show version and configuration information."""
    print_banner()
    
    settings = get_settings()
    
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Version", __version__)
    table.add_row("LLM Provider", settings.llm_provider)
    table.add_row("Consensus Threshold", str(settings.consensus_threshold))
    table.add_row("Max Iterations", str(settings.consensus_max_iterations))
    table.add_row("Docker Image", settings.docker_image)
    table.add_row("Log Level", settings.log_level)
    
    console.print(table)


if __name__ == "__main__":
    main()
