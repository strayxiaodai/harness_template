# Asyncio In This Harness

The harness is async end-to-end: FastAPI handlers, LangGraph `ainvoke` /
`astream`, LLM calls, tool execution, and Postgres pools all run on asyncio
event loops.

## Where Async Shows Up

| Layer | Pattern | Example |
| --- | --- | --- |
| FastAPI routes | `async def` handlers | `app/api/runs.py` |
| App lifespan | `asynccontextmanager` | `memory/checkpoint.py` `graph_lifespan` |
| LangGraph | `await graph.ainvoke(...)` | `app/db/graphs.py` |
| Streaming | `async for` over `graph.astream` | `app/services/harness.py` |
| LLM | `await call_llm(...)` with tenacity retry | `llm/retry.py` |
| Tools | `await tool.ainvoke(args)` | `agent/executor.py` |
| Audit | `await write_audit_event(...)` | `audit/logger.py` |
| Tests | `pytest-asyncio` strict mode | `pyproject.toml` |

## FastAPI Lifespan

Startup compiles both graphs and initializes RAG + optional MCP:

```python
@asynccontextmanager
async def graph_lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_rag_service()
    # open checkpointer, set pools, compile graph_auto + graph_step
    yield
    # shutdown MCP, close pools
```

**Example — lifespan failure:**

```text
CHECKPOINT_BACKEND=postgres without DATABASE_URL
→ RuntimeError at startup (API never serves /health as ok)
```

## Graph Invocation

```python
await invoke_with_timeout(
    graph,
    initial_state(body),
    {"configurable": {"thread_id": body.thread_id}},
    timeout_seconds=body.timeout_seconds,
)
```

Raises `TimeoutError` → HTTP 504 on `/run` and `/resume`.

## Streaming (SSE)

```python
async for chunk in graph.astream(initial, config, stream_mode="updates"):
    yield f"data: {json.dumps(chunk)}\n\n"
```

Each chunk is a dict keyed by node name, e.g. `{"planner": {"role": "planner", ...}}`.

## Testing Async Code

`pyproject.toml` sets `asyncio_mode = "strict"`. Mark async tests:

```python
@pytest.mark.asyncio
async def test_write_audit_event_skips_without_pool() -> None:
    await write_audit_event(...)
```

**Example — run async tests only:**

```bash
pytest tests/test_audit_logger.py tests/test_actioner.py -v
```

## Common Pitfalls

| Pitfall | Fix |
| --- | --- |
| Blocking call inside async node | Use async LLM/tool APIs or `asyncio.to_thread` |
| Forgetting `await` on `ainvoke` | Lint + pytest will catch hung tests |
| Mixing sync Postgres in async path | Use `psycopg_pool.AsyncConnectionPool` |
| SSE client timeout | Increase `timeout_seconds` on `RunRequest` |

## Related

- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — `/stream` API examples
- [`RELIABILITY.md`](RELIABILITY.md) — timeouts and failure modes
- [`LANGGRAPH.md`](LANGGRAPH.md) — async Postgres checkpointer
