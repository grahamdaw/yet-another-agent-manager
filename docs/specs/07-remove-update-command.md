# Remove `yaam update` Command

**Goal:** Remove the `yaam update` command. It does not work with the recommended `uv tool install .` installation method, and the manual update flow is simple enough that a dedicated command adds no value.

---

## Background

The `update` command (`cli.py:347-424`) locates the yaam source repo by walking up from `yaam.__file__` looking for a `.git` directory. With `uv tool install .`, the installed package lives inside the uv tools environment (`~/.local/share/uv/tools/yaam/...`), not the cloned repo. Walking up from there never finds `.git`, so the command always fails with:

> Cannot locate the yaam source repository.

The command only works with `pip install -e .` (editable installs). Since the recommended method is `uv tool install .`, the command is effectively broken for the primary use case. The manual update flow is two commands:

```bash
git pull
uv tool install --force .
```

---

## Scope of changes

### `src/yaam/cli.py`

- Remove the `_find_source_dir()` helper function (`cli.py:335-344`)
- Remove the `update` command and its implementation (`cli.py:347-424`)

### `tests/test_cli.py`

- Remove all tests covering the `update` command and `_find_source_dir()`

### `README.md`

- Remove `yaam update` row from the Commands reference table
- Update the Installation section: replace the re-run instruction for `uv tool install .` with an explicit note that updating is `git pull && uv tool install --force .`
- Replace any "personal use" or "personal" framing with "local use" / "local install"

### `AGENTS.md`

- Remove Stage 13 (`Update command`) from the Implementation Plan table
- Update `cli.py` description in the Package Structure section to remove `update` from the command list
- Remove `update` from the commands line in the Package Structure code block

---

## Acceptance criteria

- `yaam update` no longer exists as a command
- `yaam --help` does not list `update`
- README documents the manual update flow (`git pull && uv tool install --force .`)
- `ruff check` and `ruff format --check` pass
- All remaining tests pass
