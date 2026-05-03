---
type: internal
created: 2026-05-01
tags: [knowledge-manager]
---

# Log

Append-only record of design decisions, new information, and significant
doc changes. Most recent first. Format: `## [YYYY-MM-DD] short title #tag`.

---

## [2026-05-03] Added build_reference.py tool #tool
Parses docs/internal/reference.md and writes docs/reference.html. Run with python docs/internal/tools/build_reference.py.

## [2026-05-03] Renamed design and setup docs #change
01_design.md → design.md, 03_setup.md → setup.md. Index updated.

## [2026-05-03] Moved reference.md to docs/internal/ #change

## [2026-05-03] Deleted features.md #change
Superseded by reference.md.

## [2026-05-03] Created reference.md #new-file
Structured markdown source for reference.html. Sections: Device Management, Sensors & Calibration, Runtime Lifecycle, Data Operations, Services. Format: ### heading, desc/details/badges fields.

## [2026-05-03] Deleted dev-notes.md #change
Merged content into proper destinations: troubleshooting → known-issues.md,
Notes & Ideas → docs/internal/notes.md (with dated entries). V0 Scope discarded.

## [2026-05-03] Created llm-context/ folder #change
Moved knowledge-manager.md and scratchpad-design.md to `docs/internal/llm-context/`.
These are meta-docs defining how the system works — distinct from scratchpads and drafts.

## [2026-05-03] Stripped KM draft back to settled sections #change
Old content saved to [[km-old-content]] scratchpad. Draft now ends at
Frontmatter section — continuing to build from there.

## [2026-05-03] Moved repo-structure.md into docs/internal/ #change
LLM-owned, fits naturally in internal. Updated index and KM draft references.

## [2026-05-02] Consolidated KM docs into one draft #change
Merged KNOWLEDGE_MANAGER.md stub, knowledge-manager.md draft, and
knowledge-manager-design scratchpad into a single doc at
`docs/internal/drafts/knowledge-manager.md`. Deleted the other two.

## [2026-05-02] Graduated scratchpad-design to drafts/ #change
Moved to `drafts/scratchpad-design.md` — still being worked on collaboratively.

## [2026-05-02] Decided approval flagging mechanism #decision
Folder convention as primary signal: `scratchpads/` and `drafts/` are
collaborative, everything else in `docs/internal/` is LLM-owned. Frontmatter
flag `collaborative: true` available as override for edge cases.

## [2026-05-01] Added workflow and approval questions to scratchpad-design #question
Full lifecycle (scratchpad → draft → approved → live) and approval flagging
mechanism (folder convention vs frontmatter flag vs hybrid) are open questions.
Picking up next session.

## [2026-05-01] Created drafts/ folder, moved KM spec there #decision #change #draft
`docs/internal/drafts/` added alongside `scratchpads/`. KNOWLEDGE_MANAGER.md
is now a stub pointing to the draft. Ownership model updated: drafts are
collaborative alongside scratchpads; LLM-owned vs collaborative is the
two-level distinction inside `docs/internal/`.

## [2026-05-01] Started km-instructions-design scratchpad #scratchpad #new-file
Designing the behavioural instructions for the KM role — when and how the LLM
acts without being asked. Free-floating; no parent doc yet.

## [2026-05-01] Started scratchpad-design scratchpad #scratchpad #new-file
Capturing the design of how scratchpads work — lifecycle, frontmatter, parent
association, sections. Free-floating for now; output will feed into KNOWLEDGE_MANAGER.md.

## [2026-05-01] Moved log.md into docs/internal/ #decision #change
Keeps `docs/` top-level clean; LLM is the primary writer and human reads
via Obsidian either way.

## [2026-05-01] Added hashtag-style tags to log entry format #decision
Tags go in the headline, grep-parseable. Tag list is evolving — tracked in
KNOWLEDGE_MANAGER.md.

## [2026-05-01] Added scratchpads/ subfolder #decision #change
Scratchpads moved to `docs/internal/scratchpads/` so they're easy for the
human to find. Existing scratchpad moved accordingly.

## [2026-05-01] Established frontmatter convention #decision
All `docs/internal/` files use YAML frontmatter with `type`, `status`
(scratchpads), `created`, and `tags`. Dataview-queryable in Obsidian.

## [2026-05-01] Established linking convention #decision
Wikilinks (`[[filename]]`) inside `docs/internal/` for Obsidian graph and
backlinks; standard relative markdown links everywhere else for GitHub compatibility.

## [2026-05-01] Bootstrapped knowledge manager #new-file #scratchpad
Created the initial knowledge management structure for psilia-edge docs.
New files: `internal/index.md`, `internal/chores.md`, `internal/tools/index.md`,
`internal/scratchpads/knowledge-manager-design.md`, `internal/log.md`.

## [2026-05-01] Designed knowledge manager role spec #decision
Drafted `KNOWLEDGE_MANAGER.md` in collaboration with the human. Key decisions:
four doc tiers (blueprint / state / internal / log); `docs/internal/` as the
LLM-owned space covering synthesis, scratchpads, and tools.
See [[knowledge-manager-design]] for full decision history.

## [2026-05-03] Renamed knowledge-manager.md to llm-project-manager.md #change
Reflected new framing as LLM-assisted project manager. Rewrote doc to match user's proposed structure: Core Ideas, Ownership, Indexing and Logging, Project Management and Documentation, Tools and Chores, Commands, Frontmatter.

## [2026-05-03] Moved tools/ to tools.md + scripts/ #change
Separated catalog (tools.md) from scripts (scripts/). Cleaner — no markdown mixed with code.
