## [2026-07-11 02:11] | Task: Action Review Memory HITL

### User Query

> Implement the action-review memory HITL feature across the graph, API,
> frontend Workplace, tests, docs, and history. Replace skill-preview-only
> actioner interrupts with one `action_review` pause, remove `memorize` from
> HITL pause nodes, and verify before committing without pushing.

### Changes Overview

- Area: Agent loop, memory review, API resume, frontend HITL review, and docs.
- Key actions: Moved memory extraction into `actioner`, added
  `pending_memories` / `approved_memories` state, mapped
  `interrupt_resume.memories` into approved rows, and made `memorize` a
  commit-only node that stores approved memories and clears review state.
- HITL behavior: `HITL_PAUSE_NODES` is `planner`, `executor`, `reviewer`.
  Actioner uses dynamic `interrupt(kind="action_review")` when HITL is on and
  memory candidates exist or `loop_score >= 80`; `memorize` no longer creates a
  second node-boundary pause.
- API / frontend: `/resume` forwards dynamic action-review resumes through
  `Command(resume=...)`. The center `Workplace` renders editable action-review
  memory rows and sends `interrupt_resume: { memories: [...] }`; Distill / skill
  preview controls remain in the Command column.
- Tests: Covered actioner interrupt payloads, resume mapping, pending cache
  idempotency, graph pause nodes, API action-review resume, and approved-memory
  commit behavior.
- Documentation: Updated implementation, architecture, frontend, design, specs,
  and history to describe final behavior.

### Design Intent

The actioner is the single decision point for loop quality, skill-preview
readiness, and memory review. Operators get one editable action-end pause before
anything is written; unattended runs auto-approve extracted candidates. The
pending-memory cache keeps local/dev LangGraph interrupt re-entry idempotent by
keying pending candidates by `(thread_id, memory_cursor)`; shared multi-process
deployments still need shared pending storage.

### Files Modified

- `agent/actioner.py`
- `agent/memory_review.py`
- `agent/memorize.py`
- `app/schemas/run.py`
- `app/services/harness.py`
- `app/frontend/src/components/Workplace.tsx`
- `app/frontend/src/hooks/useResumeDraft.ts`
- `app/frontend/src/lib/actionReview.ts`
- `app/frontend/src/types/api.ts`
- `graph/builder.py`
- `graph/state.py`
- `rag/ingest/memory_extract.py`
- `tests/test_action_review_api.py`
- `tests/test_actioner.py`
- `tests/test_graph.py`
- `tests/test_memory_pipeline.py`
- `tests/test_memory_review.py`
- `docs/IMPLEMENTATION.md`
- `docs/ARCHITECTURE.md`
- `docs/FRONTEND.md`
- `docs/DESIGN.md`
- `docs/histories/2026-07/20260711-0211-action-review-memory-hitl.md`
