# Kill tears down the tmux session

**Goal:** Make `yaam kill` fully destroy the tmux session (not just the pane), so that recreating
a session with the same name always starts from a clean tmux state.

---

## Scope of changes

### `src/yaam/cli.py`

In the `kill` command, add a `kill_session` call after `kill_pane`:

```python
with contextlib.suppress(Exception):
    tmux_mod.kill_pane(session.tmux_pane_ref)

with contextlib.suppress(Exception):
    tmux_mod.kill_session(session.tmux_session)
```

`kill_session` is already implemented and idempotent (`tmux.py` lines 142–148) — no changes
needed there.

### `tests/test_cli.py`

- Add a test: `yaam kill foo` calls both `kill_pane` and `kill_session` with the correct arguments.
- Add a test: if `kill_pane` raises, `kill_session` is still called (i.e. the two suppressions are
  independent).

## Acceptance criteria

- `yaam kill foo` destroys the tmux session named `foo` (verified via `tmux has-session -t foo`
  returning non-zero after kill).
- `yaam kill foo` followed by `yaam new foo` creates a fresh tmux session with no pre-existing
  windows or panes from the previous session.
- `uv run pytest` passes with no failures or errors.
- `ruff check src/ tests/` and `ruff format --check src/ tests/` both pass.
- `grep -n "kill_session" src/yaam/cli.py` matches the `kill` command.
