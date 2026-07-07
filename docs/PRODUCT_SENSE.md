# Product Sense

Product principles that help agents make good tradeoffs without constant
prompting.

## Canonical Product Doc

The full product specification lives at [`PRODUCT.md`](../PRODUCT.md) in the
repository root. Read that file for users, purpose, brand personality,
anti-references, and design principles.

## Tradeoff Heuristics

When choosing between implementations, prefer options that:

1. **Expose graph state** — plans, tool calls, reviews, and RAG recall must stay
   inspectable in the console, not hidden behind summaries.
2. **Treat HITL as normal** — interrupts are workflow, not errors. Resume and
   override must stay prominent.
3. **Stay local-first honest** — degrade gracefully without Postgres; surface
   which backend capabilities are active.
4. **Resist chat-app patterns** — no bubble-thread-primary layout; the graph
   spine is the navigation model.
5. **Optimize for operator clarity** over marketing polish or generic LLM
   observability SaaS patterns.

## Quality Attributes (priority order)

1. Control and clarity for the solo developer operator
2. Legibility of agent artifacts (payload visibility)
3. Local dev simplicity (SQLite default, optional Postgres)
4. Throughput of harness loops (round budget, skill reuse)
5. Visual polish within the instrument-panel aesthetic

## Early-Stage vs Mature

| Early stage | Mature operation |
| --- | --- |
| Localhost API + Vite dev server | Single deployable unit with auth |
| Read-only executor tools | Sandboxed write/edit tools with guardrails |
| Manual pytest | CI gate + integration tests |
| File-based skills in `.cursor/skills/` | Versioned skill registry with eligibility gates |
