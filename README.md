# agent-cli

A Python CLI tool that manages **tmux sessions** and **git worktrees** (via [Worktrunk](https://github.com/grahamdaw/worktrunk)) for multi-agent software engineering workflows, with built-in multi-agent orchestration via [LangGraph](https://github.com/langchain-ai/langgraph).

## Features

- Spawn isolated agent sessions — each gets its own git worktree and tmux pane
- Profile-driven setup — bundle repo, tmux layout, and init script into a named config
- Persistent session state — sessions survive shell restarts
- Multi-agent orchestration — `agent run` dispatches a swarm of workers via LangGraph
- Shell completions for zsh and bash

## Requirements

- Python 3.12+
- [tmux](https://github.com/tmux/tmux)
- [Worktrunk (`wt`)](https://github.com/grahamdaw/worktrunk) — git worktree manager

Check all requirements are met:

```bash
agent doctor
```

## Installation

```bash
pip install agent-cli
# or with uv:
uv tool install agent-cli
```

Install shell completions (one-time):

```bash
agent --install-completion
```

## Quickstart

### 1. Create a profile

Profiles live at `~/.config/agent/profiles/<name>.toml`. Run `agent profile list` to generate an example profile on first run, then edit it:

```toml
[profile]
name = "backend"
description = "Backend API agent"

[repo]
path = "~/projects/api"
default_branch_prefix = "agent/"

[tmux]
setup_script = "~/.config/agent/scripts/backend-tmux.sh"

[init]
script = "~/.config/agent/scripts/backend-init.sh"
env = { NODE_ENV = "development" }
```

Validate the profile:

```bash
agent profile validate backend
```

### 2. Spawn an agent session

```bash
agent new my-feature --profile backend
```

This will:
1. Create a git worktree on branch `agent/my-feature`
2. Run your tmux setup script to build the layout
3. Run your init script (install deps, copy `.env`, etc.)
4. Save session state

### 3. Manage sessions

```bash
agent list              # view all sessions
agent list --json       # JSON output for scripting
agent attach my-feature # switch into the agent's tmux pane
agent sync              # detect orphaned sessions
agent sync --fix        # remove orphaned sessions from store
agent kill my-feature   # kill pane, remove worktree, clear state
```

### 4. Multi-agent orchestration

```bash
agent run "add a health check endpoint" --profile backend
```

The supervisor (Claude claude-haiku-4-5-20251001) breaks the goal into tasks, spawns worker agents,
monitors progress, collects results, and reviews completion automatically.

## Profile authoring guide

A profile bundles three things:

| Field | Description |
|---|---|
| `repo.path` | Absolute path to the base git repo Worktrunk operates in |
| `tmux.setup_script` | Script that builds your tmux layout; receives the worktree path as `$1` |
| `init.script` | Post-setup script; receives `repo_path $1` and `worktree_path $2` |

The `init.script` is responsible for anything needed to make the worktree ready to work in:
copying `.env` files, installing dependencies, starting background processes, etc.

Full output from both scripts is logged to `~/.config/agent/logs/<name>-init.log`.

## Worktrunk setup

`wt` is the git worktree manager that `agent` uses under the hood. Install it and ensure it is on your `PATH`:

```bash
brew install grahamdaw/tap/worktrunk  # or follow the upstream install instructions
wt --help
```

## Commands reference

| Command | Description |
|---|---|
| `agent new <name> --profile <p>` | Spawn a new agent session |
| `agent list [--json]` | List active sessions |
| `agent attach <name>` | Attach to an existing session |
| `agent kill <name>` | Kill a session and clean up |
| `agent sync [--fix]` | Detect and optionally remove orphaned sessions |
| `agent run <goal>` | Run multi-agent orchestration |
| `agent doctor` | Check environment health |
| `agent profile list` | List available profiles |
| `agent profile validate <name>` | Validate a profile |
| `agent --install-completion` | Install shell completions |

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```
