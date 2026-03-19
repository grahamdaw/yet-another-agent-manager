"""Worktrunk (wt) subprocess wrapper."""

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel


class WorktrunkNotFoundError(RuntimeError):
    """Raised when the wt binary is not found on PATH."""


class WorktrunkError(RuntimeError):
    """Raised when a wt command fails."""


class WorktreeInfo(BaseModel):
    """Represents a single git worktree managed by Worktrunk."""

    branch: str
    path: Path
    status: str
    head: str


def wt_available() -> bool:
    """Return True if the wt binary is available on PATH."""
    return shutil.which("wt") is not None


def _require_wt() -> None:
    """Raise WorktrunkNotFoundError if wt is not on PATH."""
    if not wt_available():
        raise WorktrunkNotFoundError(
            "wt (Worktrunk) is not installed or not on PATH. "
            "See https://github.com/steveyegge/worktrunk for installation instructions."
        )


def _run(args: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a wt command, raising WorktrunkError on non-zero exit."""
    _require_wt()
    result = subprocess.run(
        ["wt", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise WorktrunkError(
            f"wt {' '.join(args)} failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return result


def create(branch: str, repo_path: str | Path) -> WorktreeInfo:
    """Create a new worktree for *branch* in *repo_path*.

    Calls ``wt switch --create <branch>`` from repo_path and returns a
    populated WorktreeInfo for the new worktree.
    """
    _run(["switch", "--create", branch], cwd=repo_path)
    worktrees = list_worktrees(repo_path)
    for entry in worktrees:
        if entry.branch == branch or entry.branch.endswith(f"/{branch}"):
            return entry
    raise WorktrunkError(
        f"wt switch --create succeeded but worktree for branch '{branch}' "
        "not found in wt list output."
    )


def remove(worktree_path: str | Path) -> None:
    """Remove the worktree at *worktree_path*.

    Calls ``wt remove`` from the worktree directory.
    """
    _run(["remove"], cwd=worktree_path)


def list_worktrees(repo_path: str | Path) -> list[WorktreeInfo]:
    """Return all active worktrees for the repo at *repo_path*.

    Calls ``wt list --json`` and parses the JSON output. Each entry is
    expected to have ``branch``, ``path``, ``status``, and ``head`` keys.
    """
    result = _run(["list", "--json"], cwd=repo_path)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorktrunkError(f"Failed to parse wt list --json output: {exc}") from exc
    return [
        WorktreeInfo(
            branch=entry.get("branch", ""),
            path=Path(entry.get("path", "")),
            status=entry.get("status", "unknown"),
            head=entry.get("head", ""),
        )
        for entry in data
    ]


def merge(worktree_path: str | Path, target: str = "main") -> None:
    """Merge the worktree at *worktree_path* into *target*.

    Calls ``wt merge <target>`` from the worktree directory.
    """
    _run(["merge", target], cwd=worktree_path)
