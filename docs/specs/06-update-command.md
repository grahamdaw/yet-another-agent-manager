# Update Command

**Goal:** Add a `yaam update` command that pulls the latest changes from the upstream repository and reinstalls the tool in-place, supporting the clone-and-install distribution model.

---

## Scope of changes

Because yaam is distributed as a clone-and-install project (not PyPI), updating means:
1. locating the source directory of the installed package
2. running `git pull` there
3. reinstalling with `uv tool install . --force` (or `pip install -e .` as a fallback)

### Files to change

- **`src/yaam/cli.py`** — add `update` command
- **`tests/test_cli.py`** — add tests for the new command
- **`AGENTS.md`** — add Stage 13 to the implementation table

### Command interface

```
yaam update [--check]
```

- `yaam update` — pull + reinstall; print what changed (git summary line) or "already up to date"
- `yaam update --check` — `git fetch origin main` only; report whether an update is available without applying it

### Source-directory discovery

The command determines the source repo root via `importlib.resources` or by resolving the path of the installed `yaam` package (`Path(yaam.__file__).parent.parent.parent` for a `src/` layout). It must validate that the resolved path is a git repository before running git commands.

### Steps executed by `yaam update`

1. Resolve source directory; abort with a clear error if not a git repo.
2. Run `git pull --ff-only origin main` in the source directory, always targeting `main` regardless of the currently checked-out branch.
   - If already up to date, print "Already up to date." and exit 0.
   - If fast-forward applied, capture the one-line summary (e.g. `abc1234..def5678  main -> origin/main`).
3. Reinstall using `uv tool install . --force` if `uv` is on `PATH`; otherwise fall back to `pip install .`.
4. Print a success message including the git summary.

### Error handling

- Source dir is not a git repo → `[red]Error:[/red]` message, exit 1
- `git pull` returns non-zero → print stderr, exit 1
- reinstall fails → print stderr, exit 1

---

## Acceptance criteria

- `yaam update` pulls from upstream and reinstalls when a source git repo is reachable.
- `yaam update --check` exits 0 and reports "Update available" or "Already up to date" without modifying anything.
- When the source directory cannot be resolved to a git repo, `yaam update` exits 1 with a helpful error.
- `ruff check` and `ruff format --check` pass.
- All existing tests continue to pass; new tests cover the happy path, `--check` flag, and the non-git-repo error case.
