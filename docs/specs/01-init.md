# Agent CLI — Implementation Plan

A staged plan for building a Python CLI tool that manages tmux sessions and git worktrees (via Worktrunk), with a path to multi-agent orchestration via LangGraph.

Agent sessions are driven by **profiles** — named configurations that bundle together a base repository, a tmux layout script, and a post-init script. Spawning an agent with a profile fully automates the environment setup for that agent role.

---

## Stage 1 — Project scaffold

**Goal:** Runnable CLI with no real functionality yet. Just the skeleton.

### Tasks

- Initialise project with `pyproject.toml` using `uv init`
- Add dependencies via `uv add`: `typer`, `rich`, `pydantic`, `libtmux`
- Create package structure:
  ```
  agent/
  ├── cli.py          # typer app entry point
  ├── config.py       # user config model
  ├── profile.py      # AgentProfile model + loader (stub)
  ├── session.py      # AgentSession model + state file
  ├── tmux.py         # libtmux wrapper (stub)
  └── worktrunk.py    # wt subprocess wrapper (stub)
  ```
- Ensure the bundled `profiles/` directory is included in package data (configure `pyproject.toml` `[tool.hatch.build.targets.wheel] include` or equivalent)
- Configure `ruff` in `pyproject.toml`: linting (`ruff check`) and formatting (`ruff format`) replacing both `flake8` and `black`
- Register `agent` as a CLI entry point
- Confirm `agent --help` runs cleanly

### Acceptance criteria

- `agent --help` prints a command list with no errors
- All modules import without error
- `pyproject.toml` pins all direct dependencies
- `ruff check` and `ruff format --check` pass on the empty scaffold

---

## Stage 2 — Worktrunk wrapper

**Goal:** Python wrapper around `wt` CLI commands, with structured return types.

### Tasks

- Implement `worktrunk.py`:
  - `create(branch: str, repo_path: str) -> WorktreeInfo` — calls `wt switch --create <branch>` from `repo_path`
  - `remove(worktree_path: str) -> None` — calls `wt remove` from the worktree path
  - `list(repo_path: str) -> list[WorktreeInfo]` — calls `wt list` and parses output
  - `merge(worktree_path: str, target: str = "main") -> None` — calls `wt merge <target>`
- Define `WorktreeInfo` Pydantic model: `branch`, `path`, `status`, `head`
- Handle subprocess errors and surface them as typed exceptions
- Add a `wt_available() -> bool` check on startup

### Acceptance criteria

- `worktrunk.create("test-branch", repo_path="~/projects/api")` creates a real worktree and returns a populated `WorktreeInfo`
- `worktrunk.list()` returns one entry per active worktree
- Calling any command when `wt` is not installed raises a clear `WorktrunkNotFoundError`
- All commands are covered by unit tests using subprocess mocking

---

## Stage 3 — Profile system

**Goal:** A named profile config that fully describes an agent role — its repo, tmux layout, and init sequence.

### Profile format

Profiles live at `~/.config/agent/profiles/<name>.toml`. Example:

```toml
[profile]
name = "backend"
description = "Backend API agent — NestJS monorepo"

[repo]
path = "~/projects/api"           # base repo for wt to operate in
default_branch_prefix = "agent/"  # e.g. agent/fix-auth-123

[tmux]
setup_script = "~/.config/agent/scripts/backend-tmux.sh"
# your existing tmux layout script; called with the worktree path as $1

[init]
script = "~/.config/agent/scripts/backend-init.sh"
# called once after tmux setup; receives worktree path as $1
# responsible for: copying .env files, running npm install, starting dev server, etc.
env = { NODE_ENV = "development" }  # extra env vars injected into the init script
```

### Tasks

- Implement `profile.py`:
  - `AgentProfile` Pydantic model: `name`, `description`, `repo_path`, `default_branch_prefix`, `tmux_setup_script`, `init_script`, `init_env`
  - `load(name: str) -> AgentProfile` — reads `~/.config/agent/profiles/<name>.toml`
  - `list_profiles() -> list[AgentProfile]` — lists all available profiles
  - `validate(profile: AgentProfile) -> list[str]` — checks scripts exist and are executable, repo path exists
- Add `agent profile list` subcommand — renders a `rich` table of available profiles with description
- Add `agent profile validate <name>` — runs `validate()` and reports issues
- Write an `example.toml` profile to `~/.config/agent/profiles/` on first run

### Acceptance criteria

- `agent profile list` shows all `.toml` files in the profiles directory
- `agent profile validate backend` reports missing scripts or bad repo path clearly
- `AgentProfile` fails fast on load if required fields are missing (Pydantic validation)
- A profile with a non-executable script path raises a clear `ProfileValidationError`

---

## Stage 4 — tmux wrapper

**Goal:** Python wrapper around `libtmux` for managing panes tied to agent sessions, including execution of profile-defined layout scripts.

### Tasks

- Implement `tmux.py`:
  - `get_or_create_session(name: str) -> libtmux.Session`
  - `run_setup_script(script_path: str, worktree_path: str) -> None` — calls the profile's tmux setup script with `worktree_path` as `$1`; captures stderr and raises on non-zero exit
  - `create_pane(session_name: str, window_name: str) -> PaneRef`
  - `send_keys(pane_ref: PaneRef, cmd: str) -> None`
  - `kill_pane(pane_ref: PaneRef) -> None`
  - `pane_alive(pane_ref: PaneRef) -> bool`
- Define `PaneRef` dataclass: `session_id`, `window_id`, `pane_id`
- Handle the case where tmux is not running (start a server or raise clearly)
- Capture tmux setup script output in a log file per session for debugging

### Acceptance criteria

- A pane can be created, written to, and killed without error
- `run_setup_script` raises `TmuxScriptError` with captured stderr on failure
- `pane_alive` returns `False` after kill
- All operations are idempotent (calling twice does not raise)

---

## Stage 5 — Session state

**Goal:** Persistent mapping between agent names, worktrees, tmux panes, and the profile used to create them.

### Tasks

- Implement `session.py`:
  - `AgentSession` Pydantic model: `name`, `branch`, `profile_name`, `worktree_path`, `tmux_session`, `tmux_pane_ref`, `created_at`, `status`
  - `SessionStore`: read/write JSON state file at `~/.config/agent/sessions.json`
    - `add(session: AgentSession) -> None`
    - `get(name: str) -> AgentSession | None`
    - `list() -> list[AgentSession]`
    - `remove(name: str) -> None`
    - `update_status(name: str, status: str) -> None`
- Implement `config.py`:
  - `AgentConfig` model: `default_profile`, `tmux_session_name`, `state_file_path`
  - Load from `~/.config/agent/config.toml` with sensible defaults

### Acceptance criteria

- Sessions survive process restart (written to disk, read back correctly)
- `get` returns `None` for unknown names (no exception)
- Concurrent writes do not corrupt state (use a file lock)
- `profile_name` is stored and round-trips correctly

---

## Stage 6 — Core commands

**Goal:** `agent new`, `agent list`, and `agent kill` working end to end, profile-driven.

### Spawn sequence

When `agent new <name> --profile <profile>` is called, the following steps run in order:

1. Load and validate the profile
2. `worktrunk.create(branch, repo_path=profile.repo_path)` — create worktree in the profile's base repo
3. `tmux.run_setup_script(profile.tmux_setup_script, worktree_path)` — run layout script with worktree path as `$1`
4. `init.run(profile.init_script, worktree_path, env=profile.init_env)` — run post-init script (copy env files, install deps, etc.)
5. Persist `AgentSession` to store

### Tasks

- `agent new <name> --profile <profile> [--branch <branch>]`
  - Runs the full spawn sequence above
  - `--branch` overrides the auto-generated branch name (default: `profile.default_branch_prefix + name`)
  - Streams init script output to the terminal with a `rich` spinner
- Implement `init.py`:
  - `run(script_path: str, repo_path: str, worktree_path: str, env: dict) -> None`
  - Calls the init script with `repo_path` as `$1` and `worktree_path` as `$2`
  - Merges `profile.init_env` with the current environment
  - Streams stdout/stderr; raises `InitScriptError` on non-zero exit
  - Logs full output to `~/.config/agent/logs/<name>-init.log`
- `agent list`
  - Reads session store, cross-references with `wt list` and `tmux.pane_alive`
  - Renders a `rich` table: name, profile, branch, status, age, pane
- `agent kill <name>`
  - Kills tmux pane, runs `wt remove` on the worktree, removes session from store

### Acceptance criteria

- Full round-trip: `agent new foo --profile backend` → tmux layout appears → init script runs → `agent list` shows it → `agent kill foo` removes it
- Init script failure surfaces the log path and exits cleanly — worktree and tmux pane are cleaned up on failure
- `agent list` includes the profile name column
- `agent kill` on an unknown name prints a helpful error, does not crash

---

## Stage 7 — Attach and sync

**Goal:** `agent attach` and `agent sync` for day-to-day use.

### Tasks

- `agent attach <name>`
  - Switches the current terminal to the named tmux pane
  - Prints an error if the pane is dead
- `agent sync`
  - Finds orphaned sessions: in store but pane dead and/or worktree gone
  - Finds untracked worktrees: `wt list` returns entries not in store
  - Reports discrepancies with a `rich` table
  - `--fix` flag to auto-remove orphaned sessions from store

### Acceptance criteria

- `agent attach foo` puts the user inside the correct pane
- `agent sync` detects a manually removed worktree as orphaned
- `agent sync --fix` clears orphaned sessions without touching live ones

---

## Stage 8 — LangGraph orchestrator (multi-agent)

**Goal:** A supervisor that dispatches tasks to worker agents, each spawned via a named profile.

### Tasks

- Add dependency: `langgraph`, `langchain-anthropic`
- Extend state to include profile assignment per task:

  ```python
  class Task(TypedDict):
      id: str
      description: str
      profile: str        # which profile to spawn for this task

  class OrchestratorState(TypedDict):
      tasks: list[Task]
      agents: list[AgentSession]
      results: list[TaskResult]
      phase: Literal["planning", "executing", "reviewing", "done"]
  ```

- Implement `orchestrator/graph.py`:
  - `plan_node` — supervisor breaks a goal into tasks, assigns a profile to each
  - `dispatch_node` — calls `agent new --profile <task.profile>` for each task
  - `monitor_node` — polls pane status and result files
  - `collect_node` — reads results from `results/<name>.json` per agent
  - `review_node` — supervisor reviews collected results, decides next step
- Implement `orchestrator/worker.py` — thin wrapper each agent process runs; writes result to `results/<name>.json` on completion
- Add `agent run <goal> [--profile <profile>]` CLI command — entry point into the graph

### Acceptance criteria

- `agent run "add a health check endpoint" --profile backend` spawns at least one worker in its own worktree with the correct tmux layout and init sequence
- Supervisor collects results after worker completes
- Graph reaches `done` phase without manual intervention for a simple single-task goal
- Failure in one worker does not crash the supervisor

---

## Stage 9 — Polish and packaging

**Goal:** Distributable, documented tool ready for daily use.

### Tasks

- Add `--json` output flag to `agent list` for scripting
- Add shell completions via `typer` (`agent --install-completion`)
- Write a `README.md` with installation, quickstart, profile authoring guide, and Worktrunk setup instructions
- Add `agent doctor` command: checks `wt` installed, tmux running, config valid, at least one profile valid
- Publish to PyPI or package as a standalone binary via `pyinstaller`

### Acceptance criteria

- `agent doctor` passes on a clean machine with `wt`, tmux, and one valid profile
- Shell completions work in zsh and bash
- `pip install agent-cli` (or equivalent) produces a working `agent` binary

---

## Dependency summary

| Package               | Purpose                  | Stage introduced |
| --------------------- | ------------------------ | ---------------- |
| `typer`               | CLI interface            | 1                |
| `rich`                | Terminal output          | 1                |
| `pydantic`            | Data models              | 1                |
| `libtmux`             | tmux control             | 4                |
| `filelock`            | Safe state writes        | 5                |
| `tomllib` / `tomli`   | Config + profile parsing | 3                |
| `langgraph`           | Agent graph              | 8                |
| `langchain-anthropic` | Claude model             | 8                |

External tools required: `wt` (Worktrunk), `tmux`

Dev tooling: `uv` (package manager + virtualenv), `ruff` (linter + formatter — replaces `flake8`, `isort`, and `black`)
