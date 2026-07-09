# References

Curated external and in-repo references for agents. Prefer short, durable
notes over large vendor dumps.

## In-Repo Technical References

| Doc | Topic |
| --- | --- |
| [`IMPLEMENTATION.md`](../IMPLEMENTATION.md) | Full harness API, RAG, agents, configuration (as-built) |
| [`LANGGRAPH.md`](../LANGGRAPH.md) | Checkpoint backends |
| [`ASYNCIO.md`](../ASYNCIO.md) | Async patterns in this codebase |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Repository layout |
| [`mcp/README.md`](../../mcp/README.md) | MCP server configuration |

## External References (starting points)

| Topic | Link | Use when |
| --- | --- | --- |
| LangGraph | https://langchain-ai.github.io/langgraph/ | HITL interrupts, checkpointers, `astream` |
| LangGraph persistence | https://langchain-ai.github.io/langgraph/concepts/persistence/ | SQLite vs Postgres savers |
| FastAPI | https://fastapi.tiangolo.com/ | Lifespan, dependency injection |
| FastAPI SSE | https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse | `/stream` pattern |
| Pydantic v2 | https://docs.pydantic.dev/latest/ | `app/schemas/` models |
| MCP spec | https://modelcontextprotocol.io/ | `harness_mcp/` integration |
| Harness engineering (OpenAI) | https://openai.com/index/harness-engineering/ | Methodology context |
| Upstream template | https://github.com/iFurySt/harness-template | Agent-first repo scaffolding |

## Good Candidates To Add Here

- Curated excerpt: LangGraph `interrupt_after` vs `interrupt()` usage
- Ollama embedding setup for `config/settings.yaml` defaults
- pgvector dimension alignment with `RAG_MEMORY_EMBEDDING_DIM`

## Avoid

- Copying full framework manuals into the repo
- Duplicating [`IMPLEMENTATION.md`](../IMPLEMENTATION.md) configuration tables
- Stale links without a last-verified date (add date when copying excerpts)

**Example — adding a reference note:**

```markdown
## LangGraph interrupt_after (verified 2026-07)

interrupt_after pauses *after* named nodes complete; resume with null input.
See graph/builder.py compile_with_checkpointer(human_in_the_loop=True).
```
