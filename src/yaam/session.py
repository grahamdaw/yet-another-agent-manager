"""AgentSession model and state file."""

import json
from datetime import datetime
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel

from yaam.tmux import PaneRef

STATE_FILE = Path("~/.config/yaam/sessions.json")


class AgentSession(BaseModel):
    """Persistent record of a live agent session."""

    name: str
    branch: str
    profile_name: str
    worktree_path: Path
    tmux_session: str
    tmux_pane_ref: PaneRef | None = None
    created_at: datetime
    status: str = "running"


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
        """Persist *session*, overwriting any existing entry with the same name."""
        with self._lock:
            data = self._read()
            data[session.name] = session.model_dump(mode="json")
            self._write(data)

    def get(self, name: str) -> AgentSession | None:
        """Return the session named *name*, or None if it does not exist."""
        data = self._read()
        entry = data.get(name)
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

    def remove(self, name: str) -> None:
        """Remove the session named *name*. Silent no-op if it does not exist."""
        with self._lock:
            data = self._read()
            data.pop(name, None)
            self._write(data)

    def update_status(self, name: str, status: str) -> None:
        """Update the status field of an existing session. No-op if not found."""
        with self._lock:
            data = self._read()
            if name in data:
                data[name]["status"] = status
                self._write(data)
