"""libtmux wrapper for managing panes."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import libtmux
from libtmux.exc import ObjectDoesNotExist

# Detached `tmux new-session -d` dimensions via libtmux `x` / `y`. Large enough for setup
# scripts to split panes before any client attaches (avoids tmux "no space for new pane").
NEW_SESSION_WIDTH = 1000
NEW_SESSION_HEIGHT = 500


class TmuxScriptError(RuntimeError):
    """Raised when a tmux setup script exits with a non-zero code."""


@dataclass(frozen=True)
class PaneRef:
    """Immutable reference to a specific tmux pane."""

    session_id: str
    window_id: str
    pane_id: str


def _server() -> libtmux.Server:
    """Return a libtmux Server instance."""
    return libtmux.Server()


def _get(collection, **kwargs):
    """Return collection.get(**kwargs), or None if the object does not exist."""
    try:
        return collection.get(**kwargs)
    except ObjectDoesNotExist:
        return None


def get_or_create_session(name: str) -> libtmux.Session:
    """Return the named tmux session, creating it if it does not exist.

    Idempotent: calling twice with the same name returns the same session.
    """
    server = _server()
    if server.has_session(name):
        session = _get(server.sessions, session_name=name)
        if session is not None:
            return session
    return server.new_session(
        session_name=name,
        x=NEW_SESSION_WIDTH,
        y=NEW_SESSION_HEIGHT,
    )


def run_setup_script(
    script_path: str | Path,
    worktree_path: str | Path,
    session_name: str,
) -> None:
    """Run the profile tmux setup script, streaming output to the terminal.

    Calls ``script_path session_name worktree_path`` as a subprocess.
    Output is streamed directly to stdout/stderr.
    Raises TmuxScriptError on non-zero exit.
    """
    result = subprocess.run(
        [str(script_path), str(session_name), str(worktree_path)],
        stdout=None,
        stderr=None,
        text=True,
    )

    if result.returncode != 0:
        raise TmuxScriptError(
            f"tmux setup script failed (exit {result.returncode})"
        )


def create_pane(session_name: str, window_name: str) -> PaneRef:
    """Create or find a window in the session and return a reference to its active pane.

    If *window_name* already exists, splits it to create a new pane.
    If it does not exist, creates a new window.
    Raises ValueError if the session is not found.
    """
    server = _server()
    session = _get(server.sessions, session_name=session_name)
    if session is None:
        raise ValueError(f"tmux session '{session_name}' not found")
    window = _get(session.windows, window_name=window_name)
    if window is None:
        window = session.new_window(window_name=window_name)
        pane = window.active_pane
    else:
        pane = window.split()
    return PaneRef(
        session_id=pane.session_id,
        window_id=pane.window_id,
        pane_id=pane.pane_id,
    )


def send_keys(pane_ref: PaneRef, keys: str) -> None:
    """Send *keys* to the pane identified by *pane_ref*.

    Raises ValueError if the pane no longer exists.
    """
    server = _server()
    pane = _get(server.panes, pane_id=pane_ref.pane_id)
    if pane is None:
        raise ValueError(f"tmux pane '{pane_ref.pane_id}' not found")
    pane.send_keys(keys)


def pane_alive(pane_ref: PaneRef | None) -> bool:
    """Return True if the pane identified by *pane_ref* still exists."""
    if pane_ref is None:
        return False
    server = _server()
    return _get(server.panes, pane_id=pane_ref.pane_id) is not None


def kill_pane(pane_ref: PaneRef | None) -> None:
    """Kill the pane identified by *pane_ref*. No-op if already gone."""
    if pane_ref is None:
        return
    server = _server()
    pane = _get(server.panes, pane_id=pane_ref.pane_id)
    if pane is not None:
        pane.kill()


def session_alive(session_name: str) -> bool:
    """Return True if the named tmux session still exists."""
    return _server().has_session(session_name)


def kill_session(session_name: str) -> None:
    """Kill the named tmux session. Idempotent: no-op if it does not exist."""
    server = _server()
    if server.has_session(session_name):
        session = _get(server.sessions, session_name=session_name)
        if session is not None:
            session.kill()
