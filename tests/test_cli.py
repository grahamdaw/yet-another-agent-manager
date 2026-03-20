"""Unit tests for CLI commands (agent new, list, kill)."""

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from agent.cli import app
from agent.profile import AgentProfile
from agent.session import AgentSession
from agent.tmux import PaneRef
from agent.worktrunk import WorktreeInfo

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_PANE_REF = PaneRef(session_id="$1", window_id="@1", pane_id="%1")
_NOW = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
_WORKTREE = Path("/repo/agent/foo")


def _profile(**kwargs) -> AgentProfile:
    defaults = dict(
        name="backend",
        description="Backend",
        repo_path=Path("/repo"),
        default_branch_prefix="agent/",
        tmux_setup_script=Path("/scripts/tmux.sh"),
        init_script=Path("/scripts/init.sh"),
        init_env={},
    )
    defaults.update(kwargs)
    return AgentProfile(**defaults)


def _session(**kwargs) -> AgentSession:
    defaults = dict(
        name="foo",
        branch="agent/foo",
        profile_name="backend",
        worktree_path=_WORKTREE,
        tmux_session="agent",
        tmux_pane_ref=_PANE_REF,
        created_at=_NOW,
        status="running",
    )
    defaults.update(kwargs)
    return AgentSession(**defaults)


def _cfg() -> MagicMock:
    return MagicMock(tmux_session_name="agent")


def _worktree_info(branch: str = "agent/foo") -> WorktreeInfo:
    return WorktreeInfo(branch=branch, path=_WORKTREE, status="clean", head="abc123")


# ---------------------------------------------------------------------------
# agent new
# ---------------------------------------------------------------------------


def test_new_happy_path(tmp_path):
    with (
        patch("agent.cli.profile_mod.load", return_value=_profile()),
        patch("agent.cli.profile_mod.validate", return_value=[]),
        patch("agent.cli.worktrunk.create", return_value=_worktree_info()),
        patch("agent.cli.tmux_mod.get_or_create_session"),
        patch("agent.cli.tmux_mod.run_setup_script"),
        patch("agent.cli.tmux_mod.create_pane", return_value=_PANE_REF),
        patch("agent.cli.init_mod.run"),
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.config_mod.load_config", return_value=_cfg()),
    ):
        mock_store_cls.return_value.add = MagicMock()
        result = runner.invoke(app, ["new", "foo", "--profile", "backend"])

    assert result.exit_code == 0
    assert "foo" in result.output
    assert "spawned" in result.output


def test_new_profile_not_found():
    with patch("agent.cli.profile_mod.load", side_effect=FileNotFoundError("not found")):
        result = runner.invoke(app, ["new", "foo", "--profile", "missing"])

    assert result.exit_code == 1
    assert "Error" in result.output


def test_new_profile_validation_issues():
    with (
        patch("agent.cli.profile_mod.load", return_value=_profile()),
        patch("agent.cli.profile_mod.validate", return_value=["repo missing"]),
    ):
        result = runner.invoke(app, ["new", "foo", "--profile", "backend"])

    assert result.exit_code == 1
    assert "repo missing" in result.output


def test_new_cleans_up_on_init_failure():
    from agent.init import InitScriptError

    with (
        patch("agent.cli.profile_mod.load", return_value=_profile()),
        patch("agent.cli.profile_mod.validate", return_value=[]),
        patch("agent.cli.worktrunk.create", return_value=_worktree_info()),
        patch("agent.cli.tmux_mod.get_or_create_session"),
        patch("agent.cli.tmux_mod.run_setup_script"),
        patch("agent.cli.tmux_mod.create_pane", return_value=_PANE_REF),
        patch("agent.cli.init_mod.run", side_effect=InitScriptError("boom")),
        patch("agent.cli.tmux_mod.kill_pane") as mock_kill,
        patch("agent.cli.worktrunk.remove") as mock_remove,
        patch("agent.cli.config_mod.load_config", return_value=_cfg()),
    ):
        result = runner.invoke(app, ["new", "foo", "--profile", "backend"])

    assert result.exit_code == 1
    mock_kill.assert_called_once_with(_PANE_REF)
    mock_remove.assert_called_once_with(_WORKTREE)


def test_new_cleans_up_worktree_if_no_pane_yet():
    """Failure before create_pane should still remove the worktree."""
    with (
        patch("agent.cli.profile_mod.load", return_value=_profile()),
        patch("agent.cli.profile_mod.validate", return_value=[]),
        patch("agent.cli.worktrunk.create", return_value=_worktree_info()),
        patch("agent.cli.tmux_mod.get_or_create_session"),
        patch("agent.cli.tmux_mod.run_setup_script", side_effect=RuntimeError("tmux down")),
        patch("agent.cli.tmux_mod.kill_pane") as mock_kill,
        patch("agent.cli.worktrunk.remove") as mock_remove,
        patch("agent.cli.config_mod.load_config", return_value=_cfg()),
    ):
        result = runner.invoke(app, ["new", "foo", "--profile", "backend"])

    assert result.exit_code == 1
    mock_kill.assert_not_called()
    mock_remove.assert_called_once()


def test_new_custom_branch():
    with (
        patch("agent.cli.profile_mod.load", return_value=_profile()),
        patch("agent.cli.profile_mod.validate", return_value=[]),
        patch(
            "agent.cli.worktrunk.create", return_value=_worktree_info("my-custom-branch")
        ) as mock_create,
        patch("agent.cli.tmux_mod.get_or_create_session"),
        patch("agent.cli.tmux_mod.run_setup_script"),
        patch("agent.cli.tmux_mod.create_pane", return_value=_PANE_REF),
        patch("agent.cli.init_mod.run"),
        patch("agent.cli.SessionStore"),
        patch("agent.cli.config_mod.load_config", return_value=_cfg()),
    ):
        runner.invoke(app, ["new", "foo", "--profile", "backend", "--branch", "my-custom-branch"])

    mock_create.assert_called_once_with("my-custom-branch", Path("/repo"))


# ---------------------------------------------------------------------------
# agent list
# ---------------------------------------------------------------------------


def test_list_shows_sessions():
    sessions = [_session(name="foo"), _session(name="bar")]
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=True),
    ):
        mock_store_cls.return_value.list.return_value = sessions
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "foo" in result.output
    assert "bar" in result.output


def test_list_empty():
    with patch("agent.cli.SessionStore") as mock_store_cls:
        mock_store_cls.return_value.list.return_value = []
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No active sessions" in result.output


def test_list_json_output():
    sessions = [_session()]
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=True),
    ):
        mock_store_cls.return_value.list.return_value = sessions
        result = runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["name"] == "foo"


def test_list_handles_tmux_error_gracefully():
    """If pane_alive raises, the row is still shown with stored status."""
    sessions = [_session(status="running")]
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", side_effect=RuntimeError("no tmux")),
    ):
        mock_store_cls.return_value.list.return_value = sessions
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "running" in result.output


# ---------------------------------------------------------------------------
# agent attach
# ---------------------------------------------------------------------------


def test_attach_happy_path():
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=True),
        patch("subprocess.run") as mock_run,
    ):
        mock_store_cls.return_value.get.return_value = _session()
        result = runner.invoke(app, ["attach", "foo"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_attach_unknown_session():
    with patch("agent.cli.SessionStore") as mock_store_cls:
        mock_store_cls.return_value.get.return_value = None
        result = runner.invoke(app, ["attach", "ghost"])

    assert result.exit_code == 1
    assert "No session" in result.output


def test_attach_dead_pane():
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=False),
    ):
        mock_store_cls.return_value.get.return_value = _session()
        result = runner.invoke(app, ["attach", "foo"])

    assert result.exit_code == 1
    assert "dead" in result.output


# ---------------------------------------------------------------------------
# agent sync
# ---------------------------------------------------------------------------


def test_sync_all_healthy():
    sessions = [_session()]
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_store_cls.return_value.list.return_value = sessions
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "healthy" in result.output


def test_sync_detects_dead_pane():
    sessions = [_session()]
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=False),
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_store_cls.return_value.list.return_value = sessions
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "orphaned" in result.output.lower()


def test_sync_fix_removes_orphans():
    sessions = [_session()]
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.pane_alive", return_value=False),
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_store_cls.return_value.list.return_value = sessions
        result = runner.invoke(app, ["sync", "--fix"])

    assert result.exit_code == 0
    mock_store_cls.return_value.remove.assert_called_once_with("foo")


def test_sync_empty_store():
    with patch("agent.cli.SessionStore") as mock_store_cls:
        mock_store_cls.return_value.list.return_value = []
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "No sessions" in result.output


# ---------------------------------------------------------------------------
# agent kill
# ---------------------------------------------------------------------------


def test_kill_happy_path():
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.kill_pane"),
        patch("agent.cli.worktrunk.wt_available", return_value=True),
        patch("agent.cli.worktrunk.remove"),
    ):
        mock_store_cls.return_value.get.return_value = _session()
        result = runner.invoke(app, ["kill", "foo"])

    assert result.exit_code == 0
    assert "killed" in result.output


def test_kill_unknown_session():
    with patch("agent.cli.SessionStore") as mock_store_cls:
        mock_store_cls.return_value.get.return_value = None
        result = runner.invoke(app, ["kill", "ghost"])

    assert result.exit_code == 1
    assert "No session" in result.output


def test_kill_skips_wt_if_unavailable():
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.kill_pane"),
        patch("agent.cli.worktrunk.wt_available", return_value=False),
        patch("agent.cli.worktrunk.remove") as mock_remove,
    ):
        mock_store_cls.return_value.get.return_value = _session()
        runner.invoke(app, ["kill", "foo"])

    mock_remove.assert_not_called()


def test_kill_removes_from_store():
    with (
        patch("agent.cli.SessionStore") as mock_store_cls,
        patch("agent.cli.tmux_mod.kill_pane"),
        patch("agent.cli.worktrunk.wt_available", return_value=False),
    ):
        mock_store_cls.return_value.get.return_value = _session()
        runner.invoke(app, ["kill", "foo"])

    mock_store_cls.return_value.remove.assert_called_once_with("foo")
