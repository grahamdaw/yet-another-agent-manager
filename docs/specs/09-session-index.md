# Session Index

**Goal:** Show a numerical index for each session in `yaam list` and allow `yaam attach` to accept
either a session name or its index, making it faster to attach when you can see the list.

---

## Scope of changes

### `src/yaam/cli.py`

**`new` command — name validation:**

- Reject session names that are purely numeric (i.e. `str.isdigit()` is true) with an error
  before any resources are created:
  ```
  Error: Session name '3' is not allowed — purely numeric names conflict with session indexes.
         Choose a descriptive name such as 'feature-3' or 'worker-3'.
  ```
- Exit with code 1.

**`list_sessions` command:**

- Add a `#` column as the first column in the rich table, showing the 0-based integer index of
  each row (i.e. `0`, `1`, `2`, …).
- The column header is `#`, unstyled or dim.
- The JSON output path (`--json`) is unchanged — indexes are not included in JSON output, as they
  are a transient positional concept.

**`attach` command:**

- Update the argument `help` text to:
  `"Name or index (from 'yaam list') of the session to attach to"`.
- Resolution logic (in order):
  1. Try to parse the argument as a non-negative integer.
  2. If successful, call `store.get_by_index(index)`.
  3. If the index is out of range, print `[red]Error:[/red] No session at index N` and exit 1.
  4. If the argument is not a valid integer, fall through to `store.get(name)` as today.
  5. The "no session named X" error message is unchanged for the name path.
- Because purely numeric names are rejected at creation time, there is no ambiguity: an integer
  argument always means an index.

### `src/yaam/session.py`

- Add a `get_by_index(index: int) -> AgentSession | None` method to `SessionStore`.
  - Returns the session at position `index` in the ordered list (0-based, insertion order).
  - Returns `None` if the index is out of range (negative or >= length).

### `tests/test_session.py`

- Add tests for `SessionStore.get_by_index`:
  - Returns `None` on an empty store.
  - Returns the correct session for a valid index.
  - Returns `None` for an out-of-range index (negative or >= length).

### `tests/test_cli.py`

- Add tests for the `new` command name validation:
  - `yaam new 0 --profile x` fails with exit code 1 and prints the numeric-name error.
  - `yaam new 42 --profile x` fails the same way.
  - `yaam new feature-0 --profile x` is accepted (regression).
- Add tests for `yaam list` output including the `#` column.
- Add tests for `yaam attach <index>`:
  - Attaches to the correct session by index.
  - Prints an error and exits 1 when the index is out of range.
  - Still works with a name (regression).

---

## Acceptance criteria

- `yaam new 5 --profile x` exits 1 with a clear error message explaining the restriction.
- `yaam list` renders a `#` column as the leftmost column showing `0`, `1`, `2`, … for each row.
- `yaam attach 0` attaches to the first session in the list.
- `yaam attach <name>` continues to work exactly as before.
- `yaam attach 99` (out of range) prints a clear error and exits with code 1.
- All existing tests pass.
- `ruff check` and `ruff format --check` pass.
