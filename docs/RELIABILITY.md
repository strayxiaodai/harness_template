# Reliability

Operational bar for the LangGraph harness.

## Startup And Health

| Check | Endpoint / signal |
| --- | --- |
| API alive | `GET /health` |
| Graph compiled | App lifespan in `memory/checkpoint.py` |
| RAG initialized | `init_rag_service()` at startup |
| MCP tools | Optional; logged at debug if package missing |

Startup failures on Postgres backend raise if `DATABASE_URL` is unset when
`CHECKPOINT_BACKEND=postgres`.

## Logging

- Standard library `logging` throughout Python modules.
- No shared `logging_config.py` yet — modules use `logger = logging.getLogger(__name__)`.
- Audit events skipped at debug level when no Postgres pool is configured.

## Timeouts

- Graph invoke/resume accept `timeout_seconds` on API requests (see
  `app/db/graphs.py` `invoke_with_timeout`).
- HTTP 504 returned on `TimeoutError` from `/run` and `/resume`.

## Retries

- LLM calls use tenacity retry in `llm/retry.py`.
- No automatic retry on graph routing or tool failures within a round.

## Checkpoints

| Backend | Persistence | Use case |
| --- | --- | --- |
| `sqlite` (default) | `data/checkpoints/langgraph.db` | Local dev |
| `memory` | In-process | Tests |
| `postgres` | `DATABASE_URL` | Production / Docker |

See [`langgraph.md`](langgraph.md) and [`doc.md`](../doc.md).

## Local Validation

```bash
pytest tests/ -q -k "not live"
curl http://localhost:8000/health
```

## Known Failure Modes

| Symptom | Likely cause |
| --- | --- |
| 409 on `/resume` | Thread not started with `human_in_the_loop: true` |
| Empty audit rows | No Postgres pool; expected in SQLite-only dev |
| MCP tools missing | `mcp` extra not installed or `servers.json` not configured |
| RAG recall empty | Index not ingested; run `python -m rag.ingest --source ./docs` |

## Future Work

- Redis-backed run cancellation between graph steps
- Structured logging and trace correlation by `thread_id`
- Docker Compose healthchecks

CI/CD status: [`CICD.md`](CICD.md).
