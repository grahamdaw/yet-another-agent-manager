# Attach targets the stored pane, not just the session

**Goal:** Make `yaam attach` land on the specific pane recorded in `PaneRef` rather than the
session's current active window, so users always arrive at the correct pane regardless of how
many windows the setup script created.

---

## Scope of changes

### `src/yaam/tmux.py`

Add a helper that returns the fully-qualified tmux target string for a pane:

```python
def pane_target(pane_ref: PaneRef) -> str:
    """Return the tmux target string for *pane_ref* in ``session:window.pane`` format."""
    return f"{pane_ref.session_id}:{pane_ref.window_id}.{pane_ref.pane_id}"
```

Using the libtmux IDs (e.g. `$3:@2.%5`) rather than names makes the target unambiguous even
when window or session names contain special characters.

### `src/yaam/cli.py`

In the `attach` command, replace the session-level target with the pane target:

```python
# Before
subprocess.run(["tmux", "switch-client", "-t", session.tmux_session], ...)
subprocess.run(["tmux", "attach-session", "-t", session.tmux_session], ...)

# After
target = tmux_mod.pane_target(session.tmux_pane_ref)
subprocess.run(["tmux", "switch-client", "-t", target], ...)
subprocess.run(["tmux", "attach-session", "-t", target], ...)
```

### `src/yaam/tests/test_tmux.py`

- Add a test: `pane_target(PaneRef(session_id="$1", window_id="@2", pane_id="%3"))` returns
  `"$1:@2.%3"`.

### `tests/test_cli.py`

- Update the `attach` tests that assert the subprocess target argument — they should now expect
  the `session_id:window_id.pane_id` format rather than the session name.

## Acceptance criteria

- `yaam attach foo` selects the exact pane stored in the session's `PaneRef`.
- The tmux target passed to `switch-client` / `attach-session` is in `$id:@id.%id` format, not
  the session name string.
- `uv run pytest` passes with no failures or errors.
- `ruff check src/ tests/` and `ruff format --check src/ tests/` both pass.
