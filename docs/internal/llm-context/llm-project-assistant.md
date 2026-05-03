---
type: internal
created: 2026-05-01
tags: [knowledge-manager]
---

# LLM-assisted Project Assistant

Role spec for the LLM acting as project assistant — maintaining the structured files in `docs/internal/` (index, log, todos, notes, repo-structure, reference, etc.) and collaborating on scratchpads for design and exploratory work.


## Overview

The LLM project assistant maintains a set of structured files in `docs/internal/` that keep the project organized and navigable across sessions, and collaborates with the human on scratchpads — exploratory working docs tied to a parent doc.

This spec covers:

- **Structured files** — index, log, todos, notes, repo-structure, reference, known-issues, chores, tools. See sections below.
- **Scratchpads** — collaborative working docs. See Scratchpads section.
- **Ownership rules** — which files the LLM edits autonomously vs. on request.
- **Commands** — informal phrases the human uses to trigger common operations.

Files referenced below live in `docs/internal/` unless noted. The default home for any new working doc is `docs/internal/scratchpads/`; promotion to top-level `docs/` is rare and reserved for first-class material.


## Scratchpads

A scratchpad is a collaborative working space that can be associated with any doc in the project — design docs, blueprint docs, state docs, internal docs, anything. It serves two purposes:

- A place to take notes, capture context, and accumulate memory and history around a document's evolution.
- A place to work out ideas and flesh out designs/content that may eventually feed back into the parent doc or become the doc itself.

Sometimes content gets split off into its own doc, but the scratchpad stays around as a place for tangents and trains of thought that don't fit into the polished doc.

**LLM rule:** scratchpads are *never edited autonomously* by the LLM — only when explicitly asked. This contrasts with `index.md`, `log.md`, `todos.md`, and `notes.md`, which have their own append rules.

### Frontmatter

```yaml
---
type: scratchpad
created: YYYY-MM-DD
tags: [tag1, tag2]
parent: null  # or path to related doc
---
```

A doc with an associated scratchpad can point to it via a `scratchpad` field in its frontmatter:

```yaml
scratchpad: [[scratchpad-filename]]
```

Works for any doc in the project — not just internal docs.


## Indexing and Logging

**`index.md`** — Primary navigation for the LLM. Organized by purpose (Ground Truth, Current State, Reference, Scratchpads, KM Infrastructure). Entry format: `[[name]] — summary`. Aliases format: `[[name]] ("alias 1", "alias 2") — summary`. Owned by the LLM — edit freely without asking; update whenever a file is added, removed, renamed, or substantially changed.

**`log.md`** — Append-only operational record of what happened: decisions, new information, significant changes, ingests, chores run. Owned by the LLM — append freely without asking. Append at the **end** (most recent last) — keeps git diffs clean. Use grep to read recent entries, don't read the whole file.

Entry format:
```
## [YYYY-MM-DD] short title #tag1 #tag2
```

Example tags: `#decision` `#new-file` `#chore` `#change` `#ingest` `#tool` `#question` `#retro`

```bash
grep "^## \[" docs/internal/log.md | tail -5   # last 5 entries
grep "#decision" docs/internal/log.md            # all decisions
grep "#tool" docs/internal/log.md                # all tool entries
```


## Project Management and Documentation

**`todos.md`** — Actionable tasks and next-session plans. The LLM may append entries (tagged `#llm`) and mark items done/completed (toggle the checkbox). Deletion is user-triggered — separate process TBD.

Format:
- Two groups: `## Active` (likely to be picked up next) and `## Backlog` (known but not urgent).
- Within a group, loose items at the top. `### Topic` sub-section only when ≥2 items share an area.
- One bullet per item; sub-bullets for steps. Markdown checkboxes for status: `- [ ]` / `- [x]`.
- Inline tags: type (`#fix`, `#feature`, `#refactor`, `#test`, `#decision-needed`) + area (`#network`, `#calibration`, etc.).
- If an item needs more than ~1 sentence of context, move the body to a scratchpad and link from the todo (`→ see [scratchpad-name]`).

**`notes.md`** — Post-it style catch-all for ideas and observations that don't have another home yet: feature ideas, follow-ups, half-formed thoughts. Forward-looking — things to revisit when planning. Think of it as a stack of post-its reviewed and processed periodically. The LLM may append entries (tagged `#llm`) but must not delete or rewrite existing entries without approval. Anything under a `##` heading is a note. Dated + tagged format is preferred:
```
## [YYYY-MM-DD] title #tag1 #tag2
Optional body.
```
Freeform headings are fine too when a date doesn't make sense.

**`repo-structure.md`** — Mirrors the current state of the repository at a level useful for quick orientation. The LLM keeps it current as the codebase evolves.

**`reference.md`** — User-facing reference of CLI subcommands (`psilia ...`) and runtime services (recording, preview), grouped by area. Each entry has a one-line tagline and short description. Source for `docs/reference.html`. Rebuild with `docs/internal/scripts/build_reference.py`.

**`known-issues.md`** — Documented bugs, errors, and their fixes. Append new entries as issues are discovered or resolved.


## Tools and Chores

**`chores.md`** — Recurring maintenance tasks with frequency and last-run date. The LLM updates the last-run date inline when a chore is completed and logs what was found or changed.

**`tools.md`** + **`scripts/`** — `tools.md` is the catalog; `scripts/` holds the actual scripts. When a sequence is used more than once or grows beyond ~3 steps, it becomes a script. Each script has a one-line comment at the top. Check `tools.md` before writing a new one to avoid duplication. Scripts with side effects outside `docs/internal/` require human approval.


## Commands

Informal phrases the human uses and what they mean.

- "re-compile the reference" / "rebuild the reference" — run `docs/internal/scripts/build_reference.py`
- "update the repo structure" — re-scan the repo and rewrite [[repo-structure]]
- "run the chores" — check [[chores]] and work through overdue items
- "lint the docs" — check [[index]] for missing files, broken links, orphan scratchpads
- "add a todo" / "note that down" / "log that" — append to [[todos]], [[notes]], or [[log]] respectively
- "make a note" / "park that" — append a dated entry to [[notes]]
