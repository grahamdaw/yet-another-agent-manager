"""Worktrunk (wt) subprocess wrapper."""

import json
import os
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


def _run(
    args: list[str],
    cwd: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a wt command, raising WorktrunkError on non-zero exit."""
    _require_wt()
    kwargs: dict = {"cwd": cwd, "capture_output": True, "text": True}
    if extra_env is not None:
        kwargs["env"] = {**os.environ, **extra_env}
    result = subprocess.run(["wt", *args], **kwargs)
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
    extra_env = {
        "WORKTRUNK_WORKTREE_PATH": (
            "{{ repo_path }}/../.worktrunk-{{ repo }}.{{ branch | sanitize }}"
        )
    }
    _run(["switch", "--create", branch], cwd=repo_path, extra_env=extra_env)
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


def _worktree_from_list_entry(entry: dict) -> WorktreeInfo | None:
    """Map one ``wt list --format=json`` object to WorktreeInfo, or None to skip."""
    path_str = entry.get("path")
    if not path_str:
        return None

    # Current Worktrunk: nested ``commit`` / ``working_tree`` (see worktrunk.dev/list).
    if "commit" in entry:
        commit = entry.get("commit") or {}
        sha = commit.get("sha") or ""
        head = commit.get("short_sha") or (sha[:7] if len(sha) >= 7 else sha)
        branch = entry.get("branch") or ""
        wt = entry.get("working_tree") or {}
        dirty = any(wt.get(k) for k in ("staged", "modified", "untracked", "renamed", "deleted"))
        status = "dirty" if dirty else "clean"
        return WorktreeInfo(
            branch=branch,
            path=Path(path_str),
            status=status,
            head=head,
        )

    # Legacy flat JSON (older wt / tests): branch, path, status, head
    return WorktreeInfo(
        branch=entry.get("branch", ""),
        path=Path(path_str),
        status=entry.get("status", "unknown"),
        head=entry.get("head", ""),
    )


def list_worktrees(repo_path: str | Path) -> list[WorktreeInfo]:
    """Return all active worktrees for the repo at *repo_path*.

    Calls ``wt list --format=json`` and parses the JSON array. Skips rows
    without a ``path`` (e.g. branch-only listings). Supports the current
    Worktrunk shape (``commit``, ``working_tree``) and legacy flat objects.
    """
    result = _run(["list", "--format=json"], cwd=repo_path)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorktrunkError(f"Failed to parse wt list --format=json output: {exc}") from exc
    if not isinstance(data, list):
        raise WorktrunkError("wt list --format=json did not return a JSON array")
    out: list[WorktreeInfo] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        info = _worktree_from_list_entry(entry)
        if info is not None:
            out.append(info)
    return out


def merge(worktree_path: str | Path, target: str = "main") -> None:
    """Merge the worktree at *worktree_path* into *target*.

    Calls ``wt merge <target>`` from the worktree directory.
    """
    _run(["merge", target], cwd=worktree_path)
