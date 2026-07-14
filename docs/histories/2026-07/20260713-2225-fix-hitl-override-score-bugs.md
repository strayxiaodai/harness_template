## [2026-07-13 22:25] | Task: Fix HITL learning/refine overrides and score reuse

### User Query

> fix (bugs from learner-actioner code review)

### Changes Overview

- Area: graph / API / actioner / console resume
- Key actions: Sync `approved` and preserve lessons on learning overrides;
  mirror `refine_from` onto `learning.suggested_step`; reuse stashed loop score
  across action-review re-entry; send clarification answers via
  `interrupt_resume`.

### Design Intent

Keep learning.verdict as the routing/soft-skip source of truth so operator
HITL corrections cannot diverge from `approved`, and keep interrupt/resume
idempotent without re-scoring.

### Files Modified

- `app/services/resume_overrides.py`
- `app/services/harness.py`
- `graph/routing.py`
- `agent/actioner.py`
- `agent/memory_review.py`
- `app/frontend/src/hooks/useResumeDraft.ts`
- `docs/IMPLEMENTATION.md`
- `tests/test_resume_overrides.py`
- `tests/test_graph.py`
- `tests/test_actioner.py`
- `tests/test_api.py`
- `tests/test_memory_review.py`
- `docs/histories/2026-07/20260713-2225-fix-hitl-override-score-bugs.md`
