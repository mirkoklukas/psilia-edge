# Collaborative Working Documents


## Core Idea

**Working docs** are collaborative drafts where the user and LLM flesh out ideas together — design proposals, research notes, general scratch. They serve as scratch space that can grow into finished content and as long-term memory across sessions, capturing the conversation history (questions, answers, todos) inline. They can stand alone or relate to other docs via inline wikilinks (`[[other-doc]]`), e.g. spun off as a child to preserve Q&A history.

Each doc has a YAML frontmatter (`type`, `summary`, `created`, `tags`) and a Markdown body optionally annotated with inline tags (`#todo`, `#llm`, `#q`, `#a … #/a`).

By default they live in `docs/internal/scratchpads/`. Design proposals/drafts typically go in `docs/internal/design-docs/`. These are suggestions — another location is fine if context calls for it. Phrases like *"let's start a design doc on that"*, *"let's draft that out"*, *"start a note on that"* signal that the user wants a new scratchpad.

**Cardinal rule.** No autonomous edits. The LLM only touches the doc on explicit instruction — live in session, or as an async pass following the conventions in *Working modes* below. Otherwise, surface open items; don't act on them.

## Frontmatter

Each working doc starts with YAML frontmatter:

```yaml
---
type: working-doc          # fixed — identifies the file as a working doc
summary: "..."             # one-line description of what this doc is about
created: YYYY-MM-DD
tags: [tag1, tag2]
---
```

## Inline tags

Within a working doc, hashtag-style markers signal intent to both the human reader and the LLM. Visible in rendered output, easy to `grep`, low ceremony.

| Tag          | Meaning                                                    |
| ------------ | ---------------------------------------------------------- |
| `#todo`      | work to do (any actor — human or LLM)                      |
| `#llm`       | pointer — "when you read this doc, look here" (attention only, not a task) |
| `#q`         | open question                                              |
| `#a` … `#/a` | answer block (always close, even for one-liners)           |

Example:
```markdown
The macOS cv2 index workaround is fragile. #todo replace with a name-based
lookup once we vendor a PyObjC AVFoundation bridge.

#q should we merge the container into the spatial layer?

#a Yes — but only after the base layer's FastAPI state is decoupled
from container lifecycle. Two-step plan:

1. ...
2. ...
#/a

#llm
```

## Working modes

Two ways the doc gets worked on. They share the same inline-tag vocabulary but differ in synchrony.

### Live editing

User and LLM are in session together. Co-editing happens directly — discuss, draft, revise. Inline tags can still appear (drop a `#q` to defer something, leave a `#todo` for later), but they're not required.

Live is also where async-left items get resolved:

- **Walkthrough** — *"let's walk through the open questions"*. The LLM picks the first open `#q`/`#todo`/`#llm`, discusses it with the user, and commits the agreed answer as `#a … #/a` (or resolves the `#todo`/`#llm` accordingly) before moving on.
- **Review** — *"let's go over the answers"*. Q&A pairs already exist; the LLM walks through each one, the user decides if the answer is sufficient (approves it), and approved ones get merged. See *Merging and resolving* below.

### Async editing

User and LLM work on the doc at different times. Tags are the handoff mechanism — either side leaves markers, the other side picks them up later.

- User leaves `#q`/`#todo`/`#llm` as they go.
- On demand — *"go through the open items"* / *"draft answers inline"* / *"do a triage pass"* — the LLM scans the doc, adds `#a … #/a` blocks under each `#q`, and addresses `#todo` / `#llm` markers. It does **not** delete or modify the originals otherwise. The user reviews at a later stage.

### Merging and resolving

Only **approved** answers get merged. Approval currently happens via live review (see *Live editing → Review*). On approved answers, the default action is to resolve and flatten — delete the `#q` / `#a … #/a` markers and fold the content into the doc body as proper prose. Working tags disappear once resolved; the doc evolves toward finished content.

Flattening is destructive: the Q&A trail is gone unless preserved in a child doc. Only flatten on explicit instruction.

Optionally when the user calls for it explicitly, and/or when a Q&A history is worth preserving (e.g. it documents *why* a decision was made, not just *what* was decided), we create a new Q&A working doc attached to the doc under review and move the questions and answers there.

## Feature ideas

Speculative additions — not adopted, captured here so they don't get lost.

- **`#approved` tag for async merge.** Lets the user mark accepted answers between sessions; the LLM resolves them on the next pass without live review. Risk: drifts toward a comment-thread feature; revisit later.
- **Opt-in IDs for cross-reference (`#q-01`, `#ref-01`, …).** Number a tag only when something else needs to point at it (e.g. an answer in a different section, or an `#llm` pointing at a specific question). Default stays unnumbered — adding IDs everywhere is bookkeeping for no payoff.
- **Typed `parent`/`children` frontmatter properties.** For now we lean on Obsidian-native wikilinks (`[[other-doc]]`) in prose — the link graph and backlinks come for free. Add `parent`/`children` only if we need *typed* relationships (e.g. for non-Obsidian tooling); idiomatic form would be linked properties: `parent: "[[other-doc]]"`.
