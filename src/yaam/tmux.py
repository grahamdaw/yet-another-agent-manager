"""libtmux wrapper for managing panes."""

import re
import subprocess
from pathlib import Path

import libtmux

LOGS_DIR = Path("~/.config/yaam/logs")


class TmuxScriptError(RuntimeError):
    """Raised when a tmux setup script exits with a non-zero code."""


def _server() -> libtmux.Server:
    """Return a libtmux Server instance."""
    return libtmux.Server()


def get_or_create_session(name: str) -> libtmux.Session:
    """Return the named tmux session, creating it if it does not exist.

    Idempotent: calling twice with the same name returns the same session.
    """
    server = _server()
    if server.has_session(name):
        session = server.sessions.get(session_name=name)
        if session is not None:
            return session
    return server.new_session(session_name=name)


def run_setup_script(
    script_path: str | Path,
    worktree_path: str | Path,
    session_name: str,
    agent_name: str,
) -> None:
    """Run the profile tmux setup script, logging output to a per-session log file.

    Calls ``script_path session_name worktree_path`` as a subprocess.  Stdout
    and stderr are appended to ``~/.config/yaam/logs/<agent_name>.log``.
    Raises TmuxScriptError on non-zero exit.
    """
    logs_dir = LOGS_DIR.expanduser()
    logs_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[/\\:*?"<>|]', "-", agent_name)
    log_file = logs_dir / f"{safe_name}.log"

    with log_file.open("a") as fh:
        result = subprocess.run(
            [str(script_path), str(session_name), str(worktree_path)],
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if result.returncode != 0:
        raise TmuxScriptError(
            f"tmux setup script failed (exit {result.returncode})\n"
            f"Log: {log_file}"
        )


def session_alive(session_name: str) -> bool:
    """Return True if the named tmux session still exists."""
    return _server().has_session(session_name)


def kill_session(session_name: str) -> None:
    """Kill the named tmux session. Idempotent: no-op if it does not exist."""
    server = _server()
    if server.has_session(session_name):
        session = server.sessions.get(session_name=session_name)
        if session is not None:
            session.kill()
