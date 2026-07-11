# Center workplace + timeline drawer

Date: 2026-07-11  
Status: approved for planning  
Surface: `app/frontend` harness console  
Supersedes (layout center): parts of [`2026-07-10-console-layout-density-design.md`](2026-07-10-console-layout-density-design.md) for center/HITL placement only. Column order (Inspector · Center · Command) and command regroup remain.

## Problem

Clarification HITL currently lives in the right **Command** column, so the main work surface is a side panel. **Trace timeline** fills most of the center under the spine, leaving no dedicated workplace for clarification or step payloads. Operators need the center to be the primary workplace; Command should stay a thin control bar; timeline should dock as a bottom drawer, not own the middle.

## Goals

1. Center owns the **workplace** (clarification when interrupted; otherwise selected-step payloads; else idle hint).
2. Command is a **control bar** only (Run / Skills / HITL toggle / Distill + secondary Continue).
3. Trace timeline is a **bottom drawer** on the center column (collapsed by default).
4. Left Inspector becomes a **collapsible rail** (auto-collapse during clarification).
5. Preserve graph-native spine, amber HITL, keyboard `r` / `j` / `k`, resizable columns when inspector is open.

## Non-goals

- Palette / token redesign
- API or interrupt payload schema changes
- LangSmith-style trace trees or chat-primary layout
- Removing the inspector entirely (rejected two-column shell)

## Decisions

| Decision | Choice |
|----------|--------|
| Center content model | **Workplace swap** — clarification XOR step payloads XOR idle |
| Left column | **Collapsible rail** — open by default; auto-collapse when clarification active |
| Continue placement | **Both** — primary in Workplace; secondary in Command HITL |
| Timeline | **Bottom drawer** — collapsed bar by default; expand upward |
| Implementation | **`CenterColumn` component** owning spine + workplace + timeline drawer |

## Shell

```text
┌ StatusBar ──────────────────────────────────────────────────────────┐
├─ Inspector rail ─┬─ CenterColumn ──────────────────┬─ Command bar ─┤
│  open ~240–280px │  GraphSpine (auto)              │  ~220–268px   │
│  or ~28–36px     │  Workplace (flex)               │  controls +   │
│  strip           │  TraceTimeline drawer (bottom)  │  2° Continue  │
├──────────────────┴─────────────────────────────────┴───────────────┤
│ Footer shortcuts                                                    │
```

- Desktop ≥1024: three columns; resize handles between inspector↔center and center↔command when inspector is **open**.
- When inspector is collapsed, left handle is disabled/hidden; center expands.
- Narrow (&lt;1024): stack **spine → workplace → timeline drawer → inspector → command**.

## CenterColumn

New component wrapping:

1. **GraphSpine** — unchanged behavior (active / done / HITL amber on pending next).
2. **Workplace** — see below.
3. **TraceTimeline** — drawer chrome; see below.

### Workplace priority

1. If interrupt `kind === 'clarification'`: show clarification UI (reason, questions, answers, primary **Continue**, optional overrides `<details>`). Amber treatment.
2. Else if a timeline step is selected: show primary step payloads (plan / execution / tools / review) that today live in the inspector for that step.
3. Else: short idle hint (start from Command / expand timeline).

Clarification **question fields are not duplicated** in Command.

### Trace timeline drawer

- Default: **collapsed** bar — label + step count (+ optional live node).
- Expanded: panel grows upward (~160–240px), scrollable rows; does not permanently take flex middle.
- Row selection still updates workplace (when not clarifying) and inspector secondary content when rail is open.
- `j` / `k`: change selection even while collapsed; optionally open drawer on first nav (implementation may open on nav — preferred).

## Inspector rail

- Desktop default: **open** (~240–280px, user-resizable, persist width as today).
- Auto-collapse when clarification workplace is active; user may re-expand via strip/chevron.
- When open: **secondary** artifacts — RAG recall, audit, skill meta. Primary plan/tools/review move to Workplace when a step is selected.
- Narrow: full-width panel in stack (no rail chrome).

## Command bar

- Sections unchanged in spirit: Run → Skills (collapsed) → HITL → Distill.
- HITL: toggle always; when `awaiting_human`, show **secondary Continue** (amber). No clarification question list.
- Overrides: optional `<details>` sharing the same draft state as Workplace overrides.
- Errors / distill / skills unchanged.

## Files likely touched

- `app/frontend/src/App.tsx` / `App.css` — compose CenterColumn; inspector collapse state
- `app/frontend/src/components/CenterColumn.tsx` (+ css) — new
- `app/frontend/src/components/Workplace.tsx` (+ css) — new (clarification + step payloads + idle)
- `app/frontend/src/components/CommandColumn.tsx` — remove clarification form; keep secondary Continue
- `app/frontend/src/components/TraceTimeline.tsx` / `.css` — drawer collapsed/expanded
- `app/frontend/src/components/InspectorStack.tsx` / `.css` — rail collapse; secondary-only when workplace owns payloads
- `docs/DESIGN.md`, `docs/FRONTEND.md` — layout map

## Success criteria

1. Clarification answers + primary Continue appear in center Workplace, not as the main Command body.
2. Command remains a thin control column with secondary Continue only during interrupt.
3. Timeline default is a bottom bar; expanding it does not permanently replace the workplace.
4. Inspector auto-collapses during clarification; can be re-opened.
5. Selecting a timeline step shows payloads in Workplace when not clarifying.
6. `r` / `j` / `k` still work; build passes; DESIGN/FRONTEND updated.

## Verification

- Desktop: idle, step selected, clarification interrupt (drawer collapsed + expanded).
- Narrow stack order.
- Resume from primary and secondary Continue.
- Resize inspector when open; collapsed rail does not leave a dead splitter.
