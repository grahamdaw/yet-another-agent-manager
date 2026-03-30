# Sanitized name as canonical internal session key

**Goal:** Make the sanitized session name the single internal key for all session lookups, so two
names that differ only in sanitized characters (e.g. `my/feature` and `my-feature`) are treated as
the same session, eliminating the collision that bypasses the duplicate check.

---

## Scope of changes

### `src/yaam/session.py`

- Add a `display_name: str` field to `AgentSession` (the original, unsanitized name as provided
  by the user).
- The existing `name` field becomes the canonical internal key and must always equal
  `sanitize_name(display_name)`. Rename it to `key` to make the contract explicit:

  ```python
  class AgentSession(BaseModel):
      key: str            # sanitize_name(display_name) — internal store key and tmux session name
      display_name: str   # original name as provided by the user
      branch: str
      ...
      tmux_session: str   # kept for clarity; always equals key
  ```

  > **Migration note:** existing `sessions.json` entries use `name` not `key` — add a
  > `model_validator(mode="before")` that maps `name → key` and `key → display_name` when
  > `display_name` is absent, so old state files continue to load.

- `SessionStore` — change the dict key from `session.name` to `session.key` throughout:
  - `add()`: `data[session.key] = ...`
  - `get(key)`: looks up by sanitized key
  - `remove(key)`: removes by sanitized key
  - `update_status(key, status)`: updates by sanitized key

### `src/yaam/cli.py`

- Add a helper `_session_key(name: str) -> str` that returns `sanitize_name(name)`. Use it
  everywhere a name is converted to a store/tmux key.
- `new` command:
  - Duplicate check: `store.get(sanitize_name(name)) is not None` (was `store.get(name)`).
  - Build `AgentSession` with `key=sanitize_name(name)`, `display_name=name`.
- `kill` and `attach` commands:
  - Look up by `sanitize_name(name)` so `yaam kill my/feature` and `yaam kill my-feature` both
    resolve to the same session.
- `list` command:
  - Display `s.display_name` in the Name column (was `s.name`).
  - The tmux session column continues to show `s.tmux_session` (unchanged).
- `sync` command: no change needed; iterates over all sessions, not by key.

### `src/yaam/utils.py`

- Add a module docstring noting that `sanitize_name` output is the canonical internal session key.

### `tests/test_session.py`

- Update all `AgentSession(name=...)` constructions to `AgentSession(key=..., display_name=...)`.
- Add a test: loading a legacy JSON entry (with `name` but no `display_name`) deserialises
  correctly — `key == display_name == name`.
- Add a test: `SessionStore.get` with the sanitized key finds the session regardless of the
  original display name.

### `tests/test_cli.py`

- Update fixture session constructions to use `key`/`display_name`.
- Add a test: `yaam new my-feature` fails when a session with key `my-feature` already exists
  (even if the existing session was created as `my/feature`).
- Add a test: `yaam kill my/feature` correctly kills a session whose key is `my-feature`.

## Acceptance criteria

- `yaam new my/feature` followed by `yaam new my-feature` is rejected with a clear error naming
  the collision (`my-feature` already exists).
- `yaam list` shows the original name as typed by the user in the Name column.
- `yaam kill my/feature` and `yaam kill my-feature` both resolve to the same session.
- Loading an existing `sessions.json` that uses the old `name` field (no `display_name`) does not
  raise a validation error.
- `uv run pytest` passes with no failures or errors.
- `ruff check src/ tests/` and `ruff format --check src/ tests/` both pass.
- `grep -n "store.get(name)" src/yaam/cli.py` returns no matches.
