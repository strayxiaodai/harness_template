# Design

Product-wide design principles for this repository.

## Canonical Design Doc

The harness console design system lives at [`DESIGN.md`](../DESIGN.md) in the
repository root. That file defines mood, palette (OKLCH tokens), typography,
layout (three-column shell), and component conventions.

Impeccable skill references under `.cursor/skills/impeccable/` are tooling for
live UI iteration — they are not the product design system of record.

## Stable Principles

- **Instrument panel** — dense, precise, terminal-adjacent; not a consumer chat
  app.
- **Graph-native layout** — LangGraph flow is the UI spine.
- **Amber for HITL only** — interrupt states get accent color; active trace uses
  cyan primary.
- **Payload visibility** — expandable artifacts beat collapsed summaries.
- **WCAG 2.1 AA baseline** — keyboard HITL flows, visible focus, sufficient
  contrast.

## When To Extend vs Reuse

- Reuse tokens from `app/frontend/src/styles/tokens.css` before adding one-off
  colors.
- Reuse existing console components (`GraphSpine`, `InspectorStack`,
  `TraceTimeline`, `CommandColumn`) before creating parallel patterns.
- Extend [`DESIGN.md`](../DESIGN.md) when introducing new global tokens or layout
  breakpoints.

## Frontend Implementation

See [`FRONTEND.md`](FRONTEND.md) for dev commands and verification flows.
