# Design System — Harness Console

Visual system of record for the harness developer console. Product constraints:
[`PRODUCT.md`](PRODUCT.md). Implementation: [`FRONTEND.md`](FRONTEND.md).

Impeccable skill files under `.cursor/skills/impeccable/` are live iteration
tooling — not the product design system of record.

## Mood

Late-night lab bench — phosphor trace on matte black, amber interrupt lamps.

## Color Strategy

Restrained. Dark pure-near-black surfaces; cyan carries active trace; amber
reserved for HITL interrupt only.

## Palette (OKLCH)

| Token | Value | Role |
|-------|-------|------|
| `--bg` | `oklch(0.09 0.008 220)` | App background |
| `--surface` | `oklch(0.13 0.012 220)` | Panels, sidebars |
| `--surface-raised` | `oklch(0.16 0.014 220)` | Inputs, nested regions |
| `--ink` | `oklch(0.92 0.01 220)` | Primary text |
| `--muted` | `oklch(0.68 0.015 220)` | Secondary labels |
| `--primary` | `oklch(0.72 0.14 195)` | Active node, primary actions |
| `--primary-on` | `oklch(0.98 0 0)` | Text on primary fills |
| `--accent` | `oklch(0.78 0.16 75)` | HITL interrupt, warnings |
| `--accent-on` | `oklch(0.12 0 0)` | Text on accent fills |
| `--success` | `oklch(0.65 0.14 150)` | Approved / complete |
| `--border` | `oklch(0.28 0.02 220)` | Dividers, panel edges |
| `--focus-ring` | `oklch(0.72 0.14 195)` | Focus-visible outline |

CSS implementation: `app/frontend/src/styles/tokens.css`.

## Typography

- **UI:** `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`
- **Data:** `"JetBrains Mono", "SF Mono", ui-monospace, monospace`
- **Scale (rem):** 0.75 / 0.8125 / 0.875 / 1 / 1.125 / 1.25
- Body max measure for prose: 70ch

## Layout

- Three-column shell ≥ 1024px: inspector rail · center · command bar (defaults 280px · flex · 268px)
- Side columns are **user-resizable** via drag handles when the inspector rail is open; widths persist in `localStorage`
- Double-click a handle (or Home while focused) resets to defaults
- `< 1024px`: stack spine → workplace → timeline drawer → inspector → command (resize disabled)
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32px
- Panel radius: 12px max; buttons 8px; pills full-round

### CenterColumn

The center column is the primary workplace. `CenterColumn` stacks three regions:

1. **GraphSpine** — graph-native node strip (planner → actioner)
2. **Workplace** — flex middle: clarification HITL, selected-step payloads, or idle hint
3. **TraceTimeline drawer** — bottom dock; **collapsed by default** (label + step count). Expands upward (~160–240px) without permanently displacing the workplace

### Inspector rail

- Desktop default: **open** (~240–280px, user-resizable)
- **Collapsible** to a narrow strip (~28–36px); left resize handle hidden when collapsed; center expands
- **Auto-collapses** when clarification interrupt is active; user may re-expand via strip/chevron
- When open: **secondary** artifacts only (RAG recall, audit, skill meta). Primary plan/tools/review move to Workplace when a step is selected

### Command bar

- Thin control column: Run → Skills → HITL toggle → Distill
- During `awaiting_human`: **secondary Continue** (amber) in HITL section; no clarification or memory-edit list
- **Primary Continue** lives in Workplace during clarification and action-review interrupts
- Overrides optional in both surfaces via shared draft state

```text
┌──────────────────────────────────────────────────────────┐
│ StatusBar                                                │
├──────────────┬─┬───────────────────────┬─┬───────────────┤
│ Inspector    │⁞│ GraphSpine            │⁞│ CommandColumn │
│  rail        │ │ Workplace (flex)    │ │  control bar  │
│  (drag/open) │ │ TraceTimeline drawer  │ │  (drag)       │
├──────────────┴─┴───────────────────────┴─┴───────────────┤
│ Footer shortcuts                                         │
└──────────────────────────────────────────────────────────┘
```

## Motion

- Active node pulse: 180ms ease-out; disabled under `prefers-reduced-motion`
- No page-load choreography

## Z-index

| Layer | Value |
|-------|-------|
| dropdown | 10 |
| sticky bar | 20 |
| toast | 40 |
| skip link | 50 |

## Product Principles (UI)

| Principle | Implementation |
| --- | --- |
| Instrument panel | Dense layout, monospace payloads, no chat bubbles |
| Graph-native | `GraphSpine` follows planner → executor → learner → actioner |
| Amber = HITL only | `--accent` for interrupts; `--primary` for active trace |
| Payload visibility | `Workplace` shows primary plan/tools/review; `InspectorStack` secondary RAG/audit |
| Local-first honesty | `StatusBar` reflects API health and capability gaps |

Do **not** introduce LangSmith-style trace trees or chat-thread-primary layouts
(see product anti-references in [`PRODUCT.md`](PRODUCT.md)).

## Console ↔ Artifact Mapping

| Operator question | UI location | State / API field |
| --- | --- | --- |
| What was the plan? | Workplace → Plan (or Inspector secondary) | `plan[]` |
| What did executor do? | Workplace → Execution | `execution`, `tool_calls` |
| Pass or fail? | Workplace → Review | `review.verdict`, `approved` |
| Where are we in the graph? | GraphSpine | `activeNode`, `timeline` |
| Clarification answers? | Workplace (primary Continue) | `interrupt`, `answers` |
| Memory approval? | Workplace → Action review | `interrupt.value.memories`, `interrupt_resume.memories` |
| Can I save a skill? | CommandColumn | `skill_eligible`, `skill_ineligible_reason` |
| Is the API up? | StatusBar | `GET /health` |

**Example — HITL interrupt styling:**

- `needs_human: true` → amber accent on pending `next_action` node
- Clarification: primary Continue in Workplace; secondary Continue in command bar
- Action review: editable pending memories in Workplace; Distill stays in command bar

## When To Extend vs Reuse

1. Reuse tokens from `app/frontend/src/styles/tokens.css`
2. Reuse `CenterColumn`, `Workplace`, `GraphSpine`, `InspectorStack`, `TraceTimeline`, `CommandColumn`
3. Update this file when adding global tokens or breakpoints
4. Mirror token changes in `tokens.css` in the same PR

## Responsive Behavior

- Three-column shell ≥ 1024px (see Layout above)
- Narrow viewports: `useNarrowViewport` stacks columns; preserve spine readability
- WCAG 2.1 AA: keyboard HITL flows, visible focus, sufficient contrast

## Related

- Dev commands and component map: [`FRONTEND.md`](FRONTEND.md)
- API shapes feeding the UI: [`IMPLEMENTATION.md`](IMPLEMENTATION.md#http-api)
