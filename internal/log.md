---
type: internal
created: 2026-05-01
tags: [knowledge-manager]
---

# Log

Append-only record of design decisions, new information, and significant
doc changes. Most recent first. Format: `## [YYYY-MM-DD] short title #tag`.

---

## [2026-05-12] Lite mode: sensor identity is not auto-resolvable #decision
The cv2/AVFoundation probe in lite mode returns a `cv_index` and a resolution but no USB descriptors (vendor/product/serial), so there is no way to fingerprint the live device against the `sensors:` registry in `psilia.yaml` the way the two-layer runtime does (see design.md → "Calibration Resolution"). Consequence: associating a recording with a registered sensor — and therefore picking a calibration from `~/.psilia/calibrations/` — must be a manual UI step. Calibration will be snapshotted into the recording dir (design.md → "Lite Mode → Recordings"). Note added to `src/psilia_edge/runtime/lite.py` module docstring.

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

## [2026-05-05] Started stereo-depth scratchpad #new-file
New scratchpad at docs/internal/scratchpads/stereo-depth.md for stereo depth on Jetson Orin Nano. Blank — to be filled in collaboratively. Linked from index.md.

## [2026-05-05] Staged finding: Orin Nano has no PVA #new-file #hardware
docs/internal/staged/jetson-orin-nano-accelerators.md — verified via NVIDIA Jetson Linux Developer Guide that Orin Nano (4GB and 8GB) has zero PVA cores. Implication: no VPI PVA offload for stereo depth; GPU is the only compute target. OFA presence not separately verified.

## [2026-05-05] Spec update: always log new files under docs/internal/ #change
Added explicit rule to llm-project-assistant.md: append a #new-file entry to log.md whenever a new file is added under docs/internal/ (staged docs, scratchpads, scripts, reference material).

## [2026-05-05] Added Staged Files section to project-assistant spec #change
New section in llm-project-assistant.md describing the staged/ inbox pattern (placeholder — intake flow TBD). Frontmatter spec includes summary (1-line preferred, up to ~3 lines) and source fields. Backfilled summary/source into the existing staged doc jetson-orin-nano-accelerators.md.

## [2026-05-05] Clarified source field semantics #change
source is origin-only (conversation, web, paper, experiment) — full citations and verifying refs live in the doc body. Updated llm-project-assistant.md spec wording and trimmed the existing staged doc's source to "Conversation 2026-05-05".

## [2026-05-05] Renamed staged/ to inbox/, added knowledge-base framing #change
Renamed docs/internal/staged/ → docs/internal/inbox/. Reframed the project-assistant spec around "building a knowledge base" — Overview now distinguishes existing pieces (structured files, scratchpads, inbox) from the planned curated destination (docs/internal/knowledge-base/). Section "Staged Files" → "Inbox". Frontmatter type: staged → inbox (backfilled in jetson-orin-nano-accelerators.md).

## [2026-05-05] Verified: Orin Nano also has no OFA #change
Confirmed via NVIDIA Jetson Linux Developer Guide R36.4.4 (NVP Model Clock Configuration tables) that the Orin Nano tier has no OFA entries — Orin NX and AGX Orin list ofa: 780.8 MHz, Nano variants do not. Updated inbox/jetson-orin-nano-accelerators.md: added "What is OFA?" section, merged finding into "no PVA and no OFA", removed OFA from "Not verified", updated summary and tags. VPI's OFA-backend "advanced SGM" path is therefore unavailable on Orin Nano in addition to the PVA path.

## [2026-06-11] Migrated docs scaffold to SETUP.md root layout #convention
Adopted the SETUP.md workflow structure rooted at the repo root. Moved (git mv, history preserved): docs/internal/{index,log,notes,todos}.md → internal/, docs/internal/next-session.md → internal/tmp/next-session.md, docs/internal/repo-structure.md → repo-structure.md, docs/design.md → design.md. Non-SETUP files placed by judgment: known-issues.md & reference.md → docs/, scripts/build_reference.py + scripts/tools.md (catalog) moved out of docs/internal/scripts/ (updated REPO=parents[1] and reference.md path inside the script + catalog line). New scaffold: internal/feedback.md, internal/templates/SPEC.md, docs/drafts/, results/. .gitignore: docs/internal/tmp/ → internal/tmp/ with !next-session.md kept tracked. CLAUDE.md: replaced stale # Project Context @-refs (pointed to non-existent docs/01_design.md etc.), added # WORKFLOW SETUP section; kept @design.md + @internal/tmp/next-session.md auto-loaded (deviation from SETUP, which lists them as on-demand bullets) to preserve prior auto-load behavior.

## [2026-06-12] CLI restructured to a top-level composition root #change
Moved the `psilia` entry point from `psilia.edge.cli:app` to a new `psilia/cli.py` (root composition: owns the top-level Typer `app`, mounts the edge sub-apps flat — `runtime`/`sensor`/`data` — and registers `debug`). `psilia/edge/cli.py` no longer creates a root `app`; it just exposes `runtime_app`, `sensor_app`, `data_app`, and `debug` for the root to compose. **Why:** the `psilia` command will host general non-edge commands (`psilia <command>`), so the root belongs to the package, not to `edge`; `edge` becomes one contributor among future subpackages (data, vision). UX is unchanged — edge commands stay flat. pyproject.toml entry point updated + reinstalled to regenerate the console script (old script imported the now-removed `psilia.edge.cli:app`). Updated design.md (CLI tier) and repo-structure.md.
