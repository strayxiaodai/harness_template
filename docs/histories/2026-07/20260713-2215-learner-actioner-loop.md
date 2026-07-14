## [2026-07-13 22:15] | Task: Learner loop + fold memorize + stage UI

### User Query

> Ensure planner → executor → reviewer/actioner stages show on UI; fold memorize
> under actioner; evolve checker/reviewer into learner; actioner continue only
> back to planner (or END).

### Changes Overview

- Area: graph, agents, API, frontend, docs
- Key actions: Renamed reviewer→learner with lessons/candidates; folded memory
  commit into actioner (soft-skip on fail); routing `planner|finish` only;
  exposed `RunResponse.interrupt` + compact state; console GRAPH_NODES and
  Workplace/timeline patches for all four stages.

### Design Intent

Make actioner always meaningful after a learner pass (score/HITL/commit), keep
fail rounds routing-only, and ensure each stage can show results in the console.

### Files Modified

- Spec/plan under `docs/superpowers/`
- `graph/`, `agent/`, `skills/`, `app/schemas/`, `app/services/snapshot.py`
- `app/frontend/src/**`
- `docs/IMPLEMENTATION.md`, `ARCHITECTURE.md`, `FRONTEND.md`, `DESIGN.md`
- Tests: learner, actioner, graph, api, skills, memory pipeline
