# Consolidate worktree sanitisation and clarify fallback chain

**Goal:** Replace three copies of the same `re.sub(r'[/\\:*?"<>|]', "-", ...)` call with a single
shared utility, fix an incorrect docstring in `worktrunk.py`, add inline comments to the `create()`
fallback chain, and correct stale mock-response counts in the tests.

---

## Scope of changes

### New file: `src/yaam/utils.py`

Introduce a single public function:

```python
def sanitize_name(s: str) -> str:
    """Replace filesystem-unsafe characters with hyphens."""
```

Uses a module-level compiled regex `_UNSAFE = re.compile(r'[/\\:*?"<>|]')`.

### `src/yaam/worktrunk.py`

- Add `from yaam.utils import sanitize_name` import.
- Remove `import re` (it is only used for the one sanitisation call).
- Replace line 131: `re.sub(r'[/\\:*?"<>|]', "-", branch)` → `sanitize_name(branch)`.
- Fix `_git_find_worktree` docstring: currently says "Used as a fallback when `wt list` does not
  surface the worktree" — this is wrong; the function is the *primary* lookup. Replace with:
  "Return a `WorktreeInfo` for *branch* by parsing `git worktree list --porcelain`, or `None`
  if not found."
- Add numbered inline comments inside `create()` that correspond to the existing strategy
  docstring (items 1–5), so the code and docs are visually linked.

### `src/yaam/cli.py`

- Add `from yaam.utils import sanitize_name` import.
- Remove `import re` (only used for the one sanitisation call on line 89).
- Replace line 89: `re.sub(r'[/\\:*?"<>|]', "-", name)` → `sanitize_name(name)`.

### `src/yaam/init.py`

- Add `from yaam.utils import sanitize_name` import.
- Remove `import re` (only used for the one sanitisation call on line 32).
- Replace line 32: `re.sub(r'[/\\:*?"<>|]', "-", session_name)` → `sanitize_name(session_name)`.

### New file: `tests/test_utils.py`

Three tests for `sanitize_name`:

- Slash in input → replaced with hyphen.
- All unsafe characters (`/\:*?"<>|`) replaced in one call.
- Safe string left unchanged.

### `tests/test_worktrunk.py`

The fast-path `_git_find_worktree` call in `create()` consumes one `subprocess.run` response
before the `wt switch` call. Tests written before this fast-path was added are short one leading
response. Fix the following tests by prepending a `_completed()` response (empty stdout,
returncode 0 → fast-path returns None) and adjusting any `call_args_list` indexes:

- `test_create_returns_worktree_info`
- `test_create_raises_if_branch_not_in_list`
- `test_create_matches_branch_with_prefix`
- `test_create_injects_worktrunk_worktree_path_env` (also fix `call_args_list[0]` → `[1]`)
- `test_create_list_call_has_no_extra_env` (also fix `call_args_list[1]` → `[2]`)
- `test_create_fallback_passes_env_to_plain_switch` (also fix `call_args_list[1]` → `[2]`)

Tests that do **not** need changing: `test_create_falls_back_to_switch_when_branch_already_exists`,
`test_create_fallback_raises_if_plain_switch_also_fails`,
`test_create_no_fallback_for_unrelated_error` — for these the first mocked response already has
`returncode=1`, which naturally causes `_git_find_worktree` to return None and the existing
behaviour is correct.

## Acceptance criteria

- `uv run pytest` passes with no failures or errors.
- `grep -rn "re.sub" src/yaam/worktrunk.py src/yaam/cli.py src/yaam/init.py` returns no matches.
- `from yaam.utils import sanitize_name; sanitize_name("feat/x:y")` returns `"feat-x-y"`.
- `ruff check src/ tests/` and `ruff format --check src/ tests/` both pass.
- `_git_find_worktree` docstring no longer says "fallback".
