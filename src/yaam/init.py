"""Post-init script runner."""

import os
import subprocess
from pathlib import Path

LOGS_DIR = Path("~/.config/agent/logs")


class InitScriptError(RuntimeError):
    """Raised when the post-init script exits with a non-zero code."""


def run(
    script_path: str | Path,
    repo_path: str | Path,
    worktree_path: str | Path,
    env: dict[str, str],
    session_name: str,
) -> None:
    """Run the post-init script.

    Calls ``script_path repo_path worktree_path`` as a subprocess.
    Merges *env* with the current process environment.  Full output
    (stdout + stderr combined) is logged to
    ``~/.config/agent/logs/<session_name>-init.log``.
    Raises InitScriptError on non-zero exit.
    """
    logs_dir = LOGS_DIR.expanduser()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{session_name}-init.log"

    merged_env = {**os.environ, **env}

    with log_file.open("w") as fh:
        result = subprocess.run(
            [str(script_path), str(repo_path), str(worktree_path)],
            env=merged_env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if result.returncode != 0:
        raise InitScriptError(f"init script failed (exit {result.returncode})\nLog: {log_file}")
