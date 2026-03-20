---
name: create-profile
description: >
  How to create a profile configuration for this tool. Use this skill whenever the user wants
  to add a new agent profile, set up a new role (e.g. "backend", "frontend", "docs"), configure
  a tmux layout or init script for an agent, or asks how profiles work. Also use when the user
  says things like "create a profile for X", "set up an agent for Y", or "how do I configure
  a new agent role". Don't wait for explicit "profile" language — if the user is describing a
  new type of agent session they want to spawn, this is the right skill.
---

# Creating a Profile Configuration

Profiles are the central configuration unit in this tool. Each profile defines a named agent
role — its git repo, tmux layout, and init sequence. When you spawn an agent with
`yaam new <name> --profile <profile>`, everything is driven by the profile: which repo to
branch from, how to arrange the terminal, and what to run to make the worktree ready.

A profile is a TOML file at `~/.config/yaam/profiles/<name>.toml`.

---

## Profile TOML format

```toml
[profile]
name = "backend"                              # required; must match the filename
description = "Backend API agent — NestJS"    # optional but recommended

[repo]
path = "~/projects/api"                       # required; base repo wt operates in
default_branch_prefix = "agent/"             # optional; default is "agent/"

[tmux]
setup_script = "~/.config/yaam/scripts/backend-tmux.sh"   # required

[init]
script = "~/.config/yaam/scripts/backend-init.sh"         # required
env = { NODE_ENV = "development" }                          # optional
```

### Fields

| Section | Key | Required | Default | Notes |
|---|---|---|---|---|
| `[profile]` | `name` | yes | — | Must match the `.toml` filename (without extension) |
| `[profile]` | `description` | no | `""` | Shown in `yaam profile list` |
| `[repo]` | `path` | yes | — | Absolute or `~`-prefixed path to the base git repo |
| `[repo]` | `default_branch_prefix` | no | `"agent/"` | Branch names become `<prefix><session-name>` |
| `[tmux]` | `setup_script` | yes | — | Path to the tmux layout script |
| `[init]` | `script` | yes | — | Path to the post-init script |
| `[init]` | `env` | no | `{}` | Extra env vars injected into the init script |

---

## How the scripts are called

Understanding the calling convention matters when writing or debugging scripts.

**tmux setup script** — called immediately after the worktree is created:
```
setup_script <worktree_path>
```
- `$1` = absolute path to the new worktree
- Use this to build your tmux window/pane layout, `cd` into the worktree, open editors, etc.
- stdout and stderr are logged to `~/.config/yaam/logs/<session-name>-setup.log`
- Non-zero exit raises `TmuxScriptError` and halts the spawn

**init script** — called after tmux setup:
```
init_script <repo_path> <worktree_path>
```
- `$1` = absolute path to the base repo
- `$2` = absolute path to the new worktree
- Use this to copy `.env` files, install dependencies, seed databases, start dev servers, etc.
- All env vars from `[init] env` are merged into the subprocess environment
- stdout and stderr are logged to `~/.config/yaam/logs/<session-name>-init.log`
- Non-zero exit raises `InitScriptError` and halts the spawn (worktree and pane are cleaned up)

Both scripts must be **executable** (`chmod +x`). The tool checks this at validation time and
raises an error if a script exists but isn't executable.

---

## Step-by-step: creating a profile

### 1. Create the scripts directory

```bash
mkdir -p ~/.config/yaam/scripts
```

### 2. Write the tmux setup script

```bash
#!/usr/bin/env bash
# ~/.config/yaam/scripts/backend-tmux.sh
set -euo pipefail
WORKTREE="$1"

# Example: one editor pane, one shell pane
tmux rename-window "backend"
tmux send-keys "cd $WORKTREE && nvim ." Enter
tmux split-window -v -p 30
tmux send-keys "cd $WORKTREE" Enter
```

Make it executable:
```bash
chmod +x ~/.config/yaam/scripts/backend-tmux.sh
```

### 3. Write the init script

```bash
#!/usr/bin/env bash
# ~/.config/yaam/scripts/backend-init.sh
set -euo pipefail
REPO_PATH="$1"
WORKTREE="$2"

# Copy shared env file from base repo
cp "$REPO_PATH/.env.local" "$WORKTREE/.env.local"

# Install dependencies
cd "$WORKTREE"
npm install
```

Make it executable:
```bash
chmod +x ~/.config/yaam/scripts/backend-init.sh
```

### 4. Write the profile TOML

```bash
cat > ~/.config/yaam/profiles/backend.toml << 'EOF'
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
EOF
```

### 5. Validate the profile

```bash
yaam profile validate backend
```

This checks:
- `repo.path` exists on disk
- Both scripts exist
- Both scripts are executable

Fix any issues reported before attempting to spawn an agent.

### 6. Verify it appears in the list

```bash
yaam profile list
```

---

## Common patterns

**Monorepo with multiple agent roles** — create one profile per role, each pointing to the same
`repo.path` but with different scripts and branch prefixes:

```
~/.config/yaam/profiles/
├── backend.toml    # default_branch_prefix = "agent/be/"
├── frontend.toml   # default_branch_prefix = "agent/fe/"
└── docs.toml       # default_branch_prefix = "agent/docs/"
```

**Shared init logic** — if multiple profiles share setup steps, extract them into a shared
library script and `source` it from each init script:

```bash
source ~/.config/yaam/scripts/common.sh
```

**No tmux layout needed** — if you just want a plain shell in the worktree, the tmux script
can be minimal:

```bash
#!/usr/bin/env bash
tmux send-keys "cd $1" Enter
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ProfileNotFoundError` | TOML filename doesn't match `name` field, or wrong directory | Ensure filename is `<name>.toml` in `~/.config/yaam/profiles/` |
| `ProfileValidationError: not executable` | Script exists but missing execute bit | `chmod +x <script>` |
| `TmuxScriptError` | tmux setup script exited non-zero | Check `~/.config/yaam/logs/<name>-setup.log` |
| `InitScriptError` | init script exited non-zero | Check `~/.config/yaam/logs/<name>-init.log` |
| Profile silently missing from `yaam profile list` | TOML parse error | Run `yaam profile validate <name>` directly to surface the error |
