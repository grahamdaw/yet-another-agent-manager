"""Worktrunk (wt) subprocess wrapper."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from yaam.utils import sanitize_name


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


def _normalise_branch(branch: str) -> str:
    """Strip refs/heads/ prefix for uniform branch comparison."""
    return branch.removeprefix("refs/heads/")


def _branch_matches(entry_branch: str, target: str) -> bool:
    """Return True if *entry_branch* (from wt/git list output) refers to *target*."""
    ne = _normalise_branch(entry_branch)
    nt = _normalise_branch(target)
    return ne == nt or ne.endswith(f"/{nt}")


def _git_find_worktree(branch: str, repo_path: str | Path) -> WorktreeInfo | None:
    """Return a ``WorktreeInfo`` for *branch* by parsing ``git worktree list --porcelain``, or ``None`` if not found."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    norm_target = _normalise_branch(branch)
    current: dict[str, str] = {}

    def _check(block: dict[str, str]) -> WorktreeInfo | None:
        path_str = block.get("path")
        wt_branch = block.get("branch", "")
        if path_str and _normalise_branch(wt_branch) == norm_target:
            head = block.get("head", "")
            return WorktreeInfo(
                branch=branch,
                path=Path(path_str),
                status="clean",
                head=head[:7] if len(head) >= 7 else head,
            )
        return None

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                found = _check(current)
                if found:
                    return found
            current = {"path": line.removeprefix("worktree ").strip()}
        elif line.startswith("HEAD "):
            current["head"] = line.removeprefix("HEAD ").strip()
        elif line.startswith("branch "):
            current["branch"] = line.removeprefix("branch ").strip()

    # Check the last block
    if current:
        return _check(current)
    return None


def _git_worktree_add(branch: str, repo_path: str | Path) -> None:
    """Create a git worktree for an existing branch using ``git worktree add``.

    Used as a last resort when wt switch fails and the worktree doesn't yet exist.
    The worktree is placed next to the repo directory, mirroring wt's own path
    convention (``../.worktrunk-<repo>.<sanitized-branch>``).
    Raises WorktrunkError on failure so the caller sees the real git error.
    """
    rp = Path(repo_path).expanduser().resolve()
    worktree_path = rp.parent / f".worktrunk-{rp.name}.{sanitize_name(branch)}"

    # Clean up a stale directory left by a previous failed attempt.
    # A properly registered git worktree has a .git file; without one the
    # directory is an unrecoverable leftover and git will refuse to reuse it.
    if worktree_path.exists() and not (worktree_path / ".git").exists():
        shutil.rmtree(worktree_path)

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), branch],
        cwd=rp,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stderr.strip() or result.stdout.strip())
        raise WorktrunkError(f"git worktree add failed:\n{output}")


def create(branch: str, repo_path: str | Path) -> WorktreeInfo:
    """Create or attach to a worktree for *branch* in *repo_path*.

    Strategy:
    1. If a worktree for the branch already exists, return it immediately.
    2. ``wt switch --create <branch>`` — creates branch + worktree.
    3. If branch already exists: ``wt switch <branch>`` — attaches to existing worktree.
    4. If that also fails: ``git worktree add`` — creates worktree for the existing branch.
    5. Locate the created worktree via ``git worktree list`` then ``wt list``.
    """
    _require_wt()

    # Strategy 1: fast path — worktree may already exist (e.g. from a previous session).
    existing = _git_find_worktree(branch, repo_path)
    if existing is not None:
        return existing

    extra_env = {
        "WORKTRUNK_WORKTREE_PATH": (
            "{{ repo_path }}/../.worktrunk-{{ repo }}.{{ branch | sanitize }}"
        )
    }
    try:
        # Strategy 2: create a new branch + worktree in one step.
        _run(["switch", "--create", branch], cwd=repo_path, extra_env=extra_env)
    except WorktrunkError as exc:
        if "already exists" not in str(exc).lower():
            raise
        # Strategy 3: branch exists in git but has no worktree yet.
        try:
            _run(["switch", branch], cwd=repo_path, extra_env=extra_env)
        except WorktrunkError:
            # Strategy 4: wt switch can't attach; use git worktree add directly.
            _git_worktree_add(branch, repo_path)

    # Strategy 5: locate the newly created worktree via git, then wt list as fallback.
    git_entry = _git_find_worktree(branch, repo_path)
    if git_entry is not None:
        return git_entry

    for entry in list_worktrees(repo_path):
        if _branch_matches(entry.branch, branch):
            return entry

    raise WorktrunkError(
        f"Worktree for branch '{branch}' not found after wt switch / git worktree add. "
        "Run 'git worktree list' to inspect the state."
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
