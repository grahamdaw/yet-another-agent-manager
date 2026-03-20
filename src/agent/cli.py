"""CLI entry point for the agent tool."""

import typer
from rich.console import Console
from rich.table import Table

from agent import profile as profile_mod
from agent.profile import ProfileValidationError

app = typer.Typer(
    name="agent",
    help="Manage tmux sessions and git worktrees for multi-agent orchestration.",
    no_args_is_help=True,
)
console = Console()

profile_app = typer.Typer(help="Manage agent profiles.", no_args_is_help=True)
app.add_typer(profile_app, name="profile")


@app.command()
def new(
    name: str = typer.Argument(help="Name for the new agent session"),
    profile: str = typer.Option(..., "--profile", "-p", help="Profile to use"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Override branch name"),
) -> None:
    """Spawn a new agent session."""
    console.print(f"[bold]agent new[/bold] is not yet implemented (name={name}, profile={profile})")


@app.command("list")
def list_sessions() -> None:
    """List active agent sessions."""
    console.print("[bold]agent list[/bold] is not yet implemented")


@app.command()
def kill(name: str = typer.Argument(help="Name of the agent session to kill")) -> None:
    """Kill an agent session and clean up its resources."""
    console.print(f"[bold]agent kill[/bold] is not yet implemented (name={name})")


@app.command()
def attach(name: str = typer.Argument(help="Name of the agent session to attach to")) -> None:
    """Attach to an existing agent session."""
    console.print(f"[bold]agent attach[/bold] is not yet implemented (name={name})")


@app.command()
def sync() -> None:
    """Sync session state with tmux and worktree status."""
    console.print("[bold]agent sync[/bold] is not yet implemented")


@profile_app.command("list")
def profile_list() -> None:
    """List available agent profiles."""
    profile_mod._ensure_example_profile()
    profiles = profile_mod.list_profiles()
    if not profiles:
        console.print(
            "[yellow]No profiles found.[/yellow] Add a .toml file to ~/.config/agent/profiles/"
        )
        return
    table = Table(title="Agent Profiles", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Repo Path")
    table.add_column("Branch Prefix")
    for p in profiles:
        table.add_row(p.name, p.description, str(p.repo_path), p.default_branch_prefix)
    console.print(table)


@profile_app.command("validate")
def profile_validate(
    name: str = typer.Argument(help="Profile name to validate"),
) -> None:
    """Validate a profile configuration."""
    try:
        p = profile_mod.load(name)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    try:
        issues = profile_mod.validate(p)
    except ProfileValidationError as exc:
        console.print(f"[red]Validation error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if issues:
        console.print(f"[yellow]Profile '{name}' has issues:[/yellow]")
        for issue in issues:
            console.print(f"  [red]•[/red] {issue}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Profile '{name}' is valid.")
