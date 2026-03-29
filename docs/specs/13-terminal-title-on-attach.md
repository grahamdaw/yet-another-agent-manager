# Terminal window title on `yaam attach`

**Goal:** Update the OS-level terminal emulator window title when a user attaches to a yaam
session, and reset it when they detach.

---

## Problem

When `yaam attach <session>` is called, the terminal emulator's title bar (e.g. in iTerm2 or
Terminal.app) stays unchanged. This makes it hard to tell at a glance which yaam session is
currently active, especially when juggling multiple agent sessions.

---

## Intended outcome

- Running `yaam attach <session>` sets the terminal window title to `yaam: <session-name>`.
- When the user detaches from the tmux session (via `Ctrl-B d` or similar), the title resets
  to an empty string, causing most terminal emulators to restore their default title behaviour
  (e.g. the current working directory).
- No change is made to any other `yaam` commands.

---

## Implementation

### Helper function

Add a small private helper to `src/yaam/cli.py`:

```python
def _set_terminal_title(title: str) -> None:
    """Write an OSC 2 escape sequence to update the terminal window title."""
    import sys
    sys.stdout.write(f"\033]2;{title}\007")
    sys.stdout.flush()
```

OSC 2 (`\033]2;...\007`) is the standard escape sequence for setting the terminal window title
and is supported by all major terminal emulators.

### Update `attach` in `src/yaam/cli.py`

Two cases exist:

**Not inside tmux** (`TMUX` env var unset):
`tmux attach-session` blocks until the user detaches — set the title before and reset after.

**Already inside tmux** (`TMUX` set):
`tmux switch-client` returns immediately. Set the title before switching; no reset is
needed because switching back to the prior session restores that session's context.

```python
if os.environ.get("TMUX"):
    _set_terminal_title(f"yaam: {session.name}")
    subprocess.run(["tmux", "switch-client", "-t", session.tmux_session], check=False)
else:
    _set_terminal_title(f"yaam: {session.name}")
    subprocess.run(["tmux", "attach-session", "-t", session.tmux_session], check=False)
    _set_terminal_title("")  # reset on detach
```

---

## Files affected

- `src/yaam/cli.py` — add `_set_terminal_title` helper; update `attach` command body

---

## Out of scope

- **Tmux status-bar window name:** already set correctly — `create_pane` is called with
  `sanitize_name(name)` as the window name, so the tmux status bar already shows the session
  name.
- **Shell-level dynamic title updates** while the session is running (would require injecting
  into `PROMPT_COMMAND` / `precmd` hooks — a much larger change, deferred).
- **`yaam new`:** no interactive terminal is available at spawn time; the user is watching
  the progress spinner, not an attached shell.

---

## Verification

1. Create a session: `yaam new test-session -p <profile>`
2. From **outside tmux**: `yaam attach test-session`
   - Confirm the OS window title changes to `yaam: test-session`
   - Detach (`Ctrl-B d`) — confirm the title resets / clears
3. From **inside an existing tmux session**: `yaam attach test-session`
   - Confirm the title updates when switching
   - Switching back to the previous session should restore its context
4. Confirm `yaam list`, `yaam new`, `yaam kill`, and `yaam sync` are unaffected
