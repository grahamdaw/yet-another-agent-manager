"""Unit tests for agent.worktrunk module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.worktrunk import (
    WorktreeInfo,
    WorktrunkError,
    WorktrunkNotFoundError,
    create,
    list_worktrees,
    merge,
    remove,
    wt_available,
)

FAKE_REPO = Path("/fake/repo")
FAKE_WORKTREE = Path("/fake/worktree")


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    """Build a fake CompletedProcess."""
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


def _wt_list_json(*entries: dict) -> str:
    return json.dumps(list(entries))


# ---------------------------------------------------------------------------
# wt_available
# ---------------------------------------------------------------------------


def test_wt_available_true():
    with patch("shutil.which", return_value="/usr/local/bin/wt"):
        assert wt_available() is True


def test_wt_available_false():
    with patch("shutil.which", return_value=None):
        assert wt_available() is False


# ---------------------------------------------------------------------------
# WorktrunkNotFoundError when wt is missing
# ---------------------------------------------------------------------------


@pytest.fixture()
def no_wt():
    """Patch shutil.which to simulate wt not being installed."""
    with patch("agent.worktrunk.wt_available", return_value=False):
        yield


def test_create_raises_when_wt_missing(no_wt):
    with pytest.raises(WorktrunkNotFoundError):
        create("my-branch", FAKE_REPO)


def test_remove_raises_when_wt_missing(no_wt):
    with pytest.raises(WorktrunkNotFoundError):
        remove(FAKE_WORKTREE)


def test_list_worktrees_raises_when_wt_missing(no_wt):
    with pytest.raises(WorktrunkNotFoundError):
        list_worktrees(FAKE_REPO)


def test_merge_raises_when_wt_missing(no_wt):
    with pytest.raises(WorktrunkNotFoundError):
        merge(FAKE_WORKTREE)


# ---------------------------------------------------------------------------
# WorktrunkError on non-zero exit
# ---------------------------------------------------------------------------


@pytest.fixture()
def has_wt():
    """Patch shutil.which to simulate wt being installed."""
    with patch("agent.worktrunk.wt_available", return_value=True):
        yield


def test_run_raises_worktrunk_error_on_failure(has_wt):
    with (
        patch("subprocess.run", return_value=_completed(returncode=1, stderr="bad branch")),
        pytest.raises(WorktrunkError, match="failed"),
    ):
        create("bad-branch", FAKE_REPO)


# ---------------------------------------------------------------------------
# list_worktrees
# ---------------------------------------------------------------------------


def test_list_worktrees_returns_entries(has_wt):
    payload = _wt_list_json(
        {"branch": "main", "path": "/repo", "status": "clean", "head": "abc123"},
        {"branch": "feature/x", "path": "/repo-feature-x", "status": "dirty", "head": "def456"},
    )
    with patch("subprocess.run", return_value=_completed(stdout=payload)):
        result = list_worktrees(FAKE_REPO)

    assert len(result) == 2
    assert result[0].branch == "main"
    assert result[0].path == Path("/repo")
    assert result[0].status == "clean"
    assert result[0].head == "abc123"
    assert result[1].branch == "feature/x"


def test_list_worktrees_empty(has_wt):
    with patch("subprocess.run", return_value=_completed(stdout="[]")):
        assert list_worktrees(FAKE_REPO) == []


def test_list_worktrees_raises_on_bad_json(has_wt):
    with (
        patch("subprocess.run", return_value=_completed(stdout="not-json")),
        pytest.raises(WorktrunkError, match="parse"),
    ):
        list_worktrees(FAKE_REPO)


def test_list_worktrees_passes_cwd(has_wt):
    payload = _wt_list_json(
        {"branch": "main", "path": str(FAKE_REPO), "status": "clean", "head": "aaa"}
    )
    with patch("subprocess.run", return_value=_completed(stdout=payload)) as mock_run:
        list_worktrees(FAKE_REPO)
    mock_run.assert_called_once_with(
        ["wt", "list", "--json"],
        cwd=FAKE_REPO,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_returns_worktree_info(has_wt):
    list_payload = _wt_list_json(
        {
            "branch": "my-branch",
            "path": "/repo/my-branch",
            "status": "clean",
            "head": "cafebabe",
        }
    )
    responses = [
        _completed(),  # wt switch --create
        _completed(stdout=list_payload),  # wt list --json
    ]
    with patch("subprocess.run", side_effect=responses):
        info = create("my-branch", FAKE_REPO)

    assert isinstance(info, WorktreeInfo)
    assert info.branch == "my-branch"
    assert info.head == "cafebabe"


def test_create_raises_if_branch_not_in_list(has_wt):
    list_payload = _wt_list_json(
        {"branch": "other-branch", "path": "/repo/other", "status": "clean", "head": "000"}
    )
    responses = [
        _completed(),  # wt switch --create succeeds
        _completed(stdout=list_payload),  # branch not found in list
    ]
    with (
        patch("subprocess.run", side_effect=responses),
        pytest.raises(WorktrunkError, match="not found"),
    ):
        create("my-branch", FAKE_REPO)


def test_create_matches_branch_with_prefix(has_wt):
    list_payload = _wt_list_json(
        {
            "branch": "refs/heads/my-branch",
            "path": "/repo/my-branch",
            "status": "clean",
            "head": "111",
        }
    )
    responses = [_completed(), _completed(stdout=list_payload)]
    with patch("subprocess.run", side_effect=responses):
        info = create("my-branch", FAKE_REPO)
    assert info.branch == "refs/heads/my-branch"


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


def test_remove_calls_wt_remove(has_wt):
    with patch("subprocess.run", return_value=_completed()) as mock_run:
        remove(FAKE_WORKTREE)
    mock_run.assert_called_once_with(
        ["wt", "remove"],
        cwd=FAKE_WORKTREE,
        capture_output=True,
        text=True,
    )


def test_remove_raises_on_failure(has_wt):
    with (
        patch("subprocess.run", return_value=_completed(returncode=1, stderr="error")),
        pytest.raises(WorktrunkError),
    ):
        remove(FAKE_WORKTREE)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def test_merge_calls_wt_merge_main(has_wt):
    with patch("subprocess.run", return_value=_completed()) as mock_run:
        merge(FAKE_WORKTREE)
    mock_run.assert_called_once_with(
        ["wt", "merge", "main"],
        cwd=FAKE_WORKTREE,
        capture_output=True,
        text=True,
    )


def test_merge_uses_custom_target(has_wt):
    with patch("subprocess.run", return_value=_completed()) as mock_run:
        merge(FAKE_WORKTREE, target="develop")
    mock_run.assert_called_once_with(
        ["wt", "merge", "develop"],
        cwd=FAKE_WORKTREE,
        capture_output=True,
        text=True,
    )


def test_merge_raises_on_failure(has_wt):
    with (
        patch("subprocess.run", return_value=_completed(returncode=1, stderr="conflict")),
        pytest.raises(WorktrunkError),
    ):
        merge(FAKE_WORKTREE)
