# Pass Session Name as First Argument to tmux Setup Script

**Goal:** Give the tmux setup script access to the session name by passing it as `$1`, with the worktree path shifting to `$2`, so scripts can target the correct tmux session by name.

---

## Scope of changes

### `src/yaam/tmux.py`

In `run_setup_script`, change the subprocess invocation from:

```python
[str(script_path), str(worktree_path)]
```

to:

```python
[str(script_path), str(session_name), str(worktree_path)]
```

No signature changes — `session_name` is already the third parameter.

### `tests/test_tmux.py`

**Update `test_run_setup_script_success`:**

Currently asserts:

```python
assert args == [str(SCRIPT), str(WORKTREE)]
```

Change to:

```python
assert args == [str(SCRIPT), SESSION, str(WORKTREE)]
```

### `README.md`

**Profile authoring table (line ~129):** Update `tmux.setup_script` description:

Before: `Script that builds your tmux layout; receives the worktree path as $1`
After:  `Script that builds your tmux layout; receives session name as $1 and worktree path as $2`

### `src/yaam/profiles/example.toml`

Update the comment on `setup_script`:

Before: `# your existing tmux layout script; called with the worktree path as $1`
After:  `# your existing tmux layout script; called with session name as $1 and worktree path as $2`

### `AGENTS.md`

- Add `04-tmux-script-session-arg.md` to the specs list in the Repository Structure section.
- Add a new row to the Implementation Plan table:

| Stage | Name | Status | Spec | Description |
|---|---|---|---|---|
| 11 | tmux script session arg | Planned | `04-tmux-script-session-arg.md` | Pass session name as `$1` and worktree path as `$2` to tmux setup scripts |

---

## Acceptance criteria

- `uv run pytest tests/test_tmux.py -v` passes, including:
  - `test_run_setup_script_success` — asserts `args == [str(SCRIPT), SESSION, str(WORKTREE)]`
  - All other `run_setup_script` tests unchanged and passing
- `uv run pytest tests/` passes with no regressions
- `uv run ruff check src/ tests/` passes with no errors
- README profile authoring table reflects `$1` = session name, `$2` = worktree path
- `example.toml` comment on `setup_script` reflects new argument order
- `AGENTS.md` references this spec and stage 11
