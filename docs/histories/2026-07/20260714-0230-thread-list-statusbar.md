## [2026-07-14 02:30] | Task: StatusBar thread list attach

### Execution Context

- Agent ID: `inline-executing-plans`
- Base Model: `Composer`
- Runtime: `Cursor agent`

### User Query

> UI should be able to list existing thread for recovery/improvement again;
> threads under `app/threads`

### Changes Overview

- Area: API + harness console StatusBar
- Key actions: `GET /threads` from `app/threads` index/meta; StatusBar picker
  attaches `thread_id` + Task + Plan without checkpoint hydrate; F1–F15 tests

### Design Intent

Operators recover prior runs from on-disk artifacts without rebuilding timeline
state. Attach-only keeps resume/distill paths unchanged when checkpoints exist.

### Files Modified

- `app/services/thread_artifacts.py` — `list_threads`
- `app/schemas/threads.py`, `app/api/threads.py`, `app/core/app.py`
- `tests/test_thread_artifacts.py`, `tests/test_api.py`
- `app/frontend` — `useThreads`, `threadAttach`, StatusBar, App
- Docs: `IMPLEMENTATION.md`, `FRONTEND.md`, `DESIGN.md`, tech-debt, this history

### Manual smoke (S1–S5)

- S1: `curl /threads` returns live `app/threads` rows (verified)
- S2–S5: StatusBar picker — confirm in browser (attach preserves timeline;
  disabled while streaming; refresh after settle; New thread reset)

### Spec / plan

- [`docs/superpowers/specs/2026-07-14-thread-list-statusbar-design.md`](../superpowers/specs/2026-07-14-thread-list-statusbar-design.md)
- [`docs/superpowers/plans/2026-07-14-thread-list-statusbar.md`](../superpowers/plans/2026-07-14-thread-list-statusbar.md)
