# Console layout density rebalance

Date: 2026-07-10  
Status: approved for planning  
Surface: `app/frontend` harness console

## Problem

The three-column console feels **unevenly dense**: the command column is a packed wall of controls, the center (graph + timeline) feels hollow, and the inspector does not share the same rhythm. Palette and typography are out of scope; this is a **layout / grouping** fix.

## Goals

1. Even density across columns so the UI reads as one instrument panel.
2. **Center owns the viewport** (graph spine + trace timeline).
3. Command stays usable but no longer dominates visual weight.
4. Preserve product principles: graph-native, HITL as control surface, payload visibility, instrument density.

## Non-goals

- Palette, font, or StatusBar redesign
- New features or API changes
- Spine-led full-width shell (rejected approach C)
- LangSmith-style trace trees or chat-primary layout

## Decisions

| Decision | Choice |
|----------|--------|
| Approach | **B — Regroup command + rebalance widths** |
| Column order | **Inspector · Center · Command** (command on the right, Cursor-like agent side) |
| Desktop grid | `300px · 1fr · 220px` |
| Narrow (&lt;1024) stack | spine → timeline → inspector → command |

## Shell (§1)

```text
┌─────────────────────────────────────────────────────────────┐
│ StatusBar                                                   │
├──────────────┬────────────────────────────┬─────────────────┤
│ Inspector    │ GraphSpine + TraceTimeline │ Command         │
│ 300px        │ flex (primary)             │ 220px           │
├──────────────┴────────────────────────────┴─────────────────┤
│ Footer shortcuts                                            │
└─────────────────────────────────────────────────────────────┘
```

- Gap between columns: `--space-3` (12px).
- Center column: `min-height: 0`; timeline panel **fills leftover height** under the spine.
- Update `docs/DESIGN.md` Layout section to match (order + widths).

## Command column (§2)

Right column, regrouped:

1. **Run** (always open): Task, Plan (optional), Max rounds, Start thread, New thread.
2. **Skills** (`<details>`, **collapsed by default** on desktop and narrow): picker, preview, Run skill. Moves **below** Run (today it sits above Task).
3. **HITL**: checkbox always visible in a compact row; Resume + override/clarification UI expands when `phase === 'awaiting_human'` with amber (`--accent`) treatment.
4. **Distill**: existing `<details>`; open only when eligible (current behavior), otherwise collapsed.

Hints: one short line under Task; remove the long HITL explanatory paragraph. Keep error/alert affordances.

## Center + inspector (§3)

- **Spine:** slightly denser node chips; cyan (`--primary`) only for active; amber only for HITL interrupt state.
- **Timeline:** consistent row height (~36–40px); selected row uses `--surface-raised` + full **1px** `--primary` border (no side-stripe accent).
- **Inspector:** same `.panel` padding/radius as command; accordion gaps match; empty state is a short “Select a timeline step” line, not a tall hollow region.
- Shared panel chrome so all three columns feel like one instrument.

## Files likely touched

- `app/frontend/src/App.tsx` — column DOM order
- `app/frontend/src/App.css` — grid template columns / narrow stack
- `app/frontend/src/components/CommandColumn.tsx` + `.css` — regroup, defaults, hints
- `app/frontend/src/components/GraphSpine.css` — chip density
- `app/frontend/src/components/TraceTimeline.css` — row selection
- `app/frontend/src/components/InspectorStack.css` (+ empty state copy if needed)
- `docs/DESIGN.md` — layout map and widths
- `docs/FRONTEND.md` — only if component map / layout notes are stale

## Success criteria

1. At ≥1024px, columns render Inspector | Center | Command at ~300 / flex / 220.
2. Idle desktop: Skills and Distill collapsed; Run block is the only always-open command section.
3. Center timeline visibly fills vertical space under the spine (not a short stub).
4. Selected timeline step and inspector empty state do not leave large empty voids.
5. HITL interrupt still surfaces Resume with amber treatment; keyboard `r` unchanged.
6. Narrow viewport stacks story first, command last.
7. No palette/token renames required beyond optional shared panel padding consistency.

## Verification

- Visual check in browser at desktop and &lt;1024 widths.
- Smoke: start thread, select timeline step, interrupt + resume, open Skills / Distill.
- Existing frontend tests if any cover CommandColumn order; update snapshots only if present.
