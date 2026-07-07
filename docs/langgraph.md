# LangGraph Checkpoints

LangGraph checkpoints default to SQLite for local dev:

```text
data/checkpoints/langgraph.db
```

## Backends

| `CHECKPOINT_BACKEND` | Storage | Notes |
| --- | --- | --- |
| `sqlite` (default) | File | Survives API restarts; no Docker required |
| `memory` | In-process | Tests only |
| `postgres` | `DATABASE_URL` | Enables shared audit + pgvector memory pool |

```bash
# Postgres (optional)
export CHECKPOINT_BACKEND=postgres
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents
```

Implementation: `memory/checkpoint.py`, `memory/checkpoint_config.py`.

Full reference: [`doc.md`](../doc.md#checkpoints-sqlite-default).
