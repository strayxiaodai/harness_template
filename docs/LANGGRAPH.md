# LangGraph Checkpoints

Graph state persistence for thread resume, HITL interrupts, and skill
distillation. Full API context: [`IMPLEMENTATION.md`](IMPLEMENTATION.md#checkpoints).

## Default (SQLite)

```text
data/checkpoints/langgraph.db
```

Threads survive API restarts without Docker or Postgres.

```bash
uvicorn app.main:app --reload --port 8000
# optional override:
export CHECKPOINT_SQLITE_PATH=data/checkpoints/langgraph.db
```

## Backends

| `CHECKPOINT_BACKEND` | Storage | When to use |
| --- | --- | --- |
| `sqlite` (default) | File | Local dev |
| `memory` | In-process | Unit tests |
| `postgres` | `DATABASE_URL` | Shared env, production |

**Example — Postgres:**

```bash
pip install -r requirements-postgres.txt
export CHECKPOINT_BACKEND=postgres
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents
uvicorn app.main:app --reload --port 8000
```

Postgres startup also wires audit pool and optional pgvector memory when
configured in `memory/checkpoint.py`.

## Two Compiled Graphs

| App state | HITL | Checkpointer usage |
| --- | --- | --- |
| `graph_auto` | No | `/run` without `human_in_the_loop` |
| `graph_step` | Yes (`interrupt_after`) | `/resume` threads |

Both share the same checkpointer backend and `thread_id` namespace.

**Example — resume requires HITL graph:**

```bash
# Start HITL
curl -s -X POST http://localhost:8000/run \
  -d '{"thread_id":"t1","task":"Review API","human_in_the_loop":true}' \
  -H "Content-Type: application/json"

# Resume (uses graph_step + same thread_id in checkpoint)
curl -s -X POST http://localhost:8000/resume \
  -d '{"thread_id":"t1"}' -H "Content-Type: application/json"
```

## Checkpoint Contents

Each `thread_id` stores full `AgentState`: plan, execution, review, rounds,
`memory_cursor`, skill fields, etc. Skill distillation reads checkpoint via
`skills/context.py`.

## Migrations

| Backend | SQL migration |
| --- | --- |
| Postgres checkpoints | LangGraph managed tables |
| Audit log | `migrations/001_create_agent_audit_log.sql` |
| pgvector memory | `migrations/002_rag_memory.sql` |

## Troubleshooting

| Issue | Check |
| --- | --- |
| Resume 409 | Thread started without `human_in_the_loop` |
| Stale state after code change | New `thread_id` or delete SQLite file |
| Postgres connection error | `DATABASE_URL` reachable, pool open in lifespan |

Implementation: `memory/checkpoint.py`, `memory/checkpoint_config.py`.
