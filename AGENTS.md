# AGENTS.md

> **This file must always reflect the current state of the repository.**
> When adding features, fixing bugs, or making any structural changes, update this file as part of the same change.

## Issue Tracking

This project uses **Beads** (`bd`) for issue tracking. Issues live in `.beads/issues.jsonl` and are managed entirely via the CLI.

Run `bd onboard` to get oriented.

### Common Commands

```bash
bd ready                              # Find available work
bd list                               # View all issues
bd show <id>                          # View issue details
bd create "Description of the issue"  # Create a new issue
bd update <id> --status in_progress   # Claim work
bd update <id> --status done          # Mark work done
bd close <id>                         # Close an issue
bd sync                               # Sync with git
```

See `.beads/README.md` for full documentation.

## Maintaining AGENTS.md

**This is a critical rule.** Every change to the repository that adds, removes, or modifies features, fixes, or project structure **must** include an update to this file. AGENTS.md is the source of truth for what exists in this repo and how it works.

When making changes:

1. Update the relevant section below to reflect the new state
2. Add new sections if introducing entirely new concepts
3. Remove sections for deleted functionality
4. Keep descriptions concise and accurate

## Project Overview

**yaam (Yet Another Agent Manager)** — A Python CLI tool that manages tmux sessions and git worktrees (via Worktrunk), with a path to multi-agent orchestration via LangGraph. It is **distributed as a clone-and-install** project (see README): install from the repository root with `uv tool install .` or `pip install .`, not from PyPI.

### Architecture

The core model is **one feature → one session → one worktree → one agent**:

- Each `yaam new` creates a **dedicated tmux session** named after the agent (slashes replaced with dashes) and a **git worktree** on the corresponding branch
- Sessions are fully isolated — no shared tmux session between agents
- `yaam kill` tears down the tmux session, removes the worktree, and clears the state entry

Agent sessions are driven by **profiles** — named configurations that bundle a base repository, a tmux layout script, and a post-init script. The tmux setup script receives the agent's session name as `$1` and the worktree path as `$2`, and is free to build whatever layout it needs. yaam does not create any windows or panes itself.

## Repository Structure

```
src/
  yaam/
    __init__.py       # Package root
    cli.py            # typer app entry point
    config.py         # user config model
    profile.py        # AgentProfile model + loader
    session.py        # AgentSession model + state file
    tmux.py           # libtmux wrapper
    worktrunk.py      # wt subprocess wrapper
    profiles/         # bundled profile templates
docs/
  specs/
    01-init.md        # Full implementation plan (9 stages)
    02-rename-to-yaam.md  # Rename package/executable to yaam
    03-init-before-tmux.md    # Run init script before tmux setup
    04-tmux-script-session-arg.md  # Pass session name as $1 to tmux setup script
    05-session-name-as-branch.md  # Session name is the branch name; default_branch_prefix removed
    08-worktrunk-hidden-worktree-dirs.md  # yaam overrides WORKTRUNK_WORKTREE_PATH to use .worktrunk- prefix
.agents/
  skills/
    feature-spec/     # Skill: how to spec and register a new feature
    create-profile/   # Skill: how to create a profile configuration
.beads/               # Beads issue tracking data
  README.md           # Beads usage documentation
  issues.jsonl        # Issue database
AGENTS.md             # This file — repo state and agent instructions
pyproject.toml        # Project config, dependencies, ruff, entry points
```

## Implementation Plan

The full implementation plan is in `docs/specs/01-init.md`. Additional specs live in `docs/specs/`.

| Stage | Name                    | Status   | Spec                                   | Description                                                                                     |
| ----- | ----------------------- | -------- | -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1     | Project scaffold        | **Done** | `01-init.md`                           | CLI skeleton with `typer`, `rich`, `pydantic`, `libtmux`                                        |
| 2     | Worktrunk wrapper       | **Done** | `01-init.md`                           | Python wrapper around `wt` CLI commands                                                         |
| 3     | Profile system          | **Done** | `01-init.md`                           | Named profile configs for agent roles                                                           |
| 4     | tmux wrapper            | **Done** | `01-init.md`                           | `libtmux` wrapper for managing panes                                                            |
| 5     | Session state           | **Done** | `01-init.md`                           | Persistent session store (`sessions.json`)                                                      |
| 6     | Core commands           | **Done** | `01-init.md`                           | `yaam new`, `yaam list`, `yaam kill`                                                            |
| 7     | Attach and sync         | **Done** | `01-init.md`                           | `yaam attach`, `yaam sync`                                                                      |
| 8     | LangGraph orchestrator  | **Done** | `01-init.md`                           | Multi-agent supervisor with LangGraph                                                           |
| 9     | Polish and packaging    | **Done** | `01-init.md`                           | Shell completions, `yaam doctor`, README, `pyproject` packaging (local install)                 |
| 10    | Rename to yaam          | **Done** | `02-rename-to-yaam.md`                 | Rename package, executable, module, and config paths to `yaam`                                  |
| 11    | tmux script session arg | **Done** | `04-tmux-script-session-arg.md`        | Pass session name as `$1` and worktree path as `$2` to tmux setup scripts                       |
| 12    | Session name as branch  | **Done** | `05-session-name-as-branch.md`         | Branch name equals session name; `default_branch_prefix` removed                                |
| 13    | Hidden worktree dirs    | **Done** | `08-worktrunk-hidden-worktree-dirs.md` | `create()` injects `WORKTRUNK_WORKTREE_PATH` to place worktrees as `.worktrunk-<repo>.<branch>` |
| 14    | One session per agent   | **Done** | —                                      | Each agent gets its own tmux session; `tmux_session_name` config removed; `kill` tears down the session |

## Dependencies

| Package               | Purpose                  |
| --------------------- | ------------------------ |
| `typer`               | CLI interface            |
| `rich`                | Terminal output          |
| `pydantic`            | Data models              |
| `libtmux`             | tmux control             |
| `filelock`            | Safe state writes        |
| `tomllib` / `tomli`   | Config + profile parsing |
| `langgraph`           | Agent graph (Stage 8)    |
| `langchain-anthropic` | Claude model (Stage 8)   |

**External tools required:** `wt` (Worktrunk), `tmux`
**Dev tooling:** `uv` (package manager), `ruff` (linter + formatter)

## Package Structure

```
src/yaam/
├── __init__.py       # package root
├── cli.py            # typer app — new/list/kill/attach/sync/run/doctor commands
├── config.py         # AgentConfig model + load_config() (TOML, sensible defaults)
├── init.py           # post-init script runner (InitScriptError, run())
├── profile.py        # AgentProfile model (no branch prefix), load/list_profiles/validate, _ensure_example_profile
├── session.py        # AgentSession model + SessionStore (filelock, JSON state file)
├── tmux.py           # libtmux wrapper (get_or_create_session, run_setup_script[$1=session,$2=worktree], kill_session, session_alive)
├── worktrunk.py      # wt subprocess wrapper (WorktreeInfo, WorktrunkError; list via ``wt list --format=json``; sets WORKTRUNK_WORKTREE_PATH=".worktrunk-<repo>.<branch>" on create)
├── profiles/
│   └── example.toml  # bundled example profile written to ~/.config/yaam/profiles/ on first run
└── orchestrator/
    ├── __init__.py   # package root
    ├── models.py     # Task, TaskResult, OrchestratorState TypedDicts
    ├── graph.py      # LangGraph graph (plan/dispatch/monitor/collect/review nodes)
    └── worker.py     # worker entry point — runs task, writes results/<name>.json
tests/
├── test_worktrunk.py    # 19 tests with subprocess mocking
├── test_profile.py      # 17 tests for profile load/list/validate/example
├── test_tmux.py         # 17 tests for libtmux wrapper (fully mocked)
├── test_session.py      # 21 tests for AgentSession, SessionStore, AgentConfig
├── test_init.py         # 7 tests for init script runner
├── test_cli.py          # 25 tests for CLI commands via CliRunner (incl. doctor)
└── test_orchestrator.py # 19 tests for models, worker, graph nodes, and agent run command
README.md             # Clone-and-install, quickstart, profile authoring guide, commands reference
```

Profiles live at `~/.config/yaam/profiles/<name>.toml`.
Session state lives at `~/.config/yaam/sessions.json`.

## Agent Skills

Reusable agent instructions live in `.agents/skills/`. Each skill is a directory containing a
`SKILL.md` with YAML frontmatter (`name`, `description`) and markdown instructions.

| Skill            | Description                                                                                                                                                                         |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `feature-spec`   | How to spec and register a new feature (check docs → write spec → review → create Beads issues → sync)                                                                              |
| `create-profile` | How to create a profile TOML, write tmux/init scripts, validate, and troubleshoot. Use this skill (invoke with `/create-profile`) when creating or configuring a new agent profile. |

When adding a new skill, create `.agents/skills/<name>/SKILL.md` and add a row to this table.

## Session Completion Workflow

When ending a work session, complete ALL steps:

1. **File issues** for remaining work (`bd create "..."`)
2. **Run quality gates** if code changed (tests, `ruff check`, `ruff format --check`)
3. **Update issue status** — close finished work, update in-progress items
4. **Push to remote** — this is mandatory:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # Must show "up to date with origin"
   ```
5. **Verify** all changes are committed and pushed
6. **Hand off** context for the next session
