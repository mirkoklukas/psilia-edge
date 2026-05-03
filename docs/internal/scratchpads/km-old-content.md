---
type: scratchpad
created: 2026-05-03
tags: [knowledge-manager]
---

# KM Old Content

Saved from knowledge-manager.md draft — old sections to be redrafted or discarded.

---

## Behavioural Instructions (draft)

Rules for when to act without being asked. These are defaults — the human
can always override.

**Starting work on a new spec or design topic:**
Create a scratchpad in `docs/internal/scratchpads/`, log it, and index it.
Name descriptively (e.g. `sensor-registration-rework.md`).

**When a design decision is made during conversation:**
Append a `log.md` entry even if no doc changed. Decisions made in chat
are otherwise lost.

**When a new file is created in `docs/internal/`:**
Always log it and index it immediately.

**When a bash or Python sequence is repeated or grows beyond ~3 steps:**
Write it as a script in `docs/internal/tools/`, add it to `tools/index.md`,
and log it. Check `tools/index.md` first to avoid duplicating an existing tool.

**At the start of a session (optional):**
Glance at `docs/internal/chores.md` and flag any chores that are overdue.
Don't run them automatically — surface them so the human can decide.

---

## Doc Tiers

### 1. Blueprint docs
**Who reads:** Human + LLM
**Who writes:** Human + LLM (human approves structural changes)

Agreed ground truth. Dual role: describes the system as it is *and* guides
how it should be extended. The canonical reference both parties work from.
Any structural change — new section, split, merge, rename — requires human
approval before it happens.

Examples: `01_design.md`, `strategy/`

### 2. State docs
**Who reads:** Human + LLM (primarily LLM)
**Who writes:** LLM (no approval needed)

Quick orientation snapshots that mirror current reality. The LLM keeps these
current as the codebase evolves.

Examples: `internal/repo-structure.md`

### 3. `docs/internal/` — LLM working space

The LLM's working space: synthesis files, scratchpads, drafts, tools, log,
index, chores. Every file here is indexed.

---

## Scratchpads & Drafts

See [[scratchpad-design]] for the full spec. Summary:

- **`scratchpads/`** — working space: thinking, exploring, designing.
- **`drafts/`** — evolved scratchpads, closer to a final doc.

Both are collaborative — the LLM does not edit them autonomously.

---

## Workflows

### When a doc is added
1. Add to `internal/index.md`.
2. Append a `log.md` entry.
3. Check if existing docs should link to it.

### When a doc is substantially changed
1. Update `internal/index.md` summary if scope changed.
2. Append a `log.md` entry.
3. Check if the change contradicts or updates anything elsewhere.

### When a doc is removed or archived
1. Move to `_archive/` or delete.
2. Remove from `internal/index.md`.
3. Append a `log.md` entry.
4. Check for broken cross-references.

### When a design decision is made
Append a `log.md` entry: what was decided, alternatives considered, why.

### When starting work on a new topic
1. Create a scratchpad in `docs/internal/scratchpads/`.
2. Add to `internal/index.md`.
3. Append a `log.md` entry.

### When a new tool is written
1. Add a one-line comment at the top of the script.
2. Add to `internal/tools/index.md`.
3. Append a `log.md` entry.

### When a chore is completed
1. Update `last run` in `internal/chores.md`.
2. Append a `log.md` entry.

### Periodic lint (on request)
- Docs missing from `internal/index.md`
- Broken links in index
- Stale content contradicting the codebase
- Orphan docs with no cross-references
- Open scratchpads or drafts that may be resolved or abandoned

---

## Open Questions

- Should CLAUDE.md point to `internal/index.md` as entry point?
- What chores are missing from `chores.md`?
- Any initial tools worth writing?
