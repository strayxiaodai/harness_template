# Product

Tradeoff heuristics for day-to-day decisions: [`PRODUCT_SENSE.md`](PRODUCT_SENSE.md).
Visual system: [`DESIGN.md`](DESIGN.md).

## Register

product

## Users

Solo developers and builders working locally with this LangGraph harness template. They run agent threads on their machine, inspect what happened, and intervene at human-in-the-loop (HITL) interrupts. Context is a dev environment: terminal nearby, API running on localhost, optional Postgres for checkpoints and audit.

## Product Purpose

A developer console for the harness — not a chat wrapper around the agents. The UI exposes the Plan → Do → Check → Action loop as inspectable, resumable work: submit a goal, pause at interrupts, override or approve, and see exactly what each node produced (plans, tool calls, reviews, RAG recall, audit events).

Success means **control and clarity**: the builder can answer "what did planner/executor/reviewer do, with what context, and why?" without digging through logs or raw JSON in a terminal.

## Brand Personality

**Instrument panel** — dense, precise, terminal-adjacent. Think flight deck or oscilloscope UI, not a consumer chat app. Voice is direct and technical; labels name agents and artifacts honestly. Emotional goal: **competence** — the user feels they are operating machinery they understand, not conversing with a black box.

Three words: **precise, legible, operational**.

## Anti-references

- **Not a LangSmith / Langfuse clone** — avoid their trace-tree layouts, copy, and observability-SaaS visual language. This console is purpose-built for this harness's graph (planner → executor → reviewer → actioner → memorize), not a generic LLM trace viewer.
- **Not generic AI chat** — no centered bubble thread as the primary surface; agent steps are structured panels, not messages.
- **Not marketing-dashboard SaaS** — no hero metrics, card-grid feature tours, or cream "startup" chrome on app screens.

## Design Principles

1. **Graph-native layout** — The LangGraph flow is the spine of the UI. Navigation and panels follow nodes and edges, not a chat transcript.
2. **Payload visibility** — Plans, tool calls, review verdicts, RAG chunks, and audit rows are first-class, expandable artifacts; summaries never replace inspectable source.
3. **HITL as control surface** — Run, resume, and override are prominent; interrupts are expected workflow, not error states.
4. **Local-first honesty** — UI degrades gracefully without Postgres (in-memory checkpoints, no audit rows) and clearly signals what backend capabilities are active.
5. **Instrument density** — Prefer compact, scannable tables and monospace payloads where appropriate; whitespace earns hierarchy, not decoration.

## Accessibility & Inclusion

WCAG 2.1 AA baseline for v1: keyboard-operable run/resume and HITL flows, visible focus, semantic structure for step timelines, and text contrast ≥ 4.5:1 for body copy. Respect `prefers-reduced-motion` for any step transitions or graph animations. Do not rely on color alone for agent role or status.
