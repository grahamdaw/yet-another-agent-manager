"""CLI entry point for the agent tool."""

import typer
from rich.console import Console

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
    console.print("[bold]agent profile list[/bold] is not yet implemented")


@profile_app.command("validate")
def profile_validate(
    name: str = typer.Argument(help="Profile name to validate"),
) -> None:
    """Validate a profile configuration."""
    console.print(f"[bold]agent profile validate[/bold] is not yet implemented (name={name})")
