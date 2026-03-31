"""Unit tests for agent.worktrunk module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from yaam.worktrunk import (
    WorktreeInfo,
    WorktrunkError,
    WorktrunkNotFoundError,
    _find_main_repo,
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


def _wt_list_entry(
    branch: str,
    path: str,
    *,
    head_short: str = "abc123",
    dirty: bool = False,
) -> dict:
    """Build one Worktrunk ``wt list --format=json`` row (modern schema)."""
    wt: dict = {}
    if dirty:
        wt["modified"] = True
    return {
        "branch": branch,
        "path": path,
        "kind": "worktree",
        "commit": {
            "sha": "a" * 40,
            "short_sha": head_short,
            "message": "test",
            "timestamp": 0,
        },
        "working_tree": wt,
    }


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
    with patch("yaam.worktrunk.wt_available", return_value=False):
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
    with patch("yaam.worktrunk.wt_available", return_value=True):
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
        _wt_list_entry("main", "/repo", head_short="abc123"),
        _wt_list_entry("feature/x", "/repo-feature-x", head_short="def456", dirty=True),
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
        pytest.raises(WorktrunkError, match=r"parse.*format=json"),
    ):
        list_worktrees(FAKE_REPO)


def test_list_worktrees_raises_on_non_array_json(has_wt):
    with (
        patch("subprocess.run", return_value=_completed(stdout='{"x": 1}')),
        pytest.raises(WorktrunkError, match="array"),
    ):
        list_worktrees(FAKE_REPO)


def test_list_worktrees_passes_cwd(has_wt):
    payload = _wt_list_json(_wt_list_entry("main", str(FAKE_REPO), head_short="aaa"))
    with patch("subprocess.run", return_value=_completed(stdout=payload)) as mock_run:
        list_worktrees(FAKE_REPO)
    mock_run.assert_called_once_with(
        ["wt", "list", "--format=json"],
        cwd=FAKE_REPO,
        capture_output=True,
        text=True,
    )


def test_list_worktrees_legacy_flat_json(has_wt):
    """Older flat ``branch``/``path``/``status``/``head`` rows still parse."""
    payload = _wt_list_json(
        {"branch": "main", "path": "/repo", "status": "clean", "head": "abc123"},
    )
    with patch("subprocess.run", return_value=_completed(stdout=payload)):
        result = list_worktrees(FAKE_REPO)
    assert len(result) == 1
    assert result[0].branch == "main"
    assert result[0].status == "clean"
    assert result[0].head == "abc123"


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_returns_worktree_info(has_wt):
    list_payload = _wt_list_json(
        _wt_list_entry("my-branch", "/repo/my-branch", head_short="cafebabe"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(),  # wt switch --create
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # wt list --format=json
    ]
    with patch("subprocess.run", side_effect=responses):
        info = create("my-branch", FAKE_REPO)

    assert isinstance(info, WorktreeInfo)
    assert info.branch == "my-branch"
    assert info.head == "cafebabe"


def test_create_raises_if_branch_not_in_list(has_wt):
    list_payload = _wt_list_json(
        _wt_list_entry("other-branch", "/repo/other", head_short="000"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(),  # wt switch --create succeeds
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # branch not found in wt list (line 215)
        _completed(stdout=list_payload),  # main-repo check wt list (line 221)
    ]
    with (
        patch("subprocess.run", side_effect=responses),
        pytest.raises(WorktrunkError, match="not found"),
    ):
        create("my-branch", FAKE_REPO)


def test_create_matches_branch_with_prefix(has_wt):
    list_payload = _wt_list_json(
        _wt_list_entry("refs/heads/my-branch", "/repo/my-branch", head_short="111"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(),  # wt switch --create
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # wt list --format=json
    ]
    with patch("subprocess.run", side_effect=responses):
        info = create("my-branch", FAKE_REPO)
    assert info.branch == "refs/heads/my-branch"


def test_create_injects_worktrunk_worktree_path_env(has_wt):
    list_payload = _wt_list_json(
        _wt_list_entry("my-branch", "/repo/my-branch", head_short="cafebabe"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(),  # wt switch --create
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # wt list --format=json
    ]
    with patch("subprocess.run", side_effect=responses) as mock_run:
        create("my-branch", FAKE_REPO)

    switch_kwargs = mock_run.call_args_list[1].kwargs
    env = switch_kwargs.get("env")
    assert env is not None
    assert env["WORKTRUNK_WORKTREE_PATH"] == (
        "{{ repo_path }}/../.worktrunk-{{ repo }}.{{ branch | sanitize }}"
    )


def test_create_list_call_has_no_extra_env(has_wt):
    list_payload = _wt_list_json(
        _wt_list_entry("my-branch", "/repo/my-branch", head_short="cafebabe"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(),  # wt switch --create
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # wt list --format=json
    ]
    with patch("subprocess.run", side_effect=responses) as mock_run:
        create("my-branch", FAKE_REPO)

    list_kwargs = mock_run.call_args_list[3].kwargs
    assert "env" not in list_kwargs


# ---------------------------------------------------------------------------
# create — existing-branch fallback
# ---------------------------------------------------------------------------


def test_create_falls_back_to_switch_when_branch_already_exists(has_wt):
    """wt switch --create fails with 'already exists' → retries with wt switch."""
    list_payload = _wt_list_json(
        _wt_list_entry("my-branch", "/repo/my-branch", head_short="cafebabe"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(returncode=1, stderr="Branch my-branch already exists"),  # --create fails
        _completed(),  # wt switch (no --create) succeeds
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # wt list
    ]
    with patch("subprocess.run", side_effect=responses) as mock_run:
        info = create("my-branch", FAKE_REPO)

    assert info.branch == "my-branch"
    assert info.head == "cafebabe"
    # [1]: --create; [2]: plain switch; [4]: wt list
    assert mock_run.call_args_list[1].args[0] == ["wt", "switch", "--create", "my-branch"]
    assert mock_run.call_args_list[2].args[0] == ["wt", "switch", "my-branch"]


def test_create_fallback_raises_if_plain_switch_also_fails(has_wt):
    """When both wt switch variants fail, git worktree add is tried and its error propagates."""
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(returncode=1, stderr="Branch my-branch already exists"),  # --create fails
        _completed(returncode=1, stderr="fatal: something else"),  # plain switch fails
        _completed(returncode=1, stderr="fatal: something else"),  # git worktree add fails
    ]
    with (
        patch("subprocess.run", side_effect=responses),
        pytest.raises(WorktrunkError, match="something else"),
    ):
        create("my-branch", FAKE_REPO)


def test_create_no_fallback_for_unrelated_error(has_wt):
    """A --create failure not containing 'already exists' is raised immediately."""
    with (
        patch(
            "subprocess.run",
            return_value=_completed(returncode=1, stderr="permission denied"),
        ),
        pytest.raises(WorktrunkError, match="permission denied"),
    ):
        create("my-branch", FAKE_REPO)


def test_create_fallback_passes_env_to_plain_switch(has_wt):
    """The WORKTRUNK_WORKTREE_PATH env is forwarded to the fallback wt switch call."""
    list_payload = _wt_list_json(
        _wt_list_entry("my-branch", "/repo/my-branch", head_short="cafebabe"),
    )
    responses = [
        _completed(),  # fast-path git worktree list --porcelain → None
        _completed(returncode=1, stderr="Branch my-branch already exists"),
        _completed(),  # wt switch (no --create) succeeds
        _completed(),  # post-switch git worktree list --porcelain → None
        _completed(stdout=list_payload),  # wt list
    ]
    with patch("subprocess.run", side_effect=responses) as mock_run:
        create("my-branch", FAKE_REPO)

    fallback_kwargs = mock_run.call_args_list[2].kwargs
    env = fallback_kwargs.get("env")
    assert env is not None
    assert env["WORKTRUNK_WORKTREE_PATH"] == (
        "{{ repo_path }}/../.worktrunk-{{ repo }}.{{ branch | sanitize }}"
    )


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


def test_remove_prunes_after_wt_remove(has_wt):
    """git worktree prune is called from the main repo after wt remove."""
    fake_main = Path("/fake")
    with (
        patch("yaam.worktrunk._find_main_repo", return_value=fake_main),
        patch("subprocess.run", return_value=_completed()) as mock_run,
    ):
        remove(FAKE_WORKTREE)

    assert mock_run.call_args_list[0] == call(
        ["wt", "remove"],
        cwd=FAKE_WORKTREE,
        capture_output=True,
        text=True,
    )
    assert mock_run.call_args_list[1] == call(
        ["git", "worktree", "prune"],
        cwd=fake_main,
        capture_output=True,
        text=True,
    )


def test_remove_skips_prune_when_main_repo_unknown(has_wt):
    """When _find_main_repo returns None, git worktree prune is not called."""
    with (
        patch("yaam.worktrunk._find_main_repo", return_value=None),
        patch("subprocess.run", return_value=_completed()) as mock_run,
    ):
        remove(FAKE_WORKTREE)

    mock_run.assert_called_once_with(
        ["wt", "remove"],
        cwd=FAKE_WORKTREE,
        capture_output=True,
        text=True,
    )


def test_find_main_repo_returns_none_for_nonexistent_path():
    """_find_main_repo returns None when the worktree directory doesn't exist."""
    assert _find_main_repo(Path("/nonexistent/path/that/cannot/exist")) is None


def test_find_main_repo_resolves_absolute_git_common_dir():
    """_find_main_repo returns the parent of an absolute git-common-dir."""
    fake_worktree = Path("/fake/worktree")
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "subprocess.run",
            return_value=_completed(stdout="/main/repo/.git\n"),
        ),
    ):
        result = _find_main_repo(fake_worktree)

    assert result == Path("/main/repo")


def test_find_main_repo_resolves_relative_git_common_dir():
    """_find_main_repo resolves a relative git-common-dir against the worktree path."""
    fake_worktree = Path("/fake/worktree").resolve()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "subprocess.run",
            return_value=_completed(stdout=".git\n"),
        ),
    ):
        result = _find_main_repo(fake_worktree)

    # relative ".git" → fake_worktree / ".git" → parent is fake_worktree
    assert result == fake_worktree


def test_find_main_repo_returns_none_on_git_failure():
    """_find_main_repo returns None when git rev-parse fails."""
    fake_worktree = Path("/fake/worktree")
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "subprocess.run",
            return_value=_completed(returncode=128, stderr="not a git repo"),
        ),
    ):
        result = _find_main_repo(fake_worktree)

    assert result is None


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
