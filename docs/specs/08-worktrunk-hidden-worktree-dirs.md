# Hidden Worktree Directories

**Goal:** Prefix the worktree directory name with `.worktrunk-` so that yaam-managed worktrees are visually distinct and hidden by default in directory listings.

---

## Background

Worktrunk places worktrees according to its `worktree-path` config template. The built-in default is:

```
{{ repo_path }}/../{{ repo }}.{{ branch | sanitize }}
```

For a repo at `/path/to/myrepo` and branch `my-feature`, this creates `/path/to/myrepo.my-feature` — a visible sibling directory alongside the repo.

yaam currently delegates the path entirely to the user's Worktrunk config. This means yaam-managed worktrees are indistinguishable from any other worktree and clutter the parent directory.

The fix: override `WORKTRUNK_WORKTREE_PATH` at invocation time so that yaam-created worktrees follow a consistent, hidden naming scheme.

---

## Scope of changes

### `src/yaam/worktrunk.py`

**`_run()`** — add an optional `extra_env: dict[str, str] | None = None` parameter. When provided, merge it into a copy of the current process environment and pass as `env=` to `subprocess.run`.

**`create()`** — pass `extra_env` to `_run` with:

```python
extra_env = {
    "WORKTRUNK_WORKTREE_PATH": "{{ repo_path }}/../.worktrunk-{{ repo }}.{{ branch | sanitize }}"
}
```

This keeps the same parent directory as the default Worktrunk scheme but prefixes the directory name with `.worktrunk-`, making the worktree:

- Hidden by default (`ls` / Finder don't show dot-prefixed entries)
- Clearly namespaced as yaam-managed
- Still repo-and-branch addressable (e.g. `.worktrunk-myrepo.my-feature`)

No other call sites in `worktrunk.py` are changed (`remove`, `list_worktrees`, `merge` do not create worktrees).

### `tests/test_worktrunk.py`

Update tests for `create()` to assert that `subprocess.run` is called with an `env` kwarg containing `WORKTRUNK_WORKTREE_PATH` set to the template string above.

No other test files require changes.

### `README.md`

Add a note to the **Worktrunk setup** section explaining where yaam places worktrees. After the existing `wt --help` paragraph, add:

> yaam overrides Worktrunk's default worktree location. Worktrees are created as **hidden sibling directories** of your repo, named `.worktrunk-<repo>.<branch>`. For example, for repo `~/projects/api` and branch `my-feature`, the worktree is at `~/projects/.worktrunk-api.my-feature`. The leading dot keeps them out of normal directory listings.

Also update the "Spawn an agent session" step list in the Quickstart to say:

> 1. Create a git worktree on branch `my-feature` at `<repo-parent>/.worktrunk-<repo>.<branch>`

(replace the plain "Create a git worktree on branch `my-feature`" line)

### `AGENTS.md`

In the **Package Structure** section, update the `worktrunk.py` line to mention the path override:

```
├── worktrunk.py      # wt subprocess wrapper (WorktreeInfo, WorktrunkError; list via ``wt list --format=json``; sets WORKTRUNK_WORKTREE_PATH=".worktrunk-<repo>.<branch>" on create)
```

---

## Acceptance criteria

- `worktrunk.create()` passes `WORKTRUNK_WORKTREE_PATH={{ repo_path }}/../.worktrunk-{{ repo }}.{{ branch | sanitize }}` in the subprocess environment
- `worktrunk.remove()`, `list_worktrees()`, and `merge()` are unaffected — they do not set `WORKTRUNK_WORKTREE_PATH`
- Existing tests pass and new/updated tests cover the env injection in `create()`
- README Worktrunk setup section documents the `.worktrunk-<repo>.<branch>` naming convention
- README Quickstart step 1 mentions the worktree path pattern
- AGENTS.md `worktrunk.py` description notes the `WORKTRUNK_WORKTREE_PATH` override
- `ruff check` and `ruff format --check` pass
