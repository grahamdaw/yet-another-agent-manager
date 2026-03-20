"""libtmux wrapper for managing panes."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import libtmux

LOGS_DIR = Path("~/.config/yaam/logs")


class TmuxScriptError(RuntimeError):
    """Raised when a tmux setup script exits with a non-zero code."""


@dataclass
class PaneRef:
    """Lightweight reference to a specific tmux pane."""

    session_id: str
    window_id: str
    pane_id: str


def _server() -> libtmux.Server:
    """Return a libtmux Server instance."""
    return libtmux.Server()


def get_or_create_session(name: str) -> libtmux.Session:
    """Return the named tmux session, creating it if it does not exist.

    Idempotent: calling twice with the same name returns the same session.
    """
    server = _server()
    if server.has_session(name):
        session = server.find_where({"session_name": name})
        if session is not None:
            return session
    return server.new_session(session_name=name)


def run_setup_script(
    script_path: str | Path,
    worktree_path: str | Path,
    session_name: str,
) -> None:
    """Run the profile tmux setup script, logging output to a per-session log file.

    Calls ``script_path worktree_path`` as a subprocess.  Stdout and stderr
    are captured to ``~/.config/yaam/logs/<session_name>-setup.log``.
    Raises TmuxScriptError with captured stderr on non-zero exit.
    """
    logs_dir = LOGS_DIR.expanduser()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{session_name}-setup.log"

    with log_file.open("w") as fh:
        result = subprocess.run(
            [str(script_path), str(worktree_path)],
            stdout=fh,
            stderr=subprocess.PIPE,
            text=True,
        )

    if result.returncode != 0:
        raise TmuxScriptError(
            f"tmux setup script failed (exit {result.returncode}): {result.stderr.strip()}\n"
            f"Full log: {log_file}"
        )


def create_pane(session_name: str, window_name: str) -> PaneRef:
    """Create a new pane inside the named session/window.

    If *window_name* does not exist in the session it is created; otherwise
    the existing window is split to produce a new pane.  Returns a PaneRef
    for the newly created pane.

    Raises ValueError if the session does not exist.
    """
    server = _server()
    session = server.find_where({"session_name": session_name})
    if session is None:
        raise ValueError(f"tmux session '{session_name}' not found")

    window = session.find_where({"window_name": window_name})
    if window is None:
        window = session.new_window(window_name=window_name)
        pane = window.active_pane
    else:
        pane = window.split()

    if pane is None:
        raise RuntimeError(f"Failed to obtain a pane in window '{window_name}'")

    return PaneRef(
        session_id=pane.session_id,
        window_id=pane.window_id,
        pane_id=pane.pane_id,
    )


def send_keys(pane_ref: PaneRef, cmd: str) -> None:
    """Send *cmd* to the pane identified by *pane_ref*.

    Raises ValueError if the pane no longer exists.
    """
    server = _server()
    pane = server.panes.get(pane_id=pane_ref.pane_id)
    if pane is None:
        raise ValueError(f"pane '{pane_ref.pane_id}' not found")
    pane.send_keys(cmd)


def kill_pane(pane_ref: PaneRef) -> None:
    """Kill the pane identified by *pane_ref*.

    Idempotent: silently does nothing if the pane is already dead.
    """
    server = _server()
    pane = server.panes.get(pane_id=pane_ref.pane_id)
    if pane is not None:
        pane.kill()


def pane_alive(pane_ref: PaneRef) -> bool:
    """Return True if the pane identified by *pane_ref* still exists."""
    server = _server()
    return server.panes.get(pane_id=pane_ref.pane_id) is not None
