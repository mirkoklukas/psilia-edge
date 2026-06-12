# Preferences

- The user primarily codes and is proficient in Python.
- Keep answers crisp, clear, and to the point — don't say something for the sake of it.
- Ask if things are not clear, rather than making implicit assumptions.
- Plan and ask for confirmation before starting to code.
- Make sure not to delete non-tracked files (git) without explicitly cross-checking with me.
- Note that I gitignore files with a leading underscore `_*` and `_*.*`, except for `**/__*__.py.`. It is okay to make suggestions for other exceptions.
- Do not edit any files if it is not clear that you should, especially when we are brainstorming about a solution.
- Plan and think first before writing code.

# Project Context

Project-specific docs (load on demand):
- docs/strategy/psilia-pitch.md — short two-pager: company vision, positioning, product description, business model.
- docs/ — specs, references, how-tos, research notes (use `internal/index.md` to navigate).

# WORKFLOW SETUP

@internal/index.md
@repo-structure.md
@design.md
@internal/tmp/next-session.md

- `internal/index.md` — hand-curated semantic lookup: one-line summaries and aliases to help locate files **by what they're about**. Use it when you have a concept and need candidate docs/files, or when the user references something by alias / says _"check your index"_. Entries can target sections (`[[doc#section]]`) and carry inline aliases. It is NOT an inventory and may be incomplete — never use it to find a file by filename, and never use it as a substitute for inspecting the filesystem. For `@path` references or any "does X exist / what's in Y" question, go straight to `ls`/Read. Maintain the index and edit it freely without asking: update whenever a file is added, removed, renamed, or substantially changed.
- `repo-structure.md` — readable overview of the repo. Claude keeps it current as the codebase evolves.
- `design.md` — primary design doc (architecture, structure, key decisions). Co-edited; changes require user approval.
- `internal/tmp/next-session.md` — read at session start. Surface what's there; don't act on it autonomously.
- `internal/log.md` — append-only log of context that wouldn't survive otherwise. **Log proactively** — don't wait to be asked. After any of these land, append an entry (most recent last): design decisions (the *why* — not captured in code or commits), non-trivial fixes (`#fix`), gotchas (env quirks, undocumented behavior), convention changes. Don't duplicate what git, `notes.md`, or the artifact already records. Use `grep` to read; don't read the whole file.
- `internal/notes.md` — post-it catch-all for forward-looking ideas. Append only on user request (add the date); never delete or rewrite existing entries without approval.
- `internal/feedback.md` — append when the user adjusts your behavior mid-session. Don't fold/process unless explicitly asked.
- `internal/todos.md` — project todos. Claude may keep it tidy; substantive edits to existing items require user approval.
- New working docs: copy `internal/templates/SPEC.md` into `docs/drafts/` and rename. Seed `summary` and `tags` from context. Treat as collaborative — don't refactor unless asked.
- `#hey-claude` tags — inline sticky notes left in any doc. When the user says *"run hey-claude for this doc"* / *"run hey-claude"*, grep for `#hey-claude` in scope, propose actions for each, confirm, apply. Persistent and idempotent — tags stay in place; re-runs reconcile to the desired state.
