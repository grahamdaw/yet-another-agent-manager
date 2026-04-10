"""Unit tests for yaam.tmux module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yaam.tmux import (
    NEW_SESSION_HEIGHT,
    NEW_SESSION_WIDTH,
    TmuxScriptError,
    get_or_create_session,
    kill_session,
    run_setup_script,
    session_alive,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path("/fake/scripts/tmux.sh")
WORKTREE = Path("/fake/worktree")
SESSION = "agent-foo"


def _fake_session(name=SESSION) -> MagicMock:
    sess = MagicMock()
    sess.session_name = name
    return sess


def _fake_server(
    has_session: bool = False,
    session: MagicMock | None = None,
) -> MagicMock:
    server = MagicMock()
    server.has_session.return_value = has_session
    server.sessions = MagicMock()
    server.sessions.get.return_value = session
    return server


# ---------------------------------------------------------------------------
# get_or_create_session
# ---------------------------------------------------------------------------


def test_get_or_create_session_creates_new():
    server = _fake_server(has_session=False)
    new_session = _fake_session()
    server.new_session.return_value = new_session

    with patch("yaam.tmux._server", return_value=server):
        result = get_or_create_session(SESSION)

    server.has_session.assert_called_once_with(SESSION)
    server.new_session.assert_called_once_with(
        session_name=SESSION,
        x=NEW_SESSION_WIDTH,
        y=NEW_SESSION_HEIGHT,
    )
    assert result is new_session


def test_get_or_create_session_returns_existing():
    existing = _fake_session()
    server = _fake_server(has_session=True, session=existing)

    with patch("yaam.tmux._server", return_value=server):
        result = get_or_create_session(SESSION)

    server.new_session.assert_not_called()
    assert result is existing


def test_get_or_create_session_creates_if_sessions_get_returns_none():
    """has_session returns True but sessions.get returns None — still create."""
    server = _fake_server(has_session=True, session=None)
    new_session = _fake_session()
    server.new_session.return_value = new_session

    with patch("yaam.tmux._server", return_value=server):
        result = get_or_create_session(SESSION)

    server.new_session.assert_called_once_with(
        session_name=SESSION,
        x=NEW_SESSION_WIDTH,
        y=NEW_SESSION_HEIGHT,
    )
    assert result is new_session


def test_get_or_create_session_passes_start_directory():
    server = _fake_server(has_session=False)
    server.new_session.return_value = _fake_session()

    with patch("yaam.tmux._server", return_value=server):
        get_or_create_session(SESSION, start_directory=WORKTREE)

    server.new_session.assert_called_once_with(
        session_name=SESSION,
        x=NEW_SESSION_WIDTH,
        y=NEW_SESSION_HEIGHT,
        start_directory=str(WORKTREE),
    )


# ---------------------------------------------------------------------------
# run_setup_script
# ---------------------------------------------------------------------------


def _completed(returncode=0, stderr=""):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stderr = stderr
    return proc


def test_run_setup_script_success():
    with patch("subprocess.run", return_value=_completed()) as mock_run:
        run_setup_script(SCRIPT, WORKTREE, SESSION)

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == [str(SCRIPT), SESSION, str(WORKTREE)]


def test_run_setup_script_raises_on_failure():
    with (
        patch("subprocess.run", return_value=_completed(returncode=1, stderr="boom")),
        pytest.raises(TmuxScriptError, match="tmux setup script failed"),
    ):
        run_setup_script(SCRIPT, WORKTREE, SESSION)


# ---------------------------------------------------------------------------
# session_alive
# ---------------------------------------------------------------------------


def test_session_alive_true():
    server = _fake_server(has_session=True)

    with patch("yaam.tmux._server", return_value=server):
        assert session_alive(SESSION) is True

    server.has_session.assert_called_once_with(SESSION)


def test_session_alive_false():
    server = _fake_server(has_session=False)

    with patch("yaam.tmux._server", return_value=server):
        assert session_alive(SESSION) is False


# ---------------------------------------------------------------------------
# kill_session
# ---------------------------------------------------------------------------


def test_kill_session_kills_live_session():
    session = _fake_session()
    server = _fake_server(has_session=True, session=session)

    with patch("yaam.tmux._server", return_value=server):
        kill_session(SESSION)

    session.kill.assert_called_once()


def test_kill_session_noop_when_absent():
    server = _fake_server(has_session=False)

    with patch("yaam.tmux._server", return_value=server):
        kill_session(SESSION)  # must not raise

    server.sessions.get.assert_not_called()


def test_kill_session_noop_when_get_returns_none():
    """has_session is True but sessions.get returns None — swallow quietly."""
    server = _fake_server(has_session=True, session=None)

    with patch("yaam.tmux._server", return_value=server):
        kill_session(SESSION)  # must not raise
