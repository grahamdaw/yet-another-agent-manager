# Architecture cleanup — orchestrator and session state

**Goal:** Address four structural issues identified in a codebase review that reduce testability,
reliability, and correctness of the orchestrator and session state subsystems. This spec captures
the scope for refinement; each item should be broken into its own numbered spec before implementation.

---

## Items

### A — Extract a Python API for agent spawning

**Problem:** `orchestrator/graph.py` `dispatch_node` spawns agents by calling `yaam new` as a
subprocess. This creates a circular dependency (the tool calling itself), makes the orchestrator
untestable without a full environment, and passes task data via `os.environ`.

**Intended outcome:** A `spawn_agent(name, profile, task)` Python function that both `cli.py` and
`dispatch_node` call directly. The subprocess self-invocation is eliminated.

**Files likely affected:** `src/yaam/orchestrator/graph.py`, `src/yaam/cli.py`

---

### B — Replace file-polling completion with a proper protocol

**Problem:** `monitor_node` polls for result file existence every 5 seconds with a hard 60-poll
(5-minute) timeout. A partially-written file looks like success; a dead pane also looks like
success; there is no progress reporting during execution.

**Intended outcome:** Result file writes are atomic (write to temp path, then rename). The monitor
distinguishes between normal completion and process crash. The polling interval and timeout are
configurable rather than hardcoded module-level constants.

**Files likely affected:** `src/yaam/orchestrator/graph.py`, `src/yaam/orchestrator/worker.py`

---

### C — Wire up the error propagation model

**Problem:** `OrchestratorState.error` is defined in `models.py` but never set or checked. Node
failures raise unhandled exceptions that crash the graph rather than flowing through state. The
CLI's catch-all `except Exception` in `cli.py:122–130` may leave resources (worktrees, panes)
uncleaned if multiple steps fail.

**Intended outcome:** Graph nodes set `state["error"]` on failure. The `review_node` or a new
`error_node` handles structured error state. The CLI cleanup block is ordered to guarantee
resource teardown regardless of which step failed.

**Files likely affected:** `src/yaam/orchestrator/graph.py`, `src/yaam/orchestrator/models.py`,
`src/yaam/cli.py`

---

### D — Atomicize session state writes and remove vestigial `status` field

**Problem:** `SessionStore._write()` calls `write_text()` directly — a crash during the write
corrupts `sessions.json` with no recovery path. `AgentSession.status` defaults to `"running"` and
has an `update_status()` method but is never updated during the session lifecycle; `list` already
bypasses it by calling `pane_alive()` directly.

**Intended outcome:** `_write()` uses a write-to-temp-then-rename pattern for atomic updates.
Either `status` is wired into the actual session lifecycle (set to `"dead"` on kill, checked in
`list`) or the field and `update_status()` are removed.

**Files likely affected:** `src/yaam/session.py`, `src/yaam/cli.py`, `tests/test_session.py`

---

## Next steps

Each item above should become its own spec (`13-...`, `14-...`, etc.) when it is ready for
implementation. The items are independent and can be sequenced in any order.
