# Enterprise LangGraph Harness Template

This document describes a Python template for building multi-agent workflows
with LangGraph. The repository includes agent nodes, graph routing/builder,
LLM providers, executor tools, audit logging, and a full RAG subsystem.
FastAPI serving is implemented. Postgres checkpoints and Docker Compose are
**optional** — local dev defaults to **SQLite** checkpoints at
`data/checkpoints/langgraph.db`.

## Implementation Status

| Area | Status | Location |
|------|--------|----------|
| Agent nodes (planner, executor, reviewer, actioner, memorize) | Implemented | `agent/` |
| Graph routing and builder (memorize wired) | Implemented | `graph/routing.py`, `graph/builder.py` |
| Graph state and schemas | Implemented | `graph/` |
| LLM providers and retry | Implemented | `llm/` |
| Executor tools (`read_file`, `list_dir`, `search_knowledge_base`) | Implemented | `tools/` |
| RAG (ingest, hybrid retrieve, rerank, inject) | Implemented | `rag/`, `context/` |
| Audit logger (Postgres when pool set) | Implemented | `audit/logger.py` |
| Memory store FAISS (default) + pgvector (optional) | Implemented | `rag/stores/` |
| Prompts and settings | Implemented | `config/` |
| Unit tests (agents, graph, RAG, audit) | Implemented | `tests/` |
| FastAPI `/run`, `/resume`, `/stream`, `/health` | Implemented | `api/` |
| Skill distillation (`/skills`, `/skills/distill`) | Implemented | `skills/`, `api/server.py` |
| Skill save gate (≥1 harness loop) | Implemented | `skills/eligibility.py` |
| LangGraph checkpointer (SQLite default, Memory or Postgres) | Implemented | `memory/checkpoint.py` |
| Docker Compose stack | Planned | `docker-compose.yml` |

## Project Layout

```bash
harness_template/
├── agent/
│   ├── actioner.py         # increment rounds, set refine_from, audit route
│   ├── executor.py         # tool loop + ExecutorResult summary
│   ├── memorize.py         # post-round memory ingest (RAG write path)
│   ├── planner.py          # PlanResult + RAG memory inject
│   └── reviewer.py         # ReviewResult + tool-call visibility
├── audit/
│   └── logger.py           # Postgres audit writes (no-op without pool)
├── config/
│   ├── prompts.py
│   ├── prompts.yaml
│   └── settings.yaml       # RAG + memory_store backend
├── context/
│   └── pipeline.py         # query rewrite → memory recall → inject
├── graph/
│   ├── builder.py          # StateGraph compile + HITL interrupts
│   ├── routing.py          # route_after_action
│   ├── schemas.py
│   └── state.py
├── llm/
│   ├── providers.py
│   └── retry.py
├── rag/
│   ├── config.py, embeddings.py, service.py, schemas.py
│   ├── ingest/             # documents + memory_extract + CLI
│   ├── stores/
│   │   ├── vectorstore.py  # FAISS docs
│   │   ├── sparse.py       # BM25 docs
│   │   ├── memory.py       # FAISS memories (default)
│   │   ├── memory_pg.py    # pgvector memories (optional)
│   │   └── memory_factory.py
│   ├── retrieve/           # fusion, rewrite, search, rerank
│   └── inject/
├── tools/
│   ├── code_tools.py
│   ├── rag_tools.py
│   └── registry.py
├── api/
│   ├── schemas.py          # RunRequest, ResumeRequest, RunResponse
│   └── server.py           # FastAPI app (uvicorn api.server:api)
├── skills/
│   ├── distill.py          # thread → Cursor SKILL.md
│   ├── store.py            # .cursor/skills/ filesystem
│   └── context.py          # checkpoint → LLM context
├── memory/
│   └── checkpoint.py       # lifespan: pools, RAG, graph compile
├── migrations/
│   ├── 001_create_agent_audit_log.sql
│   └── 002_rag_memory.sql
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_graph.py
│   ├── test_audit_logger.py
│   ├── test_planner.py, test_executor.py, test_reviewer.py
│   ├── test_actioner.py
│   └── test_rag_*.py, test_memory_pipeline.py
├── data/rag/               # gitignored indexes
├── doc.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── requirements-rag.txt
└── requirements-postgres.txt
```

### Import Convention

Source files live at the repository root. Comments use the `app.*` prefix for
the target package layout. Tests register namespace aliases in
`tests/conftest.py` (e.g. `from app.agents import planner`,
`from app.graph.routing import route_after_action`).

## Architecture

### Agent loop

```text
planner → executor → reviewer → actioner → memorize → (route)
                ↑___________________|
```

After `memorize`, `route_after_action` chooses:

- `finish` — reviewer approved or round budget exhausted
- `executor` — redo work with the same plan
- `planner` — revise the plan first

One round = `planner → executor → reviewer → actioner → memorize`. The
actioner increments `rounds`; memorize runs memory ingest before routing.

### Graph builder

```python
from langgraph.checkpoint.memory import MemorySaver
from graph.builder import compile_with_checkpointer

graph = compile_with_checkpointer(MemorySaver())
# human_in_the_loop=True pauses after every node including memorize
```

`HITL_PAUSE_NODES`: `planner`, `executor`, `reviewer`, `actioner`, `memorize`.

### RAG

| Corpus | Index (default) | Index (postgres backend) |
|--------|-----------------|--------------------------|
| Documents | FAISS + BM25 under `data/rag/` | unchanged |
| Memories | FAISS under `data/rag/memory/` | `memory_entries` + pgvector |

**Read path** (planner round): rewrite → memory search → rerank → inject.

**Write path** (`memorize_agent`): `messages[cursor:]` → LLM extract → embed → store.

**Doc search** (executor tool): BM25 + FAISS → RRF → rerank → `ToolMessage`.

```python
from rag.service import init_rag_service
init_rag_service()
```

## Structured Schemas

See `graph/schemas.py`: `PlanResult`, `ExecutorResult`, `ReviewResult`.

## Core State

See `graph/state.py`. RAG fields:

- `memory_cursor` — ingest bookmark in `messages`
- `memory_context` — formatted recall block for prompts
- `memory_context_round` — round when context was built

## Routing

```python
# graph/routing.py
def route_after_action(state: AgentState) -> ActionRoute:
    if state.get("approved"):
        return "finish"
    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"
    refine_from = state.get("refine_from", "executor")
    if refine_from == "planner":
        return "planner"
    if refine_from == "finish":
        return "finish"
    return "executor"
```

`DEFAULT_MAX_ROUNDS = 3`.

## Agent Nodes

| Node | LLM? | Key outputs |
|------|------|-------------|
| `planner_agent` | Yes | `plan`, `memory_context`, `memory_context_round` |
| `executor_agent` | Yes | `execution`, `result`, `tool_calls` |
| `reviewer_agent` | Yes | `approved`, `review` |
| `actioner_agent` | No | `rounds`, `refine_from` + audit |
| `memorize_agent` | Yes (extract) | `memory_cursor` |

## Audit Logging

`audit/logger.py` writes to `agent_audit_log` when a Postgres pool is installed
via `set_audit_pool(pool)`. Without a pool, events are skipped at debug level
(tests and local dev work without a database).

```python
from audit.logger import set_audit_pool, write_audit_event

await write_audit_event(
    thread_id=state["thread_id"],
    round_number=1,
    node="executor",
    event_type="tool_call",
    payload={"tool": "read_file", "status": "ok"},
)
```

Apply migration: `migrations/001_create_agent_audit_log.sql`.

Event types in use: `tool_call`, `route_decision`. Planned: `rag_memory_write`,
`rag_memory_recall`.

## RAG Configuration

`config/settings.yaml` + environment:

| Variable | Purpose |
|----------|---------|
| `RAG_ENABLED` | Kill switch |
| `RAG_INDEX_DIR` | Document/memory FAISS directory |
| `EMBEDDING_PROVIDER` | `openai` or `ollama` |
| `RAG_MEMORY_BACKEND` | `faiss` (default) or `postgres` |
| `DATABASE_URL` | Required for postgres memory + audit |
| `RAG_MEMORY_EMBEDDING_DIM` | pgvector dimension (default 1536) |
| `EXECUTOR_TOOLS` | Add `search_knowledge_base` for doc search |

### Memory store backends

**FAISS (default)** — file-backed under `data/rag/memory/`. No database required.

**Postgres + pgvector** — set `RAG_MEMORY_BACKEND=postgres` and
`DATABASE_URL`. Install `requirements-postgres.txt`. Apply
`migrations/002_rag_memory.sql`. Wire the pool at startup:

```python
from rag.stores.memory_pg import set_memory_pool
set_memory_pool(audit_pool)  # same AsyncConnectionPool as audit
```

Falls back to FAISS if postgres is selected but `DATABASE_URL` is unset.

### Ingest documents

```bash
python -m rag.ingest --source ./docs
```

### Enable doc search

```bash
export EXECUTOR_TOOLS=read_file,list_dir,search_knowledge_base
```

## Executor Tools

| Tool | Default allow-list | Description |
|------|-------------------|-------------|
| `read_file` | Yes | Read workspace file |
| `list_dir` | Yes | List directory |
| `search_knowledge_base` | No (opt-in) | Hybrid doc search |

## Configuration

### LLM

```bash
LLM_PROVIDER=openai          # openai | anthropic | ollama
OPENAI_API_KEY=...
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.6:27b
```

### Checkpoints (SQLite default)

```bash
# default — SQLite file at data/checkpoints/langgraph.db
uvicorn api.server:api --reload --port 8000

# optional overrides
CHECKPOINT_BACKEND=sqlite
CHECKPOINT_SQLITE_PATH=data/checkpoints/langgraph.db

# in-memory (tests)
CHECKPOINT_BACKEND=memory

# Postgres (Docker / production) — also enables audit + pgvector memory pool
CHECKPOINT_BACKEND=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents
```

### Database (audit + postgres memory)

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents
```

## Requirements

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt       # pytest + SQLite checkpoints
pip install -r requirements-rag.txt      # optional cross-encoder
pip install -r requirements-postgres.txt # optional pgvector memory + audit
```

`requirements.txt` includes `langgraph`, `fastapi`, and `uvicorn`. SQLite
checkpoints use `requirements-sqlite.txt` (included in `requirements-dev.txt`).
Postgres checkpointing requires `requirements-postgres.txt` and
`CHECKPOINT_BACKEND=postgres`.

## Running Locally

### Start the API

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# optional: Postgres checkpoints + audit + pgvector memory
# pip install -r requirements-postgres.txt
# export CHECKPOINT_BACKEND=postgres
# export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents

uvicorn api.server:api --reload --host 0.0.0.0 --port 8000
```

Local dev uses **SQLite** checkpoints by default (`data/checkpoints/langgraph.db`).
Threads survive API restarts without Postgres or Docker.

### Example requests

```bash
# health
curl http://localhost:8000/health

# run to completion (auto graph, up to max_rounds)
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-1",
    "task": "Create a plan for adding request tracing",
    "plan": [],
    "max_rounds": 3
  }'

# human-in-the-loop (pauses after every node)
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-2",
    "task": "Create a plan for adding request tracing",
    "max_rounds": 3,
    "human_in_the_loop": true
  }'

# resume a paused HITL thread
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "demo-2"}'

# resume with plan override
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-2",
    "overrides": {"plan": ["clarify requirements", "add tracing"]}
  }'

# stream updates (SSE)
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-3",
    "task": "Review the architecture"
  }'

# list distilled Cursor skills
curl http://localhost:8000/skills

# load one skill playbook
curl http://localhost:8000/skills/add-request-tracing

# run a harness thread with a saved skill (task optional)
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "skill-run-1",
    "task": "",
    "skill_slug": "add-request-tracing",
    "human_in_the_loop": true
  }'

# manually distill a completed thread into .cursor/skills/<slug>/SKILL.md
curl -X POST http://localhost:8000/skills/distill \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-1",
    "name": "add-request-tracing",
    "refine": true,
    "save": false
  }'

# persist a previewed draft
curl -X POST http://localhost:8000/skills/save \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-1",
    "slug": "add-request-tracing",
    "name": "add-request-tracing",
    "description": "Add request tracing to the API",
    "body": "# Add request tracing\n\n..."
  }'
```

### Tests

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio

pytest tests/ -q -k "not live"    # 47 unit tests
pytest tests/test_api.py -v
```

### RAG ingest and query

```bash
python -m rag.ingest --source ./docs
python -c "
import asyncio
from rag.service import init_rag_service
svc = init_rag_service()
print(asyncio.run(svc.search_documents_text('your query')))
"
```

## Testing

| File | Covers |
|------|--------|
| `test_api.py` | `/health`, `/run`, `/resume`, `/stream`, schemas |
| `test_graph.py` | `route_after_action`, workflow nodes, compile |
| `test_audit_logger.py` | skip without pool, INSERT with pool |
| `test_planner.py` | Plan output, review feedback |
| `test_executor.py` | Tool loop, structured summary |
| `test_reviewer.py` | Verdict, tool calls in prompt |
| `test_actioner.py` | Rounds, refine_from, audit |
| `test_rag_*.py` | Fusion, formatter, service, tools |
| `test_memory_pipeline.py` | Extract, recall, inject, memorize |

## Planned Infrastructure

### Docker Compose

Postgres, Redis, API healthchecks, `test_compose_integration.py`.

## Production Notes

- Authentication and authorization for API routes
- Prompt-injection guardrails on retrieved memories
- Manifest validation at startup (embedding model vs index)
- Postgres connection pooling shared by audit and memory stores
- CI: unit tests, formatting, type checking

## Roadmap

1. Docker Compose and integration tests
2. RAG audit events (`rag_memory_write`, `rag_memory_recall`)
3. Redis-backed cancellation between graph steps
4. Authentication and rate limiting on API routes
