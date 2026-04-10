"""libtmux wrapper for managing tmux sessions.

yaam tracks agents at the **tmux session** level — each agent owns its own
dedicated tmux session, so everything lifecycle-related (liveness, attach,
teardown) keys off the session name. Layout inside a session (windows,
panes) is entirely the responsibility of the profile's ``tmux_setup_script``.
"""

import subprocess
from pathlib import Path

import libtmux
from libtmux.exc import ObjectDoesNotExist

# Detached `tmux new-session -d` dimensions via libtmux `x` / `y`. Large enough for setup
# scripts to split panes before any client attaches (avoids tmux "no space for new pane").
NEW_SESSION_WIDTH = 1000
NEW_SESSION_HEIGHT = 500


class TmuxScriptError(RuntimeError):
    """Raised when a tmux setup script exits with a non-zero code."""


def _server() -> libtmux.Server:
    """Return a libtmux Server instance."""
    return libtmux.Server()


def _get(collection, **kwargs):
    """Return collection.get(**kwargs), or None if the object does not exist."""
    try:
        return collection.get(**kwargs)
    except ObjectDoesNotExist:
        return None


def get_or_create_session(name: str, start_directory: str | Path | None = None) -> libtmux.Session:
    """Return the named tmux session, creating it if it does not exist.

    Idempotent: calling twice with the same name returns the same session.
    If *start_directory* is given it is used as the working directory for the
    initial window of a newly created session.
    """
    server = _server()
    if server.has_session(name):
        session = _get(server.sessions, session_name=name)
        if session is not None:
            return session
    kwargs: dict = {"session_name": name, "x": NEW_SESSION_WIDTH, "y": NEW_SESSION_HEIGHT}
    if start_directory is not None:
        kwargs["start_directory"] = str(start_directory)
    return server.new_session(**kwargs)


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
        raise TmuxScriptError(f"tmux setup script failed (exit {result.returncode})")


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
