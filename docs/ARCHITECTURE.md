# Architecture

Top-level map for this LangGraph harness repository.

## Repository Shape

This project uses a **flat Python package layout** at the repository root for
graph logic, with HTTP serving under `app/`.

```text
harness_template/
├── agent/           # LangGraph nodes (planner, executor, reviewer, …)
├── graph/           # StateGraph builder, routing, state, schemas
├── rag/             # Document + memory retrieval, ingest, stores
├── context/         # Memory recall pipeline for planner injection
├── llm/             # Provider adapters and retry
├── tools/           # Executor tool registry (read_file, list_dir, RAG, MCP)
├── audit/           # Postgres audit logger (no-op without pool)
├── skills/          # Thread → Cursor SKILL.md distillation
├── harness_mcp/     # MCP client: external tools in executor
├── memory/          # Checkpointer lifespan and backend config
├── config/          # prompts.yaml, settings.yaml
├── migrations/      # Postgres SQL for audit + pgvector memory
├── app/             # FastAPI app, services, schemas, React frontend
│   ├── api/         # Route handlers (/run, /resume, /stream, /skills)
│   ├── core/        # App factory and HTTP config
│   ├── services/    # Harness run/resume/stream business logic
│   ├── db/          # Graph lifespan accessors
│   └── frontend/    # React + Vite developer console
├── tests/           # pytest suite (namespace aliases in conftest.py)
├── docs/            # Collaboration, ops, and process knowledge base
├── doc.md           # Technical reference (API, RAG, env, schemas)
├── PRODUCT.md       # Product purpose and UX principles
└── DESIGN.md        # Console design system
```

This differs from the upstream harness-template scaffold (`apps/`,
`packages/`, `infra/`). Do not reorganize into that shape without an execution
plan and import-alias migration.

## Runtime Topology

```text
Client (curl / React console)
        │
        ▼
  app/main.py  (FastAPI + CORS)
        │
        ├── app/api/runs.py     → /run, /resume, /stream
        ├── app/api/skills.py   → /skills, /skills/distill, /skills/save
        └── app/api/health.py   → /health
        │
        ▼
  app/services/harness.py
        │
        ▼
  LangGraph (graph/builder.py)
  planner → executor → reviewer → actioner → memorize → route
        │
        ├── SQLite / Postgres checkpoints (memory/checkpoint.py)
        ├── RAG service (rag/service.py)
        ├── Audit pool (audit/logger.py, optional Postgres)
        └── MCP tools (harness_mcp/, optional)
```

## Boundary Rules

| Layer | Responsibility | May import from |
| --- | --- | --- |
| `agent/`, `graph/` | Graph nodes and routing | `llm/`, `tools/`, `rag/`, `audit/`, `skills/` |
| `app/` | HTTP transport and request/response schemas | Root packages via direct import |
| `tools/` | Executor tool surface | `harness_mcp/` (optional) |
| `app/frontend/` | UI only; talks to API over HTTP | No Python imports |

- Business logic for graph execution belongs in `agent/`, `graph/`, and
  `app/services/`, not in route handlers.
- The frontend must not embed graph logic; it reflects API snapshots and SSE
  streams.
- When architecture changes, update this file and [`doc.md`](../doc.md) in the
  same task.

## Import Convention

Source files live at the repository root. Some comments use an `app.*` prefix
as a target naming convention. Tests register namespace aliases in
`tests/conftest.py` so imports like `from app.graph.routing import …` resolve
to root modules.

## Data And Persistence

| Concern | Default | Optional |
| --- | --- | --- |
| Graph checkpoints | SQLite `data/checkpoints/langgraph.db` | Postgres |
| Document RAG index | FAISS + BM25 under `data/rag/` | — |
| Memory store | FAISS under `data/rag/memory/` | pgvector via Postgres |
| Audit log | No-op (debug skip) | `agent_audit_log` table |

## Local Development Model

1. Start API: `uvicorn app.main:app --reload --port 8000`
2. Start frontend (optional): `cd app/frontend && npm run dev`
3. Run tests: `pytest tests/ -q -k "not live"`

See [`doc.md`](../doc.md) for configuration, API examples, and RAG ingest.

## Observability (current)

- Python `logging` module (no centralized `logging_config.py` yet).
- Audit events to Postgres when `DATABASE_URL` + pool are configured.
- No metrics or tracing pipeline yet. See [`RELIABILITY.md`](RELIABILITY.md).

## Related Docs

- [`doc.md`](../doc.md) — schemas, env vars, API curl examples
- [`docs/langgraph.md`](langgraph.md) — checkpoint backend quick reference
- [`PRODUCT.md`](../PRODUCT.md) — console product intent
- [`DESIGN.md`](../DESIGN.md) — UI tokens and layout
