"""Post-init script runner."""

import os
import subprocess
from pathlib import Path


class InitScriptError(RuntimeError):
    """Raised when the post-init script exits with a non-zero code."""


def run(
    script_path: str | Path,
    repo_path: str | Path,
    worktree_path: str | Path,
    env: dict[str, str],
    session_name: str,
) -> None:
    """Run the post-init script, streaming output to the terminal.

    Calls ``script_path repo_path worktree_path`` as a subprocess.
    Merges *env* with the current process environment.  Output is streamed
    directly to stdout/stderr.
    Raises InitScriptError on non-zero exit.
    """
    merged_env = {**os.environ, **env}

    result = subprocess.run(
        [str(script_path), str(repo_path), str(worktree_path)],
        env=merged_env,
        stdout=None,
        stderr=None,
        text=True,
    )

    if result.returncode != 0:
        raise InitScriptError(f"init script failed (exit {result.returncode})")
