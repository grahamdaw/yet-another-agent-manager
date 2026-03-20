"""Unit tests for agent.init module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.init import InitScriptError, run

SCRIPT = Path("/fake/scripts/init.sh")
REPO = Path("/fake/repo")
WORKTREE = Path("/fake/worktree")
SESSION = "agent-foo"


def _completed(returncode: int = 0) -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    return proc


def test_run_calls_script_with_correct_args(tmp_path):
    with (
        patch("subprocess.run", return_value=_completed()) as mock_run,
        patch("agent.init.LOGS_DIR", tmp_path),
    ):
        run(SCRIPT, REPO, WORKTREE, {}, SESSION)

    args = mock_run.call_args[0][0]
    assert args == [str(SCRIPT), str(REPO), str(WORKTREE)]


def test_run_merges_env(tmp_path):
    with (
        patch("subprocess.run", return_value=_completed()) as mock_run,
        patch("agent.init.LOGS_DIR", tmp_path),
        patch.dict("os.environ", {"EXISTING": "yes"}),
    ):
        run(SCRIPT, REPO, WORKTREE, {"MY_VAR": "abc"}, SESSION)

    env = mock_run.call_args[1]["env"]
    assert env["MY_VAR"] == "abc"
    assert "EXISTING" in env


def test_run_env_overrides_process_env(tmp_path):
    with (
        patch("subprocess.run", return_value=_completed()) as mock_run,
        patch("agent.init.LOGS_DIR", tmp_path),
        patch.dict("os.environ", {"MY_VAR": "original"}),
    ):
        run(SCRIPT, REPO, WORKTREE, {"MY_VAR": "override"}, SESSION)

    assert mock_run.call_args[1]["env"]["MY_VAR"] == "override"


def test_run_writes_log(tmp_path):
    with (
        patch("subprocess.run", return_value=_completed()),
        patch("agent.init.LOGS_DIR", tmp_path),
    ):
        run(SCRIPT, REPO, WORKTREE, {}, "my-agent")

    assert (tmp_path / "my-agent-init.log").exists()


def test_run_raises_on_failure(tmp_path):
    with (
        patch("subprocess.run", return_value=_completed(returncode=1)),
        patch("agent.init.LOGS_DIR", tmp_path),
        pytest.raises(InitScriptError, match="init script failed"),
    ):
        run(SCRIPT, REPO, WORKTREE, {}, SESSION)


def test_run_error_includes_log_path(tmp_path):
    with (
        patch("subprocess.run", return_value=_completed(returncode=1)),
        patch("agent.init.LOGS_DIR", tmp_path),
        pytest.raises(InitScriptError, match=str(tmp_path)),
    ):
        run(SCRIPT, REPO, WORKTREE, {}, SESSION)


def test_run_combines_stdout_stderr(tmp_path):
    """stderr=STDOUT means both streams go to the log file."""
    with (
        patch("subprocess.run", return_value=_completed()) as mock_run,
        patch("agent.init.LOGS_DIR", tmp_path),
    ):
        run(SCRIPT, REPO, WORKTREE, {}, SESSION)

    kwargs = mock_run.call_args[1]
    assert kwargs["stderr"] == subprocess.STDOUT
