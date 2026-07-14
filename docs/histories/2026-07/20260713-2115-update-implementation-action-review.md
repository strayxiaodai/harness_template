## [2026-07-13 21:15] | Task: Refresh IMPLEMENTATION.md for action-review as-built

### User Query

> update docs/IMPLEMENTATION.md

### Changes Overview

- Area: docs
- Key actions: Brought `docs/IMPLEMENTATION.md` in line with shipped
  action-review memory HITL — helpers, HITL resume selection rules, write path
  steps, console note, curl/test coverage, and clarified that `RunResponse`
  does not yet expose `interrupt` while clarification helper remains unwired.

### Design Intent

Keep IMPLEMENTATION.md as the runtime system of record so API, graph, and
console docs match current code instead of earlier incomplete designs.

### Files Modified

- `docs/IMPLEMENTATION.md`
- `docs/histories/2026-07/20260713-2115-update-implementation-action-review.md`
