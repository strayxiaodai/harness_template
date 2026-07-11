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

- Three-column shell ≥ 1024px: inspector 300px · center flex · command 220px
- `< 1024px`: stack spine → timeline → inspector → command
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32px
- Panel radius: 12px max; buttons 8px; pills full-round

```text
┌──────────────────────────────────────────────────────────┐
│ StatusBar                                                │
├──────────────┬───────────────────────────┬───────────────┤
│ Inspector    │ GraphSpine + TraceTimeline│ CommandColumn │
│  (300px)     │      (flex)               │  (220px)      │
├──────────────┴───────────────────────────┴───────────────┤
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
| Graph-native | `GraphSpine` follows planner → memorize order |
| Amber = HITL only | `--accent` for interrupts; `--primary` for active trace |
| Payload visibility | `InspectorStack` shows raw plan, tools, review, RAG |
| Local-first honesty | `StatusBar` reflects API health and capability gaps |

Do **not** introduce LangSmith-style trace trees or chat-thread-primary layouts
(see product anti-references in [`PRODUCT.md`](PRODUCT.md)).

## Console ↔ Artifact Mapping

| Operator question | UI location | State / API field |
| --- | --- | --- |
| What was the plan? | Inspector → Plan | `plan[]` |
| What did executor do? | Inspector → Execution | `execution`, `tool_calls` |
| Pass or fail? | Inspector → Review | `review.verdict`, `approved` |
| Where are we in the graph? | GraphSpine | `activeNode`, `timeline` |
| Can I save a skill? | CommandColumn | `skill_eligible`, `skill_ineligible_reason` |
| Is the API up? | StatusBar | `GET /health` |

**Example — HITL interrupt styling:**

- `needs_human: true` → amber accent on pending `next_action` node
- Resume button primary in command column (not hidden in a menu)

## When To Extend vs Reuse

1. Reuse tokens from `app/frontend/src/styles/tokens.css`
2. Reuse `GraphSpine`, `InspectorStack`, `TraceTimeline`, `CommandColumn`
3. Update this file when adding global tokens or breakpoints
4. Mirror token changes in `tokens.css` in the same PR

## Responsive Behavior

- Three-column shell ≥ 1024px (see Layout above)
- Narrow viewports: `useNarrowViewport` stacks columns; preserve spine readability
- WCAG 2.1 AA: keyboard HITL flows, visible focus, sufficient contrast

## Related

- Dev commands and component map: [`FRONTEND.md`](FRONTEND.md)
- API shapes feeding the UI: [`IMPLEMENTATION.md`](IMPLEMENTATION.md#http-api)
