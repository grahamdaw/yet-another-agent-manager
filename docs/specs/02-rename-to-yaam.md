# Rename to `yaam`

**Goal:** Rename the package, executable, Python module, and all config paths from `agent`/`agent-cli` to `yaam`.

---

## Scope of changes

### 1. `pyproject.toml`

| Field | Before | After |
|---|---|---|
| `[project] name` | `"agent-cli"` | `"yaam"` |
| `[project.scripts]` entry | `agent = "agent.cli:app"` | `yaam = "yaam.cli:app"` |
| `[project.scripts]` worker | `agent-worker = "agent.orchestrator.worker:main"` | `yaam-worker = "yaam.orchestrator.worker:main"` |
| `[tool.hatch.build.targets.wheel] packages` | `["src/agent"]` | `["src/yaam"]` |
| `[tool.ruff.lint.isort] known-first-party` | `["agent"]` | `["yaam"]` |

### 2. Source package

- Rename `src/agent/` → `src/yaam/`
- Update all internal imports: `from agent.` → `from yaam.`, `import agent.` → `import yaam.`

### 3. Config and state paths

All runtime paths change from `~/.config/agent/` to `~/.config/yaam/`:

| Path | Before | After |
|---|---|---|
| Config dir | `~/.config/agent/` | `~/.config/yaam/` |
| Profiles dir | `~/.config/agent/profiles/` | `~/.config/yaam/profiles/` |
| Session state | `~/.config/agent/sessions.json` | `~/.config/yaam/sessions.json` |
| Logs | `~/.config/agent/logs/` | `~/.config/yaam/logs/` |
| Config file | `~/.config/agent/config.toml` | `~/.config/yaam/config.toml` |

This means updating the hardcoded path constants in `config.py`, `session.py`, `profile.py`, and `init.py`.

### 4. CLI commands

All `agent <subcommand>` invocations become `yaam <subcommand>`. No subcommand names change — only the top-level binary name.

### 5. Tests

- Update all imports: `from agent.` → `from yaam.`
- Update all CLI runner invocations if the app name is referenced
- Update any path assertions that reference `~/.config/agent/`

### 6. `README.md`

- Title and package name: `agent-cli` → `yaam`
- Installation: `pip install yaam` / `uv tool install yaam`
- All shell examples: `agent <cmd>` → `yaam <cmd>`
- Config path references updated
- Worktrunk section: `wt` reference to `yaam` updated

### 7. `AGENTS.md`

- Project overview and description updated
- Repository structure: `src/agent/` → `src/yaam/`, `agent.cli:app` → `yaam.cli:app`
- All `agent <cmd>` examples in commands table updated
- Config paths updated: `~/.config/agent/` → `~/.config/yaam/`

### 8. `docs/specs/01-init.md`

- All `agent <cmd>` command examples updated to `yaam <cmd>`
- Package/module name references updated

---

## Acceptance criteria

- `yaam --help` prints the command list with no errors
- `yaam doctor` passes (all health checks green)
- All tests pass with no import errors
- `ruff check` and `ruff format --check` pass
- `pip install .` produces a `yaam` binary and a `yaam-worker` binary, not `agent` or `agent-worker`
- No remaining references to the old `agent` binary name or `agent-cli` package name in source, docs, or config (grep clean)
- Config is read from `~/.config/yaam/` on a fresh run

---

## Migration note

Existing users with data at `~/.config/agent/` will need to manually move their config and state:

```bash
mv ~/.config/agent ~/.config/yaam
```

No automatic migration is in scope for this change.
