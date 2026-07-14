## [2026-07-10 17:55] | Task: Expand IMPLEMENTATION.md

### User Query

> Need more details to fully understand this project, please add more into
> docs/IMPLEMENTATION.md
>
> Can we have a graph to understand how does each function works with each other?

### Changes Overview

- Added mental model, request lifecycle, app startup, status derivation
- Expanded per-node agent behavior (planner through memorize)
- Documented LLM layer, prompts, console flow, data-on-disk, glossary
- Added **Function Interaction Graphs** (Mermaid): HTTP→graph, agent loop,
  executor tool sequence, RAG read/write, startup lifespan
- Linked from ARCHITECTURE.md and docs/README.md

### Design Intent

Keep IMPLEMENTATION.md as the as-built encyclopedia. Mermaid graphs make
function-level wiring scannable in the IDE preview.

### Files Modified

- `docs/IMPLEMENTATION.md`
- `docs/ARCHITECTURE.md`
- `docs/README.md`
