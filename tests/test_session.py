"""Unit tests for agent.session and agent.config modules."""

import datetime as dt
import json
from pathlib import Path

from yaam.config import AgentConfig, load_config
from yaam.session import AgentSession, SessionStore
from yaam.tmux import PaneRef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
_PANE_REF = PaneRef(session_id="$1", window_id="@1", pane_id="%1")


def _session(**kwargs) -> AgentSession:
    defaults = dict(
        key="foo",
        display_name="foo",
        branch="agent/foo",
        profile_name="backend",
        worktree_path=Path("/repo/foo"),
        tmux_session="agent",
        tmux_pane_ref=_PANE_REF,
        created_at=_NOW,
        status="running",
    )
    defaults.update(kwargs)
    return AgentSession(**defaults)


def _store(tmp_path: Path) -> SessionStore:
    return SessionStore(path=tmp_path / "sessions.json")


# ---------------------------------------------------------------------------
# AgentSession — serialisation round-trip
# ---------------------------------------------------------------------------


def test_session_round_trips_to_json():
    s = _session()
    data = s.model_dump(mode="json")
    s2 = AgentSession.model_validate(data)
    assert s2.key == s.key
    assert s2.display_name == s.display_name
    assert s2.profile_name == s.profile_name
    assert s2.tmux_pane_ref.pane_id == s.tmux_pane_ref.pane_id


def test_session_pane_ref_serialised_as_dict():
    data = _session().model_dump(mode="json")
    assert isinstance(data["tmux_pane_ref"], dict)
    assert data["tmux_pane_ref"]["pane_id"] == "%1"


def test_session_pane_ref_deserialised_from_dict():
    data = _session().model_dump(mode="json")
    s = AgentSession.model_validate(data)
    assert isinstance(s.tmux_pane_ref, PaneRef)
    assert s.tmux_pane_ref.session_id == "$1"


def test_session_default_status_is_running():
    s = AgentSession(
        key="x",
        display_name="x",
        branch="b",
        profile_name="p",
        worktree_path=Path("/r"),
        tmux_session="agent",
        tmux_pane_ref=_PANE_REF,
        created_at=_NOW,
    )
    assert s.status == "running"


# ---------------------------------------------------------------------------
# AgentSession — legacy migration
# ---------------------------------------------------------------------------


def test_legacy_name_field_migrates_to_key_and_display_name():
    """Old sessions.json entries (with `name`) deserialise without error."""
    legacy = {
        "name": "my/feature",
        "branch": "my/feature",
        "profile_name": "backend",
        "worktree_path": "/repo/foo",
        "tmux_session": "my-feature",
        "tmux_pane_ref": None,
        "created_at": _NOW.isoformat(),
        "status": "running",
    }
    s = AgentSession.model_validate(legacy)
    assert s.key == "my-feature"
    assert s.display_name == "my/feature"


def test_legacy_name_field_plain_value_round_trips():
    """Legacy entry where name has no unsafe chars: key == display_name == name."""
    legacy = {
        "name": "foo",
        "branch": "foo",
        "profile_name": "backend",
        "worktree_path": "/repo/foo",
        "tmux_session": "foo",
        "tmux_pane_ref": None,
        "created_at": _NOW.isoformat(),
        "status": "running",
    }
    s = AgentSession.model_validate(legacy)
    assert s.key == "foo"
    assert s.display_name == "foo"


def test_missing_display_name_falls_back_to_key():
    """New-format entry without display_name falls back to key."""
    data = {
        "key": "my-feature",
        "branch": "my-feature",
        "profile_name": "backend",
        "worktree_path": "/repo/foo",
        "tmux_session": "my-feature",
        "tmux_pane_ref": None,
        "created_at": _NOW.isoformat(),
        "status": "running",
    }
    s = AgentSession.model_validate(data)
    assert s.display_name == "my-feature"


# ---------------------------------------------------------------------------
# SessionStore — add / get / list / remove / update_status
# ---------------------------------------------------------------------------


def test_store_add_and_get(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo"))
    result = store.get("foo")
    assert result is not None
    assert result.key == "foo"
    assert result.display_name == "foo"
    assert result.profile_name == "backend"


def test_store_get_returns_none_for_unknown(tmp_path):
    store = _store(tmp_path)
    assert store.get("unknown") is None


def test_store_get_returns_none_when_file_absent(tmp_path):
    store = SessionStore(path=tmp_path / "no_such_file.json")
    assert store.get("x") is None


def test_store_list_returns_all(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo"))
    store.add(_session(key="bar", display_name="bar"))
    sessions = store.list()
    keys = {s.key for s in sessions}
    assert keys == {"foo", "bar"}


def test_store_list_empty_when_no_file(tmp_path):
    store = SessionStore(path=tmp_path / "missing.json")
    assert store.list() == []


def test_store_remove(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo"))
    store.remove("foo")
    assert store.get("foo") is None


def test_store_remove_nonexistent_is_noop(tmp_path):
    store = _store(tmp_path)
    store.remove("ghost")  # must not raise


def test_store_update_status(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo", status="running"))
    store.update_status("foo", "dead")
    assert store.get("foo").status == "dead"


def test_store_update_status_noop_for_unknown(tmp_path):
    store = _store(tmp_path)
    store.update_status("ghost", "dead")  # must not raise


def test_store_overwrites_existing_key(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo", branch="agent/foo"))
    store.add(_session(key="foo", display_name="foo", branch="agent/foo-v2"))
    assert store.get("foo").branch == "agent/foo-v2"


def test_store_survives_process_restart(tmp_path):
    """Data written by one store instance is readable by a new instance."""
    path = tmp_path / "sessions.json"
    store1 = SessionStore(path=path)
    store1.add(_session(key="foo", display_name="foo"))

    store2 = SessionStore(path=path)
    result = store2.get("foo")
    assert result is not None
    assert result.key == "foo"


def test_store_profile_name_round_trips(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo", profile_name="my-profile"))
    assert store.get("foo").profile_name == "my-profile"


def test_store_written_as_valid_json(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="foo", display_name="foo"))
    path = tmp_path / "sessions.json"
    data = json.loads(path.read_text())
    assert "foo" in data


def test_store_sanitized_key_prevents_collision(tmp_path):
    """Two names that sanitize to the same key occupy the same store slot."""
    store = _store(tmp_path)
    store.add(_session(key="my-feature", display_name="my/feature"))
    # A second add with the same key (from a different display name) overwrites
    store.add(_session(key="my-feature", display_name="my-feature"))
    sessions = store.list()
    assert len(sessions) == 1
    assert sessions[0].key == "my-feature"


def test_store_get_by_sanitized_key(tmp_path):
    """get() uses the sanitized key, not the display name."""
    store = _store(tmp_path)
    store.add(_session(key="my-feature", display_name="my/feature"))
    result = store.get("my-feature")
    assert result is not None
    assert result.display_name == "my/feature"
    # Looking up by the unsanitized display name returns nothing
    assert store.get("my/feature") is None


# ---------------------------------------------------------------------------
# SessionStore.get_by_index
# ---------------------------------------------------------------------------


def test_get_by_index_empty_store(tmp_path):
    assert _store(tmp_path).get_by_index(0) is None


def test_get_by_index_valid(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="alpha", display_name="alpha"))
    store.add(_session(key="beta", display_name="beta"))
    assert store.get_by_index(0).key == "alpha"
    assert store.get_by_index(1).key == "beta"


def test_get_by_index_out_of_range(tmp_path):
    store = _store(tmp_path)
    store.add(_session(key="only", display_name="only"))
    assert store.get_by_index(1) is None
    assert store.get_by_index(-1) is None


# ---------------------------------------------------------------------------
# AgentConfig / load_config
# ---------------------------------------------------------------------------


def test_load_config_defaults_when_missing(tmp_path):
    cfg = load_config(tmp_path / "no_config.toml")
    assert cfg.default_profile == ""
    assert cfg.tmux_session_name == "agent"
    assert "sessions.json" in str(cfg.state_file_path)


def test_load_config_reads_file(tmp_path):
    toml = (
        'default_profile = "backend"\n'
        'tmux_session_name = "my-agent"\n'
        'state_file_path = "/tmp/sessions.json"\n'
    )
    path = tmp_path / "config.toml"
    path.write_text(toml)
    cfg = load_config(path)
    assert cfg.default_profile == "backend"
    assert cfg.tmux_session_name == "my-agent"
    assert cfg.state_file_path == Path("/tmp/sessions.json")


def test_load_config_partial_file_uses_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('default_profile = "backend"\n')
    cfg = load_config(path)
    assert cfg.default_profile == "backend"
    assert cfg.tmux_session_name == "agent"  # default


def test_agent_config_model_defaults():
    cfg = AgentConfig()
    assert cfg.default_profile == ""
    assert cfg.tmux_session_name == "agent"
