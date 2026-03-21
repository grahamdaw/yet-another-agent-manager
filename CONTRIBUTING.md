# Contributing to yaam

Thanks for taking the time to contribute! yaam is a lean, open project and every
improvement — bug fix, new feature, or doc update — makes it better for everyone
running multi-agent workflows.

## Quick contribution checklist

Before submitting a PR, make sure:

- [ ] Your code passes `uv run pytest` locally
- [ ] You've added tests for new functionality
- [ ] Linting passes: `uv run ruff check src/ tests/`
- [ ] Formatting passes: `uv run ruff format --check src/ tests/`
- [ ] Your commits follow [Conventional Commits](#commit-messages)
- [ ] You've linked the related issue (if applicable)

## Getting started

See the [Development section in README.md](README.md#development) for setup instructions:

```bash
git clone https://github.com/grahamdaw/yet-another-agent-manager.git
cd yet-another-agent-manager
uv sync --group dev
uv run pytest
```

## Finding something to work on

Browse [open issues](https://github.com/grahamdaw/yet-another-agent-manager/issues) —
issues labeled `good first issue` are a great entry point.

Comment on an issue to let others know you're working on it. If you get stuck or
priorities change, no worries — just drop a comment so someone else can pick it up.

For significant changes, open an issue first to align on approach before writing code.

## Development workflow

### Branches

Create a branch from `main`:

- `feat/short-description` — new features
- `fix/short-description` — bug fixes
- `docs/short-description` — documentation only
- `chore/short-description` — maintenance, tooling, refactors

### Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add --dry-run flag to yaam kill
fix: handle missing tmux session gracefully
docs: document profile init script variables
chore: update ruff to 0.15
```

### Pull requests

1. Push your branch and open a PR against `main`
2. Fill in the PR template — describe what changed and why
3. Wait for CI checks to pass
4. A maintainer will review; expect feedback within a few days
5. Once approved, we'll merge

## Code standards

- **Formatter / linter:** [Ruff](https://docs.astral.sh/ruff/) — run `uv run ruff format` and
  `uv run ruff check` before pushing; CI enforces both
- **Types:** use type annotations on all public functions
- **Style:** follow patterns in the existing codebase; when in doubt, keep it simple

## Testing

```bash
uv run pytest          # run the full suite
uv run pytest -k name  # run a specific test
```

Add tests in `tests/` for any new behaviour. We use `pytest` with no coverage
threshold enforced, but aim to keep the suite meaningful.

## Documentation

- User-facing changes → update `README.md`
- New commands or flags → update the Commands reference table in `README.md`
- Architectural changes → update `AGENTS.md`
- New specs live in `docs/specs/`

## What happens after you submit

1. **CI runs** — pytest, ruff check, ruff format
2. **Maintainer review** — usually within a few days
3. **Feedback** — we may ask questions or request changes
4. **Merge** — once approved, a maintainer squashes and merges

If a week passes with no response, feel free to ping on the PR.

## Code of conduct

Be kind and assume good intent. Harassment of any kind won't be tolerated.
