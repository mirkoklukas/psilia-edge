---
type: scratchpad
created: 2026-05-01
tags: [knowledge-manager]
parent: null
---

# KM Behavioural Instructions Design

## Goal

Design the behavioural instructions for the knowledge manager role —
when and how the LLM acts without being asked. Aim for the best workflow;
if something isn't working in practice, surface it and brainstorm solutions
rather than quietly working around it.

---

## Draft

Current behavioural instructions live in KNOWLEDGE_MANAGER.md under
"Behavioural Instructions (draft)". They cover:

- Starting work on a new spec or design topic → create scratchpad, log, index
- When a scratchpad is resolved → log outcome, update index
- When a design decision is made in conversation → append to log
- When a new file is created in `docs/internal/` → log and index immediately
- When a bash/Python sequence repeats or grows → write a tool
- At session start → glance at chores, flag overdue ones

---

## Open Questions

- Are the current triggers right? Too many? Too few?
- Should the LLM proactively suggest creating a scratchpad, or just do it?
- What's the right level of autonomy — how much should the LLM do without
  being asked vs. surfacing and waiting for confirmation?
- Should there be a "session start" checklist beyond just checking chores?
- How do we handle instructions that turn out to be wrong or create friction
  in practice — what's the feedback loop?

---

## Context & Memory

- Behavioural instructions are the most important part of the KM role spec —
  they're what makes the LLM a proactive collaborator rather than a passive tool.
- The goal is the best design, not the safest one. If a workflow isn't working,
  we should say so and propose changes rather than quietly abandoning it.
- Instructions are currently marked "(draft)" in KNOWLEDGE_MANAGER.md —
  intentionally provisional while we figure out what works in practice.
