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

**Yet Another Agent Manager** — A Python CLI tool that manages tmux sessions and git worktrees (via Worktrunk), with a path to multi-agent orchestration via LangGraph.

Agent sessions are driven by **profiles** — named configurations that bundle a base repository, a tmux layout script, and a post-init script. Spawning an agent with a profile fully automates the environment setup for that agent role.

## Repository Structure

```
src/
  agent/
    __init__.py       # Package root
    cli.py            # typer app entry point
    config.py         # user config model (stub)
    profile.py        # AgentProfile model + loader (stub)
    session.py        # AgentSession model + state file (stub)
    tmux.py           # libtmux wrapper (stub)
    worktrunk.py      # wt subprocess wrapper (stub)
    profiles/         # bundled profile templates
docs/
  specs/
    01-init.md        # Full implementation plan (9 stages)
.beads/               # Beads issue tracking data
  README.md           # Beads usage documentation
  issues.jsonl        # Issue database
AGENTS.md             # This file — repo state and agent instructions
pyproject.toml        # Project config, dependencies, ruff, entry points
```

## Implementation Plan

The full implementation plan is in `docs/specs/01-init.md`. It defines 9 stages:

| Stage | Name                  | Status  | Description                                              |
|-------|-----------------------|---------|----------------------------------------------------------|
| 1     | Project scaffold      | **Done**| CLI skeleton with `typer`, `rich`, `pydantic`, `libtmux` |
| 2     | Worktrunk wrapper     | **Done**| Python wrapper around `wt` CLI commands                  |
| 3     | Profile system        | **Done**| Named profile configs for agent roles                    |
| 4     | tmux wrapper          | **Done**| `libtmux` wrapper for managing panes                     |
| 5     | Session state         | **Done**| Persistent session store (`sessions.json`)               |
| 6     | Core commands         | Pending | `agent new`, `agent list`, `agent kill`                  |
| 7     | Attach and sync       | Pending | `agent attach`, `agent sync`                             |
| 8     | LangGraph orchestrator| Pending | Multi-agent supervisor with LangGraph                    |
| 9     | Polish and packaging  | Pending | Shell completions, `agent doctor`, PyPI packaging        |

## Dependencies

| Package               | Purpose                  |
|-----------------------|--------------------------|
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
src/agent/
├── __init__.py     # package root
├── cli.py          # typer app entry point (stub commands wired up)
├── config.py       # user config model (stub)
├── profile.py      # AgentProfile model + loader (stub)
├── session.py      # AgentSession model + state file (stub)
├── tmux.py         # libtmux wrapper (stub)
├── worktrunk.py    # wt subprocess wrapper (WorktreeInfo, WorktrunkError, create/remove/list/merge)
├── profile.py      # AgentProfile model, load/list_profiles/validate, _ensure_example_profile
├── tmux.py         # libtmux wrapper (PaneRef, get_or_create_session, run_setup_script, create/send/kill/alive)
├── session.py      # AgentSession model + SessionStore (filelock, JSON state file)
├── config.py       # AgentConfig model + load_config() (TOML, sensible defaults)
├── init.py         # post-init script runner (not yet created)
└── profiles/
    └── example.toml  # bundled example profile written to ~/.config/agent/profiles/ on first run
tests/
├── test_worktrunk.py  # 19 tests with subprocess mocking
├── test_profile.py    # 17 tests for profile load/list/validate/example
├── test_tmux.py       # 17 tests for libtmux wrapper (fully mocked)
└── test_session.py    # 21 tests for AgentSession, SessionStore, AgentConfig
```

Profiles live at `~/.config/agent/profiles/<name>.toml`.
Session state lives at `~/.config/agent/sessions.json`.

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
