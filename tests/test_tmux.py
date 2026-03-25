"""Unit tests for agent.tmux module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yaam.tmux import (
    NEW_SESSION_HEIGHT,
    NEW_SESSION_WIDTH,
    PaneRef,
    TmuxScriptError,
    create_pane,
    get_or_create_session,
    kill_pane,
    pane_alive,
    run_setup_script,
    send_keys,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path("/fake/scripts/tmux.sh")
WORKTREE = Path("/fake/worktree")
SESSION = "agent-foo"


def _pane_ref(session_id="$1", window_id="@1", pane_id="%1") -> PaneRef:
    return PaneRef(session_id=session_id, window_id=window_id, pane_id=pane_id)


def _fake_pane(pane_id="%1", window_id="@1", session_id="$1") -> MagicMock:
    pane = MagicMock()
    pane.pane_id = pane_id
    pane.window_id = window_id
    pane.session_id = session_id
    return pane


def _fake_window(name="main", pane: MagicMock | None = None) -> MagicMock:
    win = MagicMock()
    win.window_name = name
    win.active_pane = pane or _fake_pane()
    return win


def _fake_session(name=SESSION) -> MagicMock:
    sess = MagicMock()
    sess.session_name = name
    return sess


def _fake_server(
    has_session: bool = False,
    session: MagicMock | None = None,
    pane: MagicMock | None = None,
) -> MagicMock:
    server = MagicMock()
    server.has_session.return_value = has_session
    server.sessions = MagicMock()
    server.sessions.get.return_value = session
    server.panes.get.return_value = pane
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
# create_pane
# ---------------------------------------------------------------------------


def test_create_pane_creates_new_window():
    pane = _fake_pane()
    win = _fake_window(pane=pane)
    win.active_pane = pane
    session = _fake_session()
    session.windows = MagicMock()
    session.windows.get.return_value = None
    session.new_window.return_value = win
    server = _fake_server(session=session)

    with patch("yaam.tmux._server", return_value=server):
        ref = create_pane(SESSION, "main")

    session.new_window.assert_called_once_with(window_name="main")
    assert ref.pane_id == pane.pane_id
    assert ref.window_id == pane.window_id
    assert ref.session_id == pane.session_id


def test_create_pane_splits_existing_window():
    split_pane = _fake_pane(pane_id="%2")
    win = _fake_window()
    win.split.return_value = split_pane
    session = _fake_session()
    session.windows = MagicMock()
    session.windows.get.return_value = win
    server = _fake_server(session=session)

    with patch("yaam.tmux._server", return_value=server):
        ref = create_pane(SESSION, "main")

    win.split.assert_called_once()
    assert ref.pane_id == "%2"


def test_create_pane_raises_if_session_missing():
    server = _fake_server(session=None)

    with (
        patch("yaam.tmux._server", return_value=server),
        pytest.raises(ValueError, match="not found"),
    ):
        create_pane(SESSION, "main")


# ---------------------------------------------------------------------------
# send_keys
# ---------------------------------------------------------------------------


def test_send_keys_calls_pane():
    pane = _fake_pane()
    server = _fake_server(pane=pane)

    with patch("yaam.tmux._server", return_value=server):
        send_keys(_pane_ref(), "ls -la")

    pane.send_keys.assert_called_once_with("ls -la")


def test_send_keys_raises_if_pane_dead():
    server = _fake_server(pane=None)

    with (
        patch("yaam.tmux._server", return_value=server),
        pytest.raises(ValueError, match="not found"),
    ):
        send_keys(_pane_ref(), "ls")


# ---------------------------------------------------------------------------
# kill_pane
# ---------------------------------------------------------------------------


def test_kill_pane_kills_live_pane():
    pane = _fake_pane()
    server = _fake_server(pane=pane)

    with patch("yaam.tmux._server", return_value=server):
        kill_pane(_pane_ref())

    pane.kill.assert_called_once()


def test_kill_pane_idempotent_when_dead():
    """Calling kill_pane on an already-dead pane must not raise."""
    server = _fake_server(pane=None)

    with patch("yaam.tmux._server", return_value=server):
        kill_pane(_pane_ref())  # should not raise


# ---------------------------------------------------------------------------
# pane_alive
# ---------------------------------------------------------------------------


def test_pane_alive_true():
    pane = _fake_pane()
    server = _fake_server(pane=pane)

    with patch("yaam.tmux._server", return_value=server):
        assert pane_alive(_pane_ref()) is True


def test_pane_alive_false():
    server = _fake_server(pane=None)

    with patch("yaam.tmux._server", return_value=server):
        assert pane_alive(_pane_ref()) is False


def test_pane_alive_false_after_kill():
    pane = _fake_pane()
    server = MagicMock()
    # First call (kill) finds the pane; second call (alive check) returns None
    server.panes.get.side_effect = [pane, None]

    with patch("yaam.tmux._server", return_value=server):
        kill_pane(_pane_ref())

    with patch("yaam.tmux._server", return_value=server):
        assert pane_alive(_pane_ref()) is False
