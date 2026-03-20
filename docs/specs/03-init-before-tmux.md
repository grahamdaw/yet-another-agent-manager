# Run Init Script Before Tmux

**Goal:** Move `init_mod.run(...)` to execute after worktree creation but before the tmux
session/pane is set up, so the worktree is fully initialised before the layout is built.

---

## Scope of changes

### `src/yaam/cli.py`

Reorder steps in `new()`. Current order:

1. `worktrunk.create(...)`
2. `tmux_mod.get_or_create_session(...)`
3. `tmux_mod.run_setup_script(...)`
4. `tmux_mod.create_pane(...)`
5. `init_mod.run(...)`  ← currently last

New order:

1. `worktrunk.create(...)`
2. `init_mod.run(...)`  ← moved here
3. `tmux_mod.get_or_create_session(...)`
4. `tmux_mod.run_setup_script(...)`
5. `tmux_mod.create_pane(...)`

Move the `with console.status("Running init script..."):` block (currently lines 96–97) to
immediately after the worktree creation block, before the tmux block. No change to the `except`
cleanup logic — `pane_ref` will still be `None` if init fails, so `kill_pane` is correctly
skipped.

### `tests/test_cli.py`

**Update `test_new_cleans_up_on_init_failure`:**

With the new order, init runs before `create_pane`, so `pane_ref` is `None` when init raises.

- Remove `patch("yaam.cli.tmux_mod.create_pane", ...)` (not reached)
- Remove `patch("yaam.cli.tmux_mod.get_or_create_session")` and `patch("yaam.cli.tmux_mod.run_setup_script")` (not reached)
- Change `mock_kill.assert_called_once_with(_PANE_REF)` → `mock_kill.assert_not_called()`
- Keep `mock_remove.assert_called_once_with(_WORKTREE)`

**Add `test_new_init_runs_before_tmux`:**

Use a shared `call_order` list with `side_effect` lambdas to assert `init_mod.run` is called
before `tmux_mod.get_or_create_session`:

```python
def test_new_init_runs_before_tmux(tmp_path):
    call_order = []
    with (
        patch("yaam.cli.profile_mod.load", return_value=_profile()),
        patch("yaam.cli.profile_mod.validate", return_value=[]),
        patch("yaam.cli.worktrunk.create", return_value=_worktree_info()),
        patch("yaam.cli.init_mod.run", side_effect=lambda *a, **kw: call_order.append("init")),
        patch(
            "yaam.cli.tmux_mod.get_or_create_session",
            side_effect=lambda *a: call_order.append("tmux"),
        ),
        patch("yaam.cli.tmux_mod.run_setup_script"),
        patch("yaam.cli.tmux_mod.create_pane", return_value=_PANE_REF),
        patch("yaam.cli.SessionStore"),
        patch("yaam.cli.config_mod.load_config", return_value=_cfg()),
    ):
        result = runner.invoke(app, ["new", "foo", "--profile", "backend"])

    assert result.exit_code == 0
    assert call_order == ["init", "tmux"]
```

### `README.md`

**"This will:" list (lines 93–97):** Swap items 2 and 3 to reflect new order:

```
1. Create a git worktree on branch `agent/my-feature`
2. Run your init script (install deps, copy `.env`, etc.)
3. Run your tmux setup script to build the layout
4. Save session state
```

**Profile authoring table (line 130):** Update `init.script` description:

Before: `Post-setup script; receives repo_path $1 and worktree_path $2`
After:  `Runs after worktree setup, before tmux; receives repo_path $1 and worktree_path $2`

### `src/yaam/profiles/example.toml`

- Move `[init]` section before `[tmux]` section
- Update comment on line 15:

Before: `# called once after tmux setup; receives worktree path as $1`
After:  `# called after worktree setup, before tmux; receives repo_path as $1 and worktree_path as $2`

---

## Acceptance criteria

- `uv run pytest tests/test_cli.py -v` passes, including:
  - `test_new_happy_path` — still passes unchanged
  - `test_new_cleans_up_on_init_failure` — `kill_pane` not called, `remove` called
  - `test_new_init_runs_before_tmux` — `call_order == ["init", "tmux"]`
  - `test_new_cleans_up_worktree_if_no_pane_yet` — still passes unchanged
- `uv run ruff check src/ tests/` passes with no errors
- README "This will:" list reflects new order (init before tmux)
- `example.toml` has `[init]` section before `[tmux]` with updated comment
