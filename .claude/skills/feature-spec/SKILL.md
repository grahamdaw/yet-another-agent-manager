---
name: feature-spec
description: >
  Workflow for speccing and registering a new feature in this project. Use this skill whenever
  the user wants to plan, define, or create a new feature, enhancement, or stage — even if they
  just describe an idea informally ("I want to add X", "next feature is Y", "let's plan Z").
  Also use when the user asks to create a spec, write a spec, or add issues to Beads for new work.
  Don't wait for the user to say "create a spec" — if they describe something new to build,
  this is the right workflow.
---

# Feature Specification Workflow

New features in this project follow a deliberate spec-first process: understand the current state,
write a precise spec, get sign-off, then register the work in Beads. This keeps the issue tracker
clean (no half-baked tickets) and ensures every piece of work is grounded in the actual codebase.

---

## Step 1 — Read the current state of the project

Before writing anything, read:

- **`AGENTS.md`** — project overview, current implementation stages, structure, and conventions
- **`docs/specs/`** — all existing specs; understand the numbering and format
- **`pyproject.toml`** — package name, entry points, dependencies

This matters because specs must describe changes to the *actual* codebase, not a hypothetical
version of it. Skipping this step leads to specs that duplicate existing work, use the wrong
module names, or miss files that need changing.

---

## Step 2 — Write the spec

Create a new file in `docs/specs/`:

- Name: `NN-<slug>.md` where `NN` is the next available zero-padded number (e.g. `02-`, `03-`)
- Slug: lowercase, hyphen-separated, descriptive of the feature

### Spec structure

```markdown
# <Feature name>

**Goal:** One sentence stating what this achieves and why.

---

## Scope of changes

Everything that will change. Be specific — list files, paths, constants, commands.
If a directory is renamed, say so. If a config path moves, show before and after.
If users need to take action (e.g. migrate data), note it here.

## Acceptance criteria

A bullet list of verifiable conditions that must be true when the work is done.
Prefer concrete commands or checks:
- "`yaam doctor` passes with no warnings"
- "`ruff check` and `ruff format --check` pass"
- "No remaining references to the old name (grep clean)"
```

The scope section is the most important part — it should be specific enough that any engineer
(or agent) can implement the feature without asking clarifying questions.

---

## Step 3 — Review with the user

After writing the spec, summarise the scope and acceptance criteria for the user.

**Do not proceed to Step 4 without explicit sign-off.** A casual "looks good", "ship it",
or "yes" counts. The point is to catch misunderstandings before they become Bead issues.

If the user requests changes, update the spec and re-summarise.

---

## Step 4 — Create Bead issues

Once the spec is approved, create one Bead issue per logical unit of work:

```bash
bd create "<short description of the task>"
```

Guidelines:
- Each issue should be completable in a single focused session
- Reference the spec file path in the description where it helps orient the implementer
- Don't bundle unrelated work into one issue
- Don't create issues for work that's already done

---

## Step 5 — Sync Beads

After creating the issues, sync so they're committed to the repo:

```bash
bd sync
```

This commits the new entries to `.beads/issues.jsonl` and makes them visible to other agents
and collaborators.

---

## Conventions

- **Specs are reference documents, not progress trackers.** Don't edit a spec to mark things
  done — that's what Bead issues are for.
- **Update `AGENTS.md`** if the feature adds a new stage, renames a major component, or
  changes the project structure in a way that affects how future agents navigate the repo.
- **One spec per feature.** If a feature is large, break it into numbered sub-specs
  (`03-rename-part-1.md`, `04-rename-part-2.md`) rather than one sprawling document.
