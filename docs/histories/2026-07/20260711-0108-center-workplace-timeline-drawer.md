## [2026-07-11 01:08] | Task: Center workplace + timeline drawer

### Execution Context

- Agent ID: `composer`
- Base Model: `Composer`
- Runtime: `Cursor agent`

### User Query

> Move clarification HITL into the center workplace (not Command); keep Command as a thin control bar with secondary Continue only. Dock trace timeline as a bottom drawer collapsed by default. Make the left inspector a collapsible rail that auto-collapses during clarification. Document layout in DESIGN.md and FRONTEND.md.

### Changes Overview

- Area: harness console frontend shell + design docs
- Key actions:
  - Added `CenterColumn` (GraphSpine + Workplace + TraceTimeline drawer)
  - Added `Workplace` for clarification, step payloads, idle hint
  - Refactored `CommandColumn` to control bar; secondary Continue during interrupt
  - Made `InspectorStack` a collapsible secondary rail; auto-collapse on clarification
  - `TraceTimeline` drawer collapsed by default; `j`/`k` open on nav
  - Updated `docs/DESIGN.md` layout section and `docs/FRONTEND.md` component map

### Design Intent

Center becomes the primary operator surface: clarification and step payloads live in Workplace instead of the side Command column. Timeline no longer owns the middle flex region — it docks as a bottom drawer so the workplace stays visible. Inspector retains secondary artifacts (RAG, audit) but yields primary payloads to Workplace and collapses automatically during clarification to reduce noise. Dual Continue (primary in Workplace, secondary in Command) preserves keyboard `r` and quick resume from either column without duplicating question fields.

### Files Modified

- `app/frontend/src/App.tsx`
- `app/frontend/src/App.css`
- `app/frontend/src/components/CenterColumn.tsx`
- `app/frontend/src/components/CenterColumn.css`
- `app/frontend/src/components/Workplace.tsx`
- `app/frontend/src/components/Workplace.css`
- `app/frontend/src/components/CommandColumn.tsx`
- `app/frontend/src/components/TraceTimeline.tsx`
- `app/frontend/src/components/TraceTimeline.css`
- `app/frontend/src/components/InspectorStack.tsx`
- `app/frontend/src/components/InspectorStack.css`
- `app/frontend/src/hooks/useResumeDraft.ts`
- `app/frontend/src/lib/clarification.ts`
- `docs/DESIGN.md`
- `docs/FRONTEND.md`
- `docs/superpowers/specs/2026-07-11-center-workplace-timeline-drawer-design.md`

### Visual smoke checklist (code review)

Static review of `App.tsx` composition — browser not exercised (API not running):

- [ ] Desktop idle: `CenterColumn` shows spine + workplace idle hint; timeline drawer collapsed bar at bottom
- [ ] Step selected: workplace shows plan/execution/review; inspector rail open shows secondary RAG/audit
- [ ] Clarification interrupt: workplace shows questions + primary Continue; inspector auto-collapses; command shows secondary Continue only
- [ ] Timeline drawer: collapsed by default (`timelineOpen` starts `false`); expands on row click or `j`/`k`
- [ ] Inspector rail: user can re-expand during clarification; left resize handle hidden when collapsed
- [ ] Keyboard: `j`/`k` change step and open drawer; `r` resumes when `awaiting_human`
- [ ] Narrow viewport: stack order spine → workplace → drawer → inspector → command
