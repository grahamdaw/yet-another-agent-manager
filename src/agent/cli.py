"""CLI entry point for the agent tool."""

import contextlib
from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

from agent import config as config_mod
from agent import init as init_mod
from agent import profile as profile_mod
from agent import tmux as tmux_mod
from agent import worktrunk
from agent.init import InitScriptError  # noqa: F401 (re-exported for callers)
from agent.profile import ProfileValidationError
from agent.session import AgentSession, SessionStore

app = typer.Typer(
    name="agent",
    help="Manage tmux sessions and git worktrees for multi-agent orchestration.",
    no_args_is_help=True,
)
console = Console()

profile_app = typer.Typer(help="Manage agent profiles.", no_args_is_help=True)
app.add_typer(profile_app, name="profile")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _age(created_at: datetime) -> str:
    """Return a human-readable age string (e.g. '3d', '2h', '5m')."""
    delta = datetime.now(UTC) - created_at.astimezone(UTC)
    if delta.days > 0:
        return f"{delta.days}d"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours}h"
    return f"{delta.seconds // 60}m"


# ---------------------------------------------------------------------------
# Core commands
# ---------------------------------------------------------------------------


@app.command()
def new(
    name: str = typer.Argument(help="Name for the new agent session"),
    profile: str = typer.Option(..., "--profile", "-p", help="Profile to use"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Override branch name"),
) -> None:
    """Spawn a new agent session."""
    # --- Load & validate profile ----------------------------------------
    try:
        p = profile_mod.load(profile)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    try:
        issues = profile_mod.validate(p)
    except ProfileValidationError as exc:
        console.print(f"[red]Validation error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if issues:
        console.print(f"[yellow]Profile '{profile}' has issues:[/yellow]")
        for issue in issues:
            console.print(f"  [red]•[/red] {issue}")
        raise typer.Exit(1)

    branch_name = branch or f"{p.default_branch_prefix}{name}"
    cfg = config_mod.load_config()

    worktree_info = None
    pane_ref = None

    try:
        with console.status(f"Creating worktree for branch '[cyan]{branch_name}[/cyan]'..."):
            worktree_info = worktrunk.create(branch_name, p.repo_path)

        with console.status("Running tmux setup script..."):
            tmux_mod.get_or_create_session(cfg.tmux_session_name)
            tmux_mod.run_setup_script(
                p.tmux_setup_script, worktree_info.path, cfg.tmux_session_name
            )

        with console.status(f"Creating pane for '[cyan]{name}[/cyan]'..."):
            pane_ref = tmux_mod.create_pane(cfg.tmux_session_name, name)

        with console.status("Running init script..."):
            init_mod.run(p.init_script, p.repo_path, worktree_info.path, p.init_env, name)

        SessionStore().add(
            AgentSession(
                name=name,
                branch=branch_name,
                profile_name=profile,
                worktree_path=worktree_info.path,
                tmux_session=cfg.tmux_session_name,
                tmux_pane_ref=pane_ref,
                created_at=datetime.now(UTC),
            )
        )
        console.print(
            f"[green]✓[/green] Agent '[bold]{name}[/bold]' spawned on branch '{branch_name}'"
        )

    except Exception as exc:
        console.print(f"\n[red]Spawn failed:[/red] {exc}")
        if pane_ref is not None:
            with contextlib.suppress(Exception):
                tmux_mod.kill_pane(pane_ref)
        if worktree_info is not None:
            with contextlib.suppress(Exception):
                worktrunk.remove(worktree_info.path)
        raise typer.Exit(1) from exc


@app.command("list")
def list_sessions(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List active agent sessions."""
    import json

    sessions = SessionStore().list()

    if json_output:
        data = [s.model_dump(mode="json") for s in sessions]
        console.print_json(json.dumps(data))
        return

    if not sessions:
        console.print(
            "[yellow]No active sessions.[/yellow] Use [bold]agent new[/bold] to spawn one."
        )
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Profile")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("Age")
    table.add_column("Pane")

    for s in sessions:
        try:
            alive = tmux_mod.pane_alive(s.tmux_pane_ref)
            status = "[green]alive[/green]" if alive else "[red]dead[/red]"
        except Exception:
            status = s.status

        table.add_row(
            s.name,
            s.profile_name,
            s.branch,
            status,
            _age(s.created_at),
            s.tmux_pane_ref.pane_id,
        )

    console.print(table)


@app.command()
def kill(name: str = typer.Argument(help="Name of the agent session to kill")) -> None:
    """Kill an agent session and clean up its resources."""
    store = SessionStore()
    session = store.get(name)
    if session is None:
        console.print(f"[red]Error:[/red] No session named '{name}'")
        raise typer.Exit(1)

    with contextlib.suppress(Exception):
        tmux_mod.kill_pane(session.tmux_pane_ref)

    if worktrunk.wt_available():
        with contextlib.suppress(Exception):
            worktrunk.remove(session.worktree_path)

    store.remove(name)
    console.print(f"[green]✓[/green] Agent '[bold]{name}[/bold]' killed.")


@app.command()
def attach(name: str = typer.Argument(help="Name of the agent session to attach to")) -> None:
    """Attach to an existing agent session."""
    console.print(f"[bold]agent attach[/bold] is not yet implemented (name={name})")


@app.command()
def sync() -> None:
    """Sync session state with tmux and worktree status."""
    console.print("[bold]agent sync[/bold] is not yet implemented")


# ---------------------------------------------------------------------------
# Profile sub-commands
# ---------------------------------------------------------------------------


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
