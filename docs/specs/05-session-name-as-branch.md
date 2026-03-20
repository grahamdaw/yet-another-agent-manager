# Session Name as Branch Name

**Goal:** Use the session name directly as the git branch name so that `yaam new my-feature --profile backend` creates branch `my-feature`, removing the `default_branch_prefix` concept entirely.

---

## Scope of changes

### `src/yaam/cli.py`

**Branch name resolution (line 77):**

Before:
```python
branch_name = branch or f"{p.default_branch_prefix}{name}"
```
After:
```python
branch_name = branch or name
```

**`profile list` command:** Remove the `Branch Prefix` column and corresponding `p.default_branch_prefix` value from `table.add_column` / `table.add_row`.

### `src/yaam/profile.py`

- Remove `default_branch_prefix: str = "agent/"` field from `AgentProfile`
- Remove `default_branch_prefix=data["repo"].get("default_branch_prefix", "agent/"),` from `_parse_toml`

### `src/yaam/profiles/example.toml`

Remove the `default_branch_prefix` line from the `[repo]` section:

Before:
```toml
[repo]
path = "~/projects/my-repo"
default_branch_prefix = "agent/"
```
After:
```toml
[repo]
path = "~/projects/my-repo"
```

### `tests/test_cli.py`

- `_profile()` helper: Remove `default_branch_prefix="agent/"` from `defaults` dict
- `_worktree_info()` helper: Change default `branch="agent/foo"` → `branch="foo"`
- `_session()` helper: Change default `branch="agent/foo"` → `branch="foo"`

**Add `test_new_branch_matches_session_name`:**

```python
def test_new_branch_matches_session_name():
    with (
        patch("yaam.cli.profile_mod.load", return_value=_profile()),
        patch("yaam.cli.profile_mod.validate", return_value=[]),
        patch("yaam.cli.worktrunk.create", return_value=_worktree_info("my-feature")) as mock_create,
        patch("yaam.cli.tmux_mod.get_or_create_session"),
        patch("yaam.cli.tmux_mod.run_setup_script"),
        patch("yaam.cli.tmux_mod.create_pane", return_value=_PANE_REF),
        patch("yaam.cli.init_mod.run"),
        patch("yaam.cli.SessionStore"),
        patch("yaam.cli.config_mod.load_config", return_value=_cfg()),
    ):
        runner.invoke(app, ["new", "my-feature", "--profile", "backend"])

    mock_create.assert_called_once_with("my-feature", Path("/repo"))
```

### `tests/test_profile.py`

- `MINIMAL_TOML`: Remove `default_branch_prefix = "agent/"` line from `[repo]` section
- `_make_profile()` helper: Remove `default_branch_prefix="agent/"` from `defaults` dict
- `test_load_returns_profile`: Remove `assert p.default_branch_prefix == "agent/"` line
- `test_load_defaults_branch_prefix`: Delete entirely (tests a removed field)

### `README.md`

**Quickstart profile TOML example (lines ~64–80):** Remove `default_branch_prefix = "agent/"`.

**"This will:" list (lines ~93–97):** Update branch reference:

Before: `1. Create a git worktree on branch 'agent/my-feature'`
After:  `1. Create a git worktree on branch 'my-feature'`

**Profile authoring table:** Remove the `default_branch_prefix` row.

### `AGENTS.md`

- Update `profile.py` description in Package Structure: remove mention of `default_branch_prefix`
- Add spec reference `05-session-name-as-branch.md` to the specs list in Repository Structure
- Add Stage 12 to the Implementation Plan table:

| 12 | Session name as branch | Planned | `05-session-name-as-branch.md` | Branch name equals session name; `default_branch_prefix` removed |

### `.claude/skills/create-profile/SKILL.md`

- **Profile TOML format block:** Remove `default_branch_prefix` line
- **Fields table:** Remove the `default_branch_prefix` row
- **Common patterns — monorepo section:** Remove the per-profile `default_branch_prefix` examples; update to note that branch names come directly from the session name passed to `yaam new`

---

## Acceptance criteria

- `yaam new my-feature --profile backend` calls `worktrunk.create("my-feature", ...)` — no prefix applied
- `yaam new my-feature --profile backend --branch custom` still calls `worktrunk.create("custom", ...)` — explicit `--branch` override still works
- `uv run pytest tests/test_cli.py -v` passes, including new `test_new_branch_matches_session_name`
- `uv run pytest tests/test_profile.py -v` passes; `test_load_defaults_branch_prefix` no longer exists
- `uv run pytest tests/ -q` — no regressions across all 124+ tests
- `uv run ruff check src/ tests/` passes with no errors
- `default_branch_prefix` does not appear in `src/` or `tests/` (`grep` clean)
- README quickstart shows branch `my-feature` (not `agent/my-feature`)
- `yaam profile list` output no longer has a "Branch Prefix" column
- `AGENTS.md` references Stage 12 and the spec file
- `create-profile` skill no longer mentions `default_branch_prefix`
