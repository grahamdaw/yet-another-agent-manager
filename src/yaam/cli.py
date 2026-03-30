"""CLI entry point for the agent tool."""

import contextlib
from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

from yaam import config as config_mod
from yaam import init as init_mod
from yaam import profile as profile_mod
from yaam import tmux as tmux_mod
from yaam import worktrunk
from yaam.init import InitScriptError  # noqa: F401 (re-exported for callers)
from yaam.profile import ProfileValidationError
from yaam.session import AgentSession, SessionStore
from yaam.utils import sanitize_name

app = typer.Typer(
    name="yaam",
    help="Manage tmux sessions and git worktrees for multi-agent orchestration.",
    no_args_is_help=True,
)
console = Console()

profile_app = typer.Typer(help="Manage agent profiles.", no_args_is_help=True)
app.add_typer(profile_app, name="profile")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_key(name: str) -> str:
    """Return the canonical internal session key for a user-supplied name."""
    return sanitize_name(name)


def _set_terminal_title(title: str) -> None:
    """Set the terminal emulator window title via OSC 2 escape."""
    import sys

    sys.stdout.write(f"\033]2;{title}\007")
    sys.stdout.flush()


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
    # --- Reject purely numeric names ------------------------------------
    if name.isdigit():
        console.print(
            f"[red]Error:[/red] Session name '{name}' is not allowed — purely numeric names"
            " conflict with session indexes.\n"
            "       Choose a descriptive name such as"
            f" 'feature-{name}' or 'worker-{name}'."
        )
        raise typer.Exit(1)

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

    branch_name = branch or name
    tmux_session = sanitize_name(name)

    worktree_info = None
    pane_ref = None

    try:
        with console.status(f"Setting up worktree for branch '[cyan]{branch_name}[/cyan]'..."):
            worktree_info = worktrunk.create(branch_name, p.repo_path)

        with console.status("Running init script..."):
            init_mod.run(p.init_script, p.repo_path, worktree_info.path, p.init_env, name)

        with console.status("Running tmux setup script..."):
            tmux_mod.get_or_create_session(tmux_session)
            tmux_mod.run_setup_script(p.tmux_setup_script, worktree_info.path, tmux_session)

        pane_ref = tmux_mod.create_pane(tmux_session, sanitize_name(name))

        SessionStore().add_exclusive(
            AgentSession(
                key=tmux_session,
                display_name=name,
                branch=branch_name,
                profile_name=profile,
                worktree_path=worktree_info.path,
                tmux_session=tmux_session,
                tmux_pane_ref=pane_ref,
                created_at=datetime.now(UTC),
            )
        )
        console.print(
            f"[green]✓[/green] Agent '[bold]{name}[/bold]' spawned on branch '{branch_name}'"
        )

    except KeyError:
        console.print(
            f"\n[red]Error:[/red] Session '{name}' already exists."
            f" Use [bold]yaam kill {name}[/bold] first."
        )
        if pane_ref is not None:
            with contextlib.suppress(Exception):
                tmux_mod.kill_pane(pane_ref)
        if worktree_info is not None:
            with contextlib.suppress(Exception):
                worktrunk.remove(worktree_info.path)
        raise typer.Exit(1)
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
            "[yellow]No active sessions.[/yellow] Use [bold]yaam new[/bold] to spawn one."
        )
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Profile")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("Age")
    table.add_column("tmux session")

    for idx, s in enumerate(sessions):
        try:
            alive = tmux_mod.pane_alive(s.tmux_pane_ref)
            status = "[green]alive[/green]" if alive else "[red]dead[/red]"
        except Exception:
            status = s.status

        table.add_row(
            str(idx),
            s.display_name,
            s.profile_name,
            s.branch,
            status,
            _age(s.created_at),
            s.tmux_session,
        )

    console.print(table)


@app.command()
def kill(name: str = typer.Argument(help="Name of the agent session to kill")) -> None:
    """Kill an agent session and clean up its resources."""
    store = SessionStore()
    session = store.get(_session_key(name))
    if session is None:
        console.print(f"[red]Error:[/red] No session named '{name}'")
        raise typer.Exit(1)

    with contextlib.suppress(Exception):
        tmux_mod.kill_pane(session.tmux_pane_ref)

    if worktrunk.wt_available():
        with contextlib.suppress(Exception):
            worktrunk.remove(session.worktree_path)

    store.remove(session.key)
    console.print(f"[green]✓[/green] Agent '[bold]{session.display_name}[/bold]' killed.")


@app.command()
def attach(
    name: str = typer.Argument(help="Name or index (from 'yaam list') of the session to attach to"),
) -> None:
    """Attach to an existing agent session."""
    store = SessionStore()

    # Try to resolve by index first (purely numeric argument → index lookup).
    # Purely numeric names are rejected at creation time, so there is no ambiguity.
    session = None
    try:
        index = int(name)
        session = store.get_by_index(index)
        if session is None:
            console.print(f"[red]Error:[/red] No session at index {index}")
            raise typer.Exit(1)
    except ValueError:
        session = store.get(_session_key(name))
        if session is None:
            console.print(f"[red]Error:[/red] No session named '{name}'")
            raise typer.Exit(1) from None

    if not tmux_mod.pane_alive(session.tmux_pane_ref):
        console.print(
            f"[red]Error:[/red] Pane for session '{name}' is dead."
            " Run [bold]yaam sync --fix[/bold]."
        )
        raise typer.Exit(1)

    import os
    import subprocess

    if os.environ.get("TMUX"):
        _set_terminal_title(f"yaam: {session.display_name}")
        subprocess.run(["tmux", "switch-client", "-t", session.tmux_session], check=False)
    else:
        _set_terminal_title(f"yaam: {session.display_name}")
        subprocess.run(["tmux", "attach-session", "-t", session.tmux_session], check=False)
        _set_terminal_title("")  # reset on detach


@app.command()
def sync(
    fix: bool = typer.Option(False, "--fix", help="Remove orphaned sessions from the store"),
) -> None:
    """Sync session state with tmux and worktree status."""
    sessions = SessionStore().list()
    store = SessionStore()

    if not sessions:
        console.print("[yellow]No sessions in store.[/yellow]")
        return

    orphaned = []
    live = []

    for s in sessions:
        try:
            alive = tmux_mod.pane_alive(s.tmux_pane_ref)
        except Exception:
            alive = False
        worktree_exists = s.worktree_path.exists()

        if not alive or not worktree_exists:
            orphaned.append((s, alive, worktree_exists))
        else:
            live.append(s)

    if not orphaned:
        console.print(f"[green]✓[/green] All {len(live)} session(s) healthy.")
        return

    table = Table(show_header=True, header_style="bold yellow")
    table.add_column("Name", style="bold")
    table.add_column("Branch")
    table.add_column("tmux session")
    table.add_column("Worktree")

    for s, session_ok, wt_ok in orphaned:
        table.add_row(
            s.display_name,
            s.branch,
            "[green]alive[/green]" if session_ok else "[red]dead[/red]",
            "[green]exists[/green]" if wt_ok else "[red]missing[/red]",
        )

    console.print(f"[yellow]Found {len(orphaned)} orphaned session(s):[/yellow]")
    console.print(table)

    if fix:
        for s, _, _ in orphaned:
            store.remove(s.key)
        console.print(f"[green]✓[/green] Removed {len(orphaned)} orphaned session(s) from store.")


# ---------------------------------------------------------------------------
# Orchestrator command
# ---------------------------------------------------------------------------


@app.command()
def run(
    goal: str = typer.Argument(help="High-level goal for the agent swarm"),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="Default profile for spawned agents"
    ),
) -> None:
    """Run a multi-agent orchestration session for a given goal."""
    from yaam.orchestrator.graph import build_graph
    from yaam.orchestrator.models import OrchestratorState

    initial_state: OrchestratorState = {
        "goal": goal,
        "tasks": [],
        "agents": [],
        "results": [],
        "phase": "planning",
        "error": None,
    }

    console.print(f"[cyan]Orchestrating:[/cyan] {goal}")
    if profile:
        console.print(f"[dim]Default profile:[/dim] {profile}")

    graph = build_graph()

    try:
        with console.status("Running orchestrator..."):
            final_state = graph.invoke(initial_state)
    except Exception as exc:
        console.print(f"[red]Orchestration failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    results = final_state.get("results", [])
    if not results:
        console.print("[yellow]No results collected.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="bold")
    table.add_column("Status")
    table.add_column("Output")

    for r in results:
        colour = "green" if r["status"] == "success" else "red"
        table.add_row(
            r["agent_name"],
            f"[{colour}]{r['status']}[/{colour}]",
            r["output"][:120],
        )

    console.print(table)
    console.print(f"[green]✓[/green] Orchestration complete — phase: {final_state.get('phase')}")


# ---------------------------------------------------------------------------
# Doctor command
# ---------------------------------------------------------------------------


@app.command()
def doctor() -> None:
    """Check that all required tools and configuration are in place."""
    import shutil

    import libtmux

    all_ok = True

    def _check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal all_ok
        if ok:
            console.print(f"  [green]✓[/green] {label}")
        else:
            console.print(f"  [red]✗[/red] {label}" + (f" — {detail}" if detail else ""))
            all_ok = False

    console.print("[bold]Checking environment...[/bold]\n")

    # wt (Worktrunk) available?
    _check(
        "wt (Worktrunk) installed", shutil.which("wt") is not None, "run: brew install worktrunk"
    )

    # tmux available?
    _check("tmux installed", shutil.which("tmux") is not None, "run: brew install tmux")

    # tmux server reachable?
    try:
        server = libtmux.Server()
        server.sessions  # noqa: B018  # triggers connection; AttributeError if not running
        tmux_ok = True
    except Exception:
        tmux_ok = False
    _check("tmux server running", tmux_ok, "start tmux first")

    # Config loads without error?
    try:
        cfg = config_mod.load_config()
        config_ok = True
        config_detail = f"tmux session: '{cfg.tmux_session_name}'"
    except Exception as exc:
        config_ok = False
        config_detail = str(exc)
    _check("config loads cleanly", config_ok, config_detail)

    # At least one valid profile?
    profile_mod._ensure_example_profile()
    profiles = profile_mod.list_profiles()
    valid_profiles = []
    for p in profiles:
        issues = profile_mod.validate(p)
        if not issues:
            valid_profiles.append(p.name)
    _check(
        f"at least one valid profile ({len(valid_profiles)}/{len(profiles)} valid)",
        bool(valid_profiles),
        "run: yaam profile validate <name>",
    )

    console.print()
    if all_ok:
        console.print("[bold green]All checks passed.[/bold green]")
    else:
        console.print("[bold red]Some checks failed.[/bold red] Fix the issues above and re-run.")
        raise typer.Exit(1)


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
            "[yellow]No profiles found.[/yellow] Add a .toml file to ~/.config/yaam/profiles/"
        )
        return
    table = Table(title="Agent Profiles", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Repo Path")
    for p in profiles:
        table.add_row(p.name, p.description, str(p.repo_path))
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
