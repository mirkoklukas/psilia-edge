# Setup

This file contains instructions for Claude to set up and bootstrap a project — creating files and folders, adding `CLAUDE.md` entries, and installing any skills the workflow components below require. Everything Claude needs is in this file; it doesn't reference any external source.

## Build instructions

All instructions in this file are **non-destructive** — append, create new files, or skip if a target already exists. Never overwrite or delete existing content. Created files are empty unless a component specifies seed content.

Walk through the components in the `## Components` section below, in the order listed. For each component:

- **Read the component body carefully.** Each component contains explicit build instructions (its `**Build instructions.**` paragraph) and may contain implicit instructions throughout the body — file/folder structure to create, templates to materialize, conventions to register, `CLAUDE.md` lines to append.
- **Follow both.** Apply the explicit and any implicit steps for that component.
- **For `CLAUDE.md` additions**, append them under a `# WORKFLOW SETUP` section at the end of the project's `CLAUDE.md` (create the section if it doesn't exist). Place any `@`-reference lines (e.g. `@internal/index.md`) at the top of the section, grouped together and separated from the bullet entries by a blank line — so auto-loaded files are visible up front.
## Components

### Index

`internal/index.md` — Claude's primary navigation index. Lists what lives where so Claude can quickly resolve "where do I look for X?" without scanning the tree. Link-dense; Claude proposes and maintains the structure (loose buckets organized by purpose, not a fixed taxonomy).

Entry format:

- `[[doc]] — one-line summary`
- `[[doc#section]] — one-line summary` for section-level targets
- `[[doc]] ("alias 1", "alias 2") — one-line summary` for inline aliases

Example:

```markdown
- [[workflow-components]] ("workflow", "components") — ground truth for the workflow components.
- [[workflow-components#Working docs]] ("working docs", "doc frontmatter") — co-edited Markdown files; new ones start from a template.
```

When the user says _"check your index"_, _"check your index for X"_, or references something by short name or alias, Claude scans index entries to resolve the target before reading.

Owned by Claude — edit freely without asking. Update whenever a file is added, removed, renamed, or substantially changed. Explicit exception to the cardinal "don't refactor docs without being asked" rule.

Distinct from `repo-structure.md`: the index is a link-dense navigation map for Claude; `repo-structure.md` is a higher-level repo overview written for both human and LLM to read.

Carries `type: index` and `summary:` frontmatter — see `# Frontmatter convention` below.

**Build instructions.** Create `internal/index.md` with the following seed content:

````markdown
---
type: index
summary: Claude's primary navigation index — link-dense map for resolving "where do I look for X?". Owned by Claude; edited freely.
---
# Index

Navigation map for Claude. Each entry is a link plus a one-line summary; optional inline metadata (date, source count, etc.). Organized into loose buckets by category/purpose (entities, concepts, sources, ...) — not a fixed taxonomy.

Entry format:

- `[[doc]] — one-line summary`
- `[[doc#section]] — one-line summary` for section-level targets
- `[[doc]] ("alias 1", "alias 2") — one-line summary` for inline aliases
````

Auto-loaded into Claude's session context via `@`-reference in `CLAUDE.md` so it's always visible from session start.

Append to `CLAUDE.md`:

> @internal/index.md
>
> - `internal/index.md` — hand-curated semantic lookup: one-line summaries and aliases to help locate files **by what they're about**. Use it when you have a concept and need candidate docs/files, or when the user references something by alias / says _"check your index"_. Entries can target sections (`[[doc#section]]`) and carry inline aliases. It is NOT an inventory and may be incomplete — never use it to find a file by filename, and never use it as a substitute for inspecting the filesystem. For `@path` references or any "does X exist / what's in Y" question, go straight to `ls`/Read. Maintain the index and edit it freely without asking: update whenever a file is added, removed, renamed, or substantially changed.


### Log

`internal/log.md` — append-only operational record of what happened. Owned by Claude — append freely without asking. Append at the **end** (most recent last) so git diffs stay clean. Use `grep` to read recent entries; don't read the whole file.

**Log proactively** — don't wait to be asked. After any of the trigger categories below land, append an entry. Tie the check to the event (the change actually landing), not to turn boundaries.

**What to log** — context that wouldn't survive otherwise. Four categories:

- **Design decisions** — the *why* behind a choice; not captured in code or commits.
- **Fixes** — symptom → cause → fix for non-trivial errors (see `# Fix logging` below).
- **Gotchas / surprises** — env quirks, undocumented behavior, "looks wrong but isn't".
- **Convention changes** — the moment a convention shifts (the convention itself lives elsewhere).

Not the log's job: auto-created files (git tracks them), generic "significant changes" (`git log`), ingests (visible in the artifact), forward-looking ideas (`notes.md`).

Entry format:

```
## [YYYY-MM-DD] short title #tag1 #tag2
optional body
```

Example tags (loose, change as needed): `#decision` `#fix` `#gotcha` `#convention`.

**Fix logging.** When Claude resolves a non-trivial error (env quirk, opaque stack trace, undocumented behavior, anything that took noticeable search or trial-and-error), append a `#fix` entry — symptom, cause, fix — so the resolution survives the session. Auto-append, no need to ask. Trivial fixes don't qualify; rule of thumb: log it if it took more than a minute or required a web search.

Useful greps:

```bash
grep "^## \[" internal/log.md | tail -5   # last 5 entries
grep "#decision" internal/log.md           # all decisions
```

Carries `type: log` and `summary:` frontmatter — see `# Frontmatter convention` below.

**Build instructions.** Create `internal/log.md` with the following seed content:

````markdown
---
type: log
summary: append-only operational record of what happened (decisions, auto-created files, fixes). Owned by Claude; append at end.
---
# Log

Append-only record of what happened. Append at the end (most recent last).

Entry format:

```
## [YYYY-MM-DD] short title #tag1 #tag2
optional body
```
````

Append to `CLAUDE.md`:

> - `internal/log.md` — append-only log of context that wouldn't survive otherwise. **Log proactively** — don't wait to be asked. After any of these land, append an entry (most recent last): design decisions (the *why* — not captured in code or commits), non-trivial fixes (`#fix`), gotchas (env quirks, undocumented behavior), convention changes. Don't duplicate what git, `notes.md`, or the artifact already records. Use `grep` to read; don't read the whole file.

### Notes

`internal/notes.md` — post-it style catch-all for ideas, observations, and half-formed thoughts that don't have another home yet: feature ideas, follow-ups, things to revisit when planning. Forward-looking; a stack of post-its reviewed and processed periodically.

Distinct from `log.md`: notes are forward-looking ideas worth not forgetting; the log is a backward-looking record of what happened.

Anything under a `##` heading is a note. Dated + tagged is preferred; freeform headings are fine:

```
## [YYYY-MM-DD] title #tag1 #tag2
optional body
```

Typically the user adds notes themselves or asks Claude to add one — Claude doesn't append unprompted. When appending, add the date at minimum. Never delete or rewrite existing entries without approval.

Carries `type: notes` and `summary:` frontmatter — see `# Frontmatter convention` below.

**Build instructions.** Create `internal/notes.md` with the following seed content:

````markdown
---
type: notes
summary: post-it catch-all for forward-looking ideas. Append on user request only; never delete or rewrite entries without approval.
---
# Notes

Post-it catch-all for forward-looking ideas and half-formed thoughts.

Entry format:

```
## [YYYY-MM-DD] title #tag1 #tag2
optional body
```
````

Append to `CLAUDE.md`:

> - `internal/notes.md` — post-it catch-all for forward-looking ideas. Append only on user request (add the date); never delete or rewrite existing entries without approval.

### Feedback

`internal/feedback.md` — append-only log of behavior corrections and adjustments accumulated during collaboration. When the user adjusts Claude's behavior mid-session ("don't do X here", "always confirm Y before applying"), append an entry. Periodically reviewed and folded into the relevant skill or instruction file; folded entries get deleted (or marked `#folded`).

Distinct from:
- `notes.md` — forward-looking *ideas*. Feedback is a *correction*.
- Auto-memory (feedback type) — captures patterns across all conversations. This file is project-specific and meant to be processed.
- A skill — feedback is the *queue*; skills hold the *settled state*.

Entry format:

```
## [YYYY-MM-DD] short note #topic
What was said / what to change. Optional context.
```

Topics tag where the feedback applies (e.g. `#co-editing`, `#design-edits`, `#commits`).

Carries `type: feedback` and `summary:` frontmatter — see `# Frontmatter convention` below.

**Build instructions.** Create `internal/feedback.md` with the following seed content:

````markdown
---
type: feedback
summary: append-only log of behavior corrections. Folded into skills periodically.
---
# Feedback

Append-only log of behavior corrections. Folded into skills periodically.

Entry format:

```
## [YYYY-MM-DD] short note #topic
What was said / what to change. Optional context.
```
````

Append to `CLAUDE.md`:

> - `internal/feedback.md` — append when the user adjusts your behavior mid-session. Don't fold/process unless explicitly asked.

### Docs

`docs/` — single top-level folder for project docs: specs and design docs (what is being built), reference material, how-tos, research notes, gathered knowledge. In-flight working drafts live under `docs/drafts/` and graduate up to `docs/` once matured.

(One natural use: a post-it in `notes.md` grows into something substantial — extract it here. But that's one example among many; the folder is a general catch-all for everything except the single `design.md` at the root.)

**Keep it flat until it hurts.** Start with a flat `docs/` and let the index handle categorization. Promote sub-buckets (e.g. `references/`, `research/`, topic folders) only once a flat `ls` gets noisy — roughly 10+ files. The `docs/drafts/` subfolder is the one standing exception.

**Build instructions.** Create `docs/` and `docs/drafts/` at the repo root. No `CLAUDE.md` addition — Claude finds these via the index when relevant.

### Design

`design.md` — *the* primary design doc for the repo/system. Covers the design and architecture: system overview, code structure, file/folder layout, key decisions. One per project. Top-level for visibility.

Co-edited. Claude only changes it when the user concretely asks, or after the user approves a proposed change. No silent edits, no "while I'm in there" tweaks (cardinal rule).

Distinct from `docs/`: `design.md` is the single high-level design doc for the repo; `docs/` holds everything else — additional specs, references, research, working drafts. A "spec" is a doc describing a system, concept, architecture, model, or experiment; rationale ("why this approach") is welcome but not required. We use "spec" and "design doc" loosely and interchangeably. New drafts start in `docs/drafts/` and graduate into `docs/` once matured.

Carries `type: design` and `summary:` frontmatter — see `# Frontmatter convention` below.

**Build instructions.** Create `design.md` at the repo root with the following seed content:

````markdown
---
type: design
summary: primary design doc for the repo — architecture, structure, key decisions. Co-edited; changes require user approval.
---
# Design
````

Append to `CLAUDE.md`:

> - `design.md` — primary design doc (architecture, structure, key decisions). Co-edited; changes require user approval.

### Working docs

A **working doc** is a Markdown file the user and Claude co-edit over time — design proposals, research notes, drafts. Persists across sessions; can link to other docs via wikilinks (`[[other-doc]]`).

New working drafts start from the template below — copy from `internal/templates/SPEC.md` into `docs/drafts/` and rename. The template carries the required frontmatter and a usage blockquote that gets deleted on first edit.

**Template:**

````markdown
---
type: working-doc          # or `spec` once matured
summary: ""                # one-line description of what this doc is about
created: YYYY-MM-DD
tags: []                   # kind tags (#spec, #design-doc, #research-notes, #scratch) + topic tags
---
> Template for a new working doc. Copy this file and rename to start a new working doc. Fill in the frontmatter, then delete this block-quote. New drafts live in `docs/drafts/`; optionally promote into `docs/` once matured. Treat the doc as collaborative — Claude doesn't refactor unless asked.
# Title

Body.
````

Materialize the template above as `internal/templates/SPEC.md` so it can be copied on demand — a generated artifact, not the source of truth. Updates happen here first.

Resolution order when creating one:
1. User names a location explicitly.
2. Conversation context clearly points to one.
3. Default: `docs/drafts/`.

**Seed `summary` and `tags` from available context** — don't leave them empty. `summary` is a short, concrete one-liner (*"design proposal for the spatial-layer rewrite"*, *"research notes on cv2 camera indexing on macOS"*). For `tags`, mix a kind tag (`#spec`, `#design-doc`, `#proposal`, `#research-notes`, `#scratch`) and a few topic tags. Better to seed something reasonable than wait for the user.

**Cardinal rule.** Treat the doc as collaborative — Claude doesn't refactor unless asked.

**Build instructions.** Ensure `docs/drafts/` exists (created by the Docs component above). Create `internal/templates/` and materialize the template above as `internal/templates/SPEC.md`.

Append to `CLAUDE.md`:

> - New working docs: copy `internal/templates/SPEC.md` into `docs/drafts/` and rename. Seed `summary` and `tags` from context. Treat as collaborative — don't refactor unless asked.

### Inline instructions

A `#hey-claude` tag embedded in any doc — a sticky note addressed to Claude. Use it to leave a standing directive (*"keep a TOC of this section"*, *"keep this list alphabetized"*) or a pointer (*"this invariant matters"*, *"edge case from incident X lives here"*) next to the content it pertains to. Claude finds these tags on demand and acts on them.

**Persistent + idempotent.** The tag stays in the doc. Re-running reconciles surrounding content to the desired state: first run creates, subsequent runs update on drift, no-op when in sync. The user removes the tag when it's no longer wanted.

**Single tag, intent inferred from context.** `#hey-claude` covers both directives and pointers — Claude reads the phrasing to decide. Imperative leads ("make…", "keep…", "update…") signal a directive; observations or pointers don't trigger an action on their own.

**Three equivalent wrapping forms** — author's choice per use:

```markdown
#hey-claude make a TOC of this section

> #hey-claude make a TOC of this section

<!-- #hey-claude make a TOC of this section -->
```

All three resolve to the same grep (`#hey-claude`) and Claude treats them identically. The block-quote form leans directive by convention (visually set apart); the HTML-comment form hides the tag from rendered output while staying greppable.

**Scope** is inferred from surrounding context — a tag at the top of a doc applies to the whole doc; under a heading, to that section; next to a list, to that list.

**Trigger** — explicit invocation:

- *"run hey-claude for this doc"* — single-doc sweep.
- *"run hey-claude"* — repo-wide sweep.
- Also accepted: *"process #hey-claude tags in this doc / in the repo"*, *"act on the hey-claude tags"*.

**Action protocol.** Propose the intended change, confirm with the user, then apply — consistent with the cardinal "don't refactor docs unless asked" rule. No-op runs (content already in sync) skip the confirm step.

**Discovery.** `grep -rn '#hey-claude' .` returns every tag in the repo.

Distinct from:
- `feedback.md` — global behavior corrections. Inline instructions are per-doc, per-spot, contextual.
- `todos.md` — tracked project tasks. Inline instructions are scoped maintenance directives, not items on a tracked list.
- `notes.md` — forward-looking ideas. Inline instructions are addressed to Claude as imperatives or pointers.

**Build instructions.** Convention only — no file or folder to create.

Append to `CLAUDE.md`:

> - `#hey-claude` tags — inline sticky notes left in any doc. When the user says *"run hey-claude for this doc"* / *"run hey-claude"*, grep for `#hey-claude` in scope, propose actions for each, confirm, apply. Persistent and idempotent — tags stay in place; re-runs reconcile to the desired state.

### Tmp folder

`internal/tmp/` — ephemeral, session-scoped stuff. No standing conventions; treat anything here as disposable.

**Build instructions.** Create `internal/tmp/`. No `CLAUDE.md` addition.

### Todos and next session

Two related but distinct files.

#### `internal/todos.md`

Project todos. Structure is loose — common sections: `backlog`, `active`, or topic-specific groupings. The user typically asks Claude to add items; Claude can also keep the file tidy (regroup, fold duplicates, trim resolved items) without asking each time. Substantive edits to existing items still need user approval.

> A dedicated todo agent is a possible future addition. Not adopted now.

#### `internal/tmp/next-session.md`

Short note on what to pick up next session — what to work on or continue, not a comprehensive todo list. Read at the start of every session. Surface; don't act on autonomously. Lives in `tmp/` because it's consumed and replaced each session.

`todos.md` carries `type: todos` and `summary:` frontmatter — see `# Frontmatter convention` below. `next-session.md` is ephemeral and skips frontmatter.

**Build instructions.** Create `internal/todos.md` with the following seed content:

````markdown
---
type: todos
summary: project todos. Claude may keep tidy; substantive edits to existing items require user approval.
---
# Todos
````

Create `internal/tmp/next-session.md` (no frontmatter, no seed).

Append to `CLAUDE.md`:

> - `internal/todos.md` — project todos. Claude may keep it tidy; substantive edits to existing items require user approval.
> - `internal/tmp/next-session.md` — read at session start. Surface what's there; don't act on it autonomously.

### Repo structure

`repo-structure.md` — mirrors the current state of the repo at a level useful for quick orientation: folder layout with a brief description per folder, key files called out. Not a literal tree dump — a readable overview. Top-level because it's useful for fresh cloners.

Owned by Claude — edits freely as the codebase evolves. Audience is both human and LLM.

Distinct from `index.md`: the index is a link-dense navigation map for Claude (lives in `internal/`); `repo-structure.md` is a readable overview of the repo for both human and LLM.

Carries `type: repo-structure` and `summary:` frontmatter — see `# Frontmatter convention` below.

**Build instructions.** Create `repo-structure.md` at the repo root with the following seed content:

````markdown
---
type: repo-structure
summary: readable overview of the repo's folder layout. Owned by Claude; kept current as the codebase evolves.
---
# Repo structure
````

Going forward, a dedicated `repo-structure-agent` will keep this file up to date. Auto-loaded into Claude's session context via `@`-reference in `CLAUDE.md`.

Append to `CLAUDE.md`:

> @repo-structure.md
>
> - `repo-structure.md` — readable overview of the repo. Claude keeps it current as the codebase evolves.

### Scripts

`scripts/` — top-level folder for one-off scripts and utilities created during sessions: data-exploration helpers, ad-hoc transforms, small CLIs. Distinct from `src/` (the actual project code) and from `internal/tmp/` (disposable session scratch). Promote to `src/` if a script stabilizes and earns a real home.

**Keep it flat until it hurts.** Descriptive filenames go a long way; topic subfolders only once a flat `ls` gets noisy.

**Optional catalog.** When the folder grows enough that "what's in here?" stops being obvious, add a `scripts/tools.md` catalog with one line per script:

```
name — path — description — side effects
```

Adding a script to the catalog requires user approval (one-time review of what it does). Running a cataloged script does *not* need re-approval. Destructive or shared-state operations (delete, push, mutate prod) still warrant per-run confirmation regardless. Until the catalog exists, scripts are informal.

Each script gets a one-line comment at the top describing what it does. Check existing scripts (and `tools.md` if present) before writing a new one to avoid duplication.

**Build instructions.** Create `scripts/` at the repo root. No `CLAUDE.md` addition.

### Results

`results/` — top-level folder for generated artifacts from running scripts or exploratory work: data dumps, plots, tables, reports. Distinct from `scripts/` (executables) and `internal/tmp/` (disposable).

**Keep it flat until it hurts.** No mandated subfolder convention — let the folder organize organically and impose structure (e.g. dated or topic-based subfolders) only once it actually gets messy.

**Build instructions.** Create `results/` at the repo root. No `CLAUDE.md` addition.
