## [2026-07-13 22:40] | Task: Sync Workplace phase with Command run state

### User Query

> for UI, sync the state between workplace and command, like when command is
> "running", Workplace still showing "ready for a run"

### Changes Overview

- Area: frontend console
- Key actions: Workplace empty/status states now follow `RunPhase` (Running /
  Awaiting human / Complete / Error / Ready); pass `activeNode` into Workplace
  for phase copy. No Live strip on selected steps (Graph spine owns that).

### Design Intent

Center Workplace should mirror Command/StatusBar run state so operators never
see an idle “ready” surface while a thread is in flight.

### Files Modified

- `app/frontend/src/components/Workplace.tsx`
- `app/frontend/src/components/Workplace.css`
- `app/frontend/src/components/CenterColumn.tsx`
- `docs/FRONTEND.md`
- `docs/histories/2026-07/20260713-2240-workplace-phase-sync.md`

Phase-aware empty states only (no Live strip under selected steps; Graph spine
already surfaces active/paused node).
