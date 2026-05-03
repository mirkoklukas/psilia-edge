---
type: internal
created: 2026-05-01
tags: [knowledge-manager]
---

# Chores

Recurring maintenance tasks. The LLM updates `Last run` inline when a chore
completes. The log captures what was found or changed.

---

## Update repo-structure.md
Frequency: when the codebase changes significantly, or on request
Last run: —

Walk the repo, compare against `02_repo-structure.md`, and update any
sections that no longer reflect reality.

## Lint docs
Frequency: periodically or on request
Last run: —

Check for: missing index entries, broken links, stale content contradicting
the codebase, orphan docs, open scratchpads that may be resolved.

## Review open scratchpads
Frequency: periodically or on request
Last run: —

Check each scratchpad in `internal/`. Flag any that look resolved, abandoned,
or stale. Surface to the human for a decision.
