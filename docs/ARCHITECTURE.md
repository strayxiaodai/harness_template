# Architecture

Top-level map for this LangGraph harness repository.

## Repository Shape

Flat Python packages at the repository root for graph logic; HTTP serving under
`app/`.

```text
harness_template/
├── agent/           # LangGraph nodes (planner, executor, learner, actioner, …)
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
│   ├── api/         # Route handlers (/run, /resume, /stream, /skills, /threads)
│   ├── core/        # App factory and HTTP config
│   ├── services/    # Harness run/resume/stream + thread_artifacts
│   ├── schemas/     # Request/response models (including ThreadSummary)
│   ├── threads/     # Per-thread stage markdown (gitignored; runtime)
│   ├── skills/      # Distilled playbooks (SKILL.md)
│   ├── db/          # Graph lifespan accessors
│   └── frontend/    # React + Vite developer console
├── tests/           # pytest suite (namespace aliases in conftest.py)
├── docs/            # Knowledge base (IMPLEMENTATION.md, PRODUCT.md, DESIGN.md, …)
```
This differs from the upstream harness-template scaffold (`apps/`,
`packages/`, `infra/`). Do not reorganize without an execution plan and
import-alias migration.

## Runtime Topology

```text
Client (curl / React console)
        │
        ▼
  app/main.py  (FastAPI + CORS)
        │
        ├── app/api/runs.py     → /run, /resume, /stream
        ├── app/api/skills.py   → /skills, /skills/distill, /skills/save
        ├── app/api/threads.py  → /threads (list app/threads artifacts)
        └── app/api/health.py   → /health
        │
        ▼
  app/services/harness.py
        │
        ▼
  LangGraph (graph/builder.py)
  planner → executor → learner → actioner → route (planner|END)
        │
        ├── SQLite / Postgres checkpoints (memory/checkpoint.py)
        ├── Thread artifacts (app/services/thread_artifacts.py → app/threads/)
        ├── RAG service (rag/service.py)
        ├── Audit pool (audit/logger.py, optional Postgres)
        └── MCP tools (harness_mcp/, optional)
```

**Example — two compiled graphs at startup:**

| App state field | `human_in_the_loop` | Use |
| --- | --- | --- |
| `graph_auto` | `false` | `/run` default; runs to completion or max rounds |
| `graph_step` | `true` | `/resume`; pauses after planner, executor, learner |

Actioner may also call `interrupt()` for action review when HITL is on and
there are pending memories or `loop_score >= 80`.

## Console ↔ API Mapping

The React console (`app/frontend/`) proxies `/api/*` → `localhost:8000` via
Vite (see [`FRONTEND.md`](FRONTEND.md)).

| UI region | API / state source |
| --- | --- |
| `StatusBar` | `GET /api/health`; thread picker from `GET /api/threads` (attach-only) |
| `CommandColumn` | `POST /api/run`, `/api/resume`; skill list from `/api/skills` |
| `GraphSpine` | `GRAPH_NODES` + `timeline` from SSE updates |
| `Workplace` | Selected timeline payloads; clarification and `action_review` HITL interrupts |
| `TraceTimeline` | SSE `stream_mode=updates` chunks per node |
| `InspectorStack` | Accumulated state: `plan`, `execution`, `learning`, `tool_calls`, `memory_context` |
| Skill distill/save | `POST /api/skills/distill`, `/api/skills/save` |
| Thread attach | `GET /api/threads` → set `thread_id` + Task/Plan (no checkpoint hydrate) |

**Example — what the operator sees after a HITL pause:**

```json
{
  "status": "awaiting_human",
  "needs_human": true,
  "next_action": "executor",
  "last_role": "planner",
  "rounds": 0
}
```

→ Graph spine highlights `planner` complete; resume button enabled in command column.

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
- When architecture changes, update this file and [`IMPLEMENTATION.md`](IMPLEMENTATION.md) in the
  same task.

## Import Convention

Source files live at the repository root. Tests register namespace aliases in
`tests/conftest.py`:

```python
# tests/conftest.py pattern — resolves app.graph.* to graph/*
from app.graph.routing import route_after_action
```

## Data And Persistence

| Concern | Default | Optional |
| --- | --- | --- |
| Graph checkpoints | SQLite `data/checkpoints/langgraph.db` | Postgres |
| Document RAG index | FAISS + BM25 under `data/rag/` | — |
| Memory store | FAISS under `data/rag/memory/` | pgvector via Postgres |
| Audit log | No-op (debug skip) | `agent_audit_log` table |
| Distilled skills | `app/skills/<slug>/SKILL.md` | — |
| Thread run artifacts | `app/threads/<slug>/` (+ `.index.json`) | `HARNESS_THREADS_DIR` |

## Local Development Model

```bash
# Terminal 1
uvicorn app.main:app --reload --port 8000

# Terminal 2 (optional console)
cd app/frontend && npm run dev

# Validation
pytest tests/ -q -k "not live"
```

See [`IMPLEMENTATION.md`](IMPLEMENTATION.md) for API curl examples and RAG ingest.

## Observability (current)

- Python `logging` module (no centralized `logging_config.py` yet).
- Audit events to Postgres when `DATABASE_URL` + pool are configured.
- No metrics or tracing pipeline yet. See [`RELIABILITY.md`](RELIABILITY.md).

## Related Docs

| Doc | Topic |
| --- | --- |
| [`IMPLEMENTATION.md`](IMPLEMENTATION.md) | Schemas, env vars, API examples |
| [`LANGGRAPH.md`](LANGGRAPH.md) | Checkpoint backends |
| [`FRONTEND.md`](FRONTEND.md) | Console dev and component map |
| [`PRODUCT.md`](PRODUCT.md) | Product intent |
| [`DESIGN.md`](DESIGN.md) | Visual system |
