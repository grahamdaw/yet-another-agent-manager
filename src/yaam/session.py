"""AgentSession model and state file."""

import json
from datetime import datetime
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, model_validator

from yaam.utils import sanitize_name

STATE_FILE = Path("~/.config/yaam/sessions.json")


class AgentSession(BaseModel):
    """Persistent record of a live agent session.

    ``key`` is the canonical internal identifier — always equal to
    ``sanitize_name(display_name)`` and used as the store key, tmux session
    name, and for all internal lookups.

    ``display_name`` is the original name as typed by the user and is used
    only for display purposes (e.g. ``yaam list``).

    The session is tracked at the **tmux session** level — there is a strict
    1:1 mapping between an agent and its dedicated tmux session, so the
    session name alone is enough to drive liveness checks, attach, and
    teardown. Earlier versions stored a ``tmux_pane_ref`` here; that field
    is silently dropped on load so existing ``sessions.json`` files keep
    working.
    """

    # ``extra="ignore"`` lets us silently drop the legacy ``tmux_pane_ref``
    # field from older sessions.json entries without raising a validation
    # error.
    model_config = ConfigDict(extra="ignore")

    key: str
    display_name: str
    branch: str
    profile_name: str
    worktree_path: Path
    tmux_session: str
    created_at: datetime
    status: str = "running"

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy(cls, values: object) -> object:
        """Map legacy ``name`` field to ``key`` / ``display_name``."""
        if not isinstance(values, dict):
            return values
        if "key" not in values and "name" in values:
            display = values.pop("name")
            values["key"] = sanitize_name(display)
            values.setdefault("display_name", display)
        elif "display_name" not in values and "key" in values:
            values["display_name"] = values["key"]
        return values


class SessionStore:
    """Read/write the session state JSON file with file-locking for safety."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = (path or STATE_FILE).expanduser()
        self._lock = FileLock(str(self._path.with_suffix(".lock")))

    def _read(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        with self._path.open() as fh:
            return json.load(fh)

    def _write(self, data: dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def add(self, session: AgentSession) -> None:
        """Persist *session*, overwriting any existing entry with the same key.

        Use add_exclusive() when creating a new session to prevent races.
        """
        with self._lock:
            data = self._read()
            data[session.key] = session.model_dump(mode="json")
            self._write(data)

    def add_exclusive(self, session: AgentSession) -> None:
        """Persist *session*, raising KeyError if a session with the same key already exists.

        Performs the existence check and write inside a single lock acquisition, making it
        safe to call from concurrent processes.
        """
        with self._lock:
            data = self._read()
            if session.key in data:
                raise KeyError(session.key)
            data[session.key] = session.model_dump(mode="json")
            self._write(data)

    def get(self, key: str) -> AgentSession | None:
        """Return the session with the given *key*, or None if it does not exist."""
        data = self._read()
        entry = data.get(key)
        if entry is None:
            return None
        return AgentSession.model_validate(entry)

    def get_by_index(self, index: int) -> AgentSession | None:
        """Return the session at 0-based position *index*, or None if out of range."""
        sessions = self.list()
        if index < 0 or index >= len(sessions):
            return None
        return sessions[index]

    def list(self) -> list[AgentSession]:
        """Return all stored sessions."""
        data = self._read()
        return [AgentSession.model_validate(v) for v in data.values()]

    def remove(self, key: str) -> None:
        """Remove the session with the given *key*. Silent no-op if it does not exist."""
        with self._lock:
            data = self._read()
            data.pop(key, None)
            self._write(data)

    def update_status(self, key: str, status: str) -> None:
        """Update the status field of an existing session. No-op if not found."""
        with self._lock:
            data = self._read()
            if key in data:
                data[key]["status"] = status
                self._write(data)
