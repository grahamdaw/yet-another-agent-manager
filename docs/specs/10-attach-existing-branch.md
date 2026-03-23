# Attach to existing branch on `yaam new`

**Goal:** When `yaam new <name>` is called and the branch already exists, reuse the existing
branch/worktree instead of failing, so interrupted or repeated sessions don't require manual
`wt switch` invocations.

---

## Background

`worktrunk.create()` calls `wt switch --create <branch>`. If the branch already exists, `wt`
exits 1 with:

```
✗ Branch <branch> already exists
↳ To switch to the existing branch, run without --create: wt switch <branch>
```

This causes `WorktrunkError` to bubble up and the entire `yaam new` invocation fails, even though
the desired state (a worktree on that branch) is already achievable.

---

## Scope of changes

### `src/yaam/worktrunk.py`

**`create()` — fallback on existing branch:**

- After calling `_run(["switch", "--create", branch])`, if a `WorktrunkError` is raised and the
  error message contains `"already exists"` (case-insensitive), fall back to
  `_run(["switch", branch], cwd=repo_path, extra_env=extra_env)`.
- If the fallback also fails, re-raise that error.
- After either the `--create` path or the fallback path, call `list_worktrees()` as today to
  locate and return the `WorktreeInfo` for the branch.
- No new exception type is needed — the fallback is silent and transparent.

### `src/yaam/cli.py`

**`new` command — status message:**

- Change the status spinner text from:
  ```
  Creating worktree for branch '<branch>'...
  ```
  to:
  ```
  Setting up worktree for branch '<branch>'...
  ```
  This phrasing is accurate for both the create and attach paths.

- No other changes to `cli.py`.

### `tests/test_worktrunk.py`

Add tests for the fallback behaviour in `create()`:

- When `wt switch --create` exits 1 with stderr containing `"already exists"`, a second
  `wt switch` call (without `--create`) is made.
- If the fallback `wt switch` succeeds, `create()` returns the correct `WorktreeInfo`.
- If the fallback `wt switch` also fails (e.g. branch doesn't exist locally either), the error
  from the fallback is raised (not the original error).
- When `wt switch --create` fails for a reason *other* than "already exists" (e.g.
  `"permission denied"`), no fallback is attempted and the original `WorktrunkError` is raised.

---

## Acceptance criteria

- `yaam new feat/ktc-400-imnproved-data-model --profile <profile>` succeeds when
  `feat/ktc-400-imnproved-data-model` already exists as a git branch, printing
  `✓ Agent '...' spawned on branch '...'`.
- Running `yaam new <name>` twice in a row (first succeeds, second tries to re-create) does not
  error on the second invocation — it attaches to the existing worktree.
- When `wt switch --create` fails for an unrelated reason, the original error is still surfaced
  (no silent swallowing of non-"already exists" errors).
- All existing tests pass.
- `ruff check` and `ruff format --check` pass.
