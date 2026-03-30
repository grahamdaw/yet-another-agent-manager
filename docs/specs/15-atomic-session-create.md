# Atomic session create: eliminate TOCTOU race in `yaam new`

**Goal:** Make the duplicate-name check and store write a single atomic operation so that two
concurrent `yaam new foo` invocations cannot both succeed and overwrite each other's session state.

---

## Scope of changes

### `src/yaam/session.py`

Replace the current `add()` method (which silently overwrites) with two methods:

```python
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
```

Remove the pre-flight `store.get(name)` duplicate check from `cli.py` — it is replaced by the
exception raised by `add_exclusive()`.

### `src/yaam/cli.py`

- Remove the `store.get(name)` check and its error block (lines 77–83).
- Replace `SessionStore().add(...)` at the end of `new()` with `SessionStore().add_exclusive(...)`.
- Catch `KeyError` from `add_exclusive()` in the existing `except Exception` block, or add a
  targeted handler before it that prints the same user-friendly message as the removed pre-flight
  check:

  ```
  Error: Session 'foo' already exists. Use `yaam kill foo` first.
  ```

  The catch must trigger cleanup (kill pane, remove worktree) exactly as the existing handler does.

### `tests/test_session.py`

- Add a test: `add_exclusive()` raises `KeyError` when a session with the same key already exists.
- Add a test: `add_exclusive()` succeeds when the key is absent.
- Add a test: concurrent `add_exclusive()` calls for the same key — patch `FileLock.__enter__` to
  simulate a race (second caller reads before first caller writes) and confirm exactly one call
  raises `KeyError`.
- Keep existing `add()` tests; update any that relied on the overwrite-protection behaviour of the
  old `add()` to use `add_exclusive()` instead.

### `tests/test_cli.py`

- Remove or update tests that mock `store.get` returning a non-None value to trigger the duplicate
  check — that path no longer exists.
- Add a test: when `add_exclusive()` raises `KeyError`, `yaam new` prints the correct error message
  and exits with code 1.
- Add a test: when `add_exclusive()` raises `KeyError`, the pane and worktree cleanup paths are
  invoked (mock `kill_pane` and `worktrunk.remove`).

## Acceptance criteria

- `yaam new foo` when `foo` already exists exits with code 1 and prints a clear error.
- Two concurrent `yaam new foo` calls: exactly one succeeds; the other exits with code 1 and
  cleans up its tmux pane and worktree.
- No `store.get(name)` duplicate check remains in `cli.py` (`grep -n "store.get" src/yaam/cli.py`
  returns no matches for a pre-flight check).
- `uv run pytest` passes with no failures or errors.
- `ruff check src/ tests/` and `ruff format --check src/ tests/` both pass.
