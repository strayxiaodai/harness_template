## [2026-07-10 20:06] | Task: HITL clarification questions

### Execution Context

- Agent ID: `Auto`
- Base Model: `Composer`
- Runtime: `Cursor`

### User Query

> Add a function that returns questions when the LLM is confused before moving
> forward when human-in-the-loop is enabled; combine with existing HITL; implement
> and document.

### Changes Overview

- Area: agent / API / console / docs
- Key actions:
  - Added shared `ask_clarification()` helper using the same `interrupt()` path
    as skill preview.
  - Extended structured agent outputs with optional clarification fields.
  - Wired planner/executor/reviewer/actioner; HITL off proceeds best-effort.
  - `/resume` accepts structured `answers` and uses `Command(resume=…)`.
  - Console shows clarification Q&A on resume; IMPLEMENTATION.md updated.

### Design Intent

Treat clarification as another HITL interrupt kind rather than a second control
plane. Structured `question_id` answers keep resume typed; auto-run stays
non-blocking.

### Files Modified

- `agent/clarification.py`
- `agent/planner.py`, `agent/executor.py`, `agent/reviewer.py`, `agent/actioner.py`
- `graph/schemas.py`, `graph/state.py`
- `app/schemas/run.py`, `app/services/harness.py`, `app/services/snapshot.py`
- `app/db/graphs.py`
- `config/prompts.yaml`
- `app/frontend/src/types/api.ts`, `CommandColumn.tsx`, `useConsole.ts`, `App.tsx`
- `tests/test_clarification.py`, `tests/test_api.py`
- `docs/IMPLEMENTATION.md`
- `docs/histories/2026-07/20260710-2006-hitl-clarification-questions.md`
