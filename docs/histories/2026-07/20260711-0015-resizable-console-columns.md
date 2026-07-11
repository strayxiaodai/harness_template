## [2026-07-11 00:15] | Task: Resizable console columns

### Execution Context

- Agent ID: `composer`
- Base Model: `Composer`
- Runtime: `Cursor agent`

### User Query

> Make left bar, right bar and center adjustable by user using mouse click and drag

### Changes Overview

- Area: frontend console shell
- Key actions: Added drag splitters between inspector / center / command; persist widths in localStorage; keyboard arrows + double-click reset; docs update

### Design Intent

Let operators tune instrument density without leaving the three-column shell; center stays flex.

### Files Modified

- `app/frontend/src/hooks/useResizableColumns.ts`
- `app/frontend/src/components/ColumnSplit.tsx`
- `app/frontend/src/components/ColumnSplit.css`
- `app/frontend/src/App.tsx`
- `app/frontend/src/App.css`
- `docs/DESIGN.md`
- `docs/FRONTEND.md`
