# yaam

A Python CLI tool that manages **tmux sessions** and **git worktrees** (via [Worktrunk](https://github.com/grahamdaw/worktrunk)) for multi-agent software engineering workflows, with built-in multi-agent orchestration via [LangGraph](https://github.com/langchain-ai/langgraph).

**Distribution:** yaam is meant to be **cloned and installed from your local checkout**. There is no supported PyPI-first workflow; treat this repo as the source of truth and upgrade by pulling.

## Features

- Spawn isolated agent sessions — each gets its own git worktree and tmux pane
- Profile-driven setup — bundle repo, tmux layout, and init script into a named config
- Persistent session state — sessions survive shell restarts
- Multi-agent orchestration — `yaam run` dispatches a swarm of workers via LangGraph
- Shell completions for zsh and bash

## Requirements

- Python 3.12+
- [tmux](https://github.com/tmux/tmux)
- [Worktrunk (`wt`)](https://github.com/grahamdaw/worktrunk) — git worktree manager

## Installation

Clone the repository, then install from the project root:

```bash
git clone https://github.com/grahamdaw/yet-another-agent-manager.git
cd yet-another-agent-manager
```

**Recommended — isolated tool environment with [uv](https://docs.astral.sh/uv/):**

```bash
uv tool install .
```

This puts `yaam` and `yaam-worker` on your PATH without polluting a global Python environment. Re-run `uv tool install .` after `git pull` to pick up changes.

**Alternative — pip in the current environment:**

```bash
pip install .
# editable, for active development on yaam itself:
pip install -e .
```

**Verify the install:**

```bash
yaam doctor
```

**Shell completions** (one-time):

```bash
yaam --install-completion
```

## Quickstart

### 1. Create a profile

Profiles live at `~/.config/yaam/profiles/<name>.toml`. Run `yaam profile list` to generate an example profile on first run, then edit it:

```toml
[profile]
name = "backend"
description = "Backend API agent"

[repo]
path = "~/projects/api"
default_branch_prefix = "agent/"

[tmux]
setup_script = "~/.config/yaam/scripts/backend-tmux.sh"

[init]
script = "~/.config/yaam/scripts/backend-init.sh"
env = { NODE_ENV = "development" }
```

Validate the profile:

```bash
yaam profile validate backend
```

### 2. Spawn an agent session

```bash
yaam new my-feature --profile backend
```

This will:
1. Create a git worktree on branch `agent/my-feature`
2. Run your init script (install deps, copy `.env`, etc.)
3. Run your tmux setup script to build the layout
4. Save session state

### 3. Manage sessions

```bash
yaam list              # view all sessions
yaam list --json       # JSON output for scripting
yaam attach my-feature # switch into the agent's tmux pane
yaam sync              # detect orphaned sessions
yaam sync --fix        # remove orphaned sessions from store
yaam kill my-feature   # kill pane, remove worktree, clear state
```

### 4. Multi-agent orchestration

```bash
yaam run "add a health check endpoint" --profile backend
```

The supervisor (Claude claude-haiku-4-5-20251001) breaks the goal into tasks, spawns worker agents,
monitors progress, collects results, and reviews completion automatically.

## Profile authoring guide

> **Tip:** If you are using Claude Code, there is a built-in skill to guide you through profile creation. Run `/create-profile` in a Claude Code session and it will walk you through writing the TOML, tmux setup script, and init script step by step.


A profile bundles three things:

| Field | Description |
|---|---|
| `repo.path` | Absolute path to the base git repo Worktrunk operates in |
| `tmux.setup_script` | Script that builds your tmux layout; receives session name as `$1` and worktree path as `$2` |
| `init.script` | Runs after worktree setup, before tmux; receives `repo_path $1` and `worktree_path $2` |

The `init.script` is responsible for anything needed to make the worktree ready to work in:
copying `.env` files, installing dependencies, starting background processes, etc.

Full output from both scripts is logged to `~/.config/yaam/logs/<name>-init.log`.

## Worktrunk setup

`wt` is the git worktree manager that `yaam` uses under the hood. Install it and ensure it is on your `PATH`:

```bash
brew install grahamdaw/tap/worktrunk  # or follow the upstream install instructions
wt --help
```

## Commands reference

| Command | Description |
|---|---|
| `yaam new <name> --profile <p>` | Spawn a new agent session |
| `yaam list [--json]` | List active sessions |
| `yaam attach <name>` | Attach to an existing session |
| `yaam kill <name>` | Kill a session and clean up |
| `yaam sync [--fix]` | Detect and optionally remove orphaned sessions |
| `yaam run <goal>` | Run multi-agent orchestration |
| `yaam doctor` | Check environment health |
| `yaam profile list` | List available profiles |
| `yaam profile validate <name>` | Validate a profile |
| `yaam --install-completion` | Install shell completions |

## Migration from agent-cli

If you have existing data at `~/.config/agent/`, move it manually:

```bash
mv ~/.config/agent ~/.config/yaam
```

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```
