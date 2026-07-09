# Reliability

Operational bar for the LangGraph harness.

## Startup And Health

| Check | Signal | Healthy example |
| --- | --- | --- |
| API process | `GET /health` | `{"status":"ok"}` |
| Graphs compiled | `app.state.graph_auto`, `graph_step` | Both set in lifespan |
| RAG service | `init_rag_service()` at startup | Doc search works when indexed |
| MCP tools | Optional | Debug log if package missing |

```bash
curl -s http://localhost:8000/health | jq
```

Degraded response when graphs failed to compile:

```json
{"status": "degraded", "detail": "graphs not compiled"}
```

Postgres backend without `DATABASE_URL` raises at startup — fail-fast by design.

## Logging

- Standard library `logging`; no shared `logging_config.py` yet.
- Pattern: `logger = logging.getLogger(__name__)` per module.
- Audit skipped at **debug** when no Postgres pool.

**Example — executor tool error logged + audited:**

```python
await write_audit_event(..., event_type="tool_call",
    payload={"tool": "read_file", "status": "error", ...})
```

## Timeouts

| Surface | Default | Max | HTTP code |
| --- | --- | --- | --- |
| `/run` `timeout_seconds` | 120s | 900s | 504 on exceed |
| `/resume` `timeout_seconds` | 120s | 900s | 504 on exceed |
| Executor tool loop | 5 iterations | — | partial result |

**Example — long-running task:**

```bash
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"slow-1","task":"Large refactor","timeout_seconds":600}'
```

## Retries

| Component | Retries | Notes |
| --- | --- | --- |
| LLM calls | Yes (`tenacity` in `llm/retry.py`) | Transient provider errors |
| Graph routing | No | Reviewer/actioner decide next step |
| Tool failures | No auto-retry | Recorded in `tool_calls` with `status: error` |
| HTTP client (frontend) | No | User retries run/resume |

## Checkpoints

| Backend | Persistence | Use case |
| --- | --- | --- |
| `sqlite` (default) | `data/checkpoints/langgraph.db` | Local dev |
| `memory` | In-process | Tests |
| `postgres` | `DATABASE_URL` | Shared / production |

Threads survive API restarts with SQLite/Postgres. See [`LANGGRAPH.md`](LANGGRAPH.md).

**Example — verify checkpoint file exists:**

```bash
ls -la data/checkpoints/langgraph.db
```

## Streaming Reliability

- SSE stream ends with `{"final": RunResponse}` or `{"error": "..."}`.
- Client disconnect does not cancel the graph today (no Redis cancellation yet).
- Frontend `useConsole` accumulates chunks; partial timeline preserved on error.

## Local Validation

```bash
pytest tests/ -q -k "not live"
curl -s http://localhost:8000/health
cd app/frontend && npm run build
```

## Known Failure Modes

| Symptom | Likely cause | Recovery |
| --- | --- | --- |
| 409 on `/resume` | Thread not HITL | Start with `human_in_the_loop: true` |
| 504 on `/run` | `timeout_seconds` exceeded | Increase timeout or reduce `max_rounds` |
| Empty audit rows | No Postgres pool | Expected in SQLite-only dev |
| MCP tools missing | Package or config | `pip install -e ".[mcp]"`, set `HARNESS_MCP_ENABLED` |
| RAG recall empty | Index not built | `python -m rag.ingest --source ./docs` |
| `skill_eligible: false` | Score &lt; 80 or rounds &lt; 1 | Continue loops or resume after stronger pass |
| Stream stalls | LLM provider down | Check `LLM_PROVIDER` and API keys |

## Future Work

- Redis-backed run cancellation between graph steps
- Structured logging with `thread_id` correlation
- Docker Compose healthchecks
- Request-level circuit breaker for LLM provider

CI/CD: [`CICD.md`](CICD.md). API detail: [`IMPLEMENTATION.md`](IMPLEMENTATION.md).
