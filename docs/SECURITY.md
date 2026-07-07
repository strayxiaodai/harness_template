# Security

Secure defaults for this harness. Several items are documented but not yet
implemented — see gaps below.

## Authentication And Authorization

**Current state:** API routes are **unauthenticated**. Suitable for localhost
development only.

**Target state:**

- API key or token middleware on `/run`, `/resume`, `/stream`, and `/skills`
- Rate limiting on graph invocation endpoints
- CORS restricted to known origins in production

## Secrets And Environment Variables

- Never commit `.env` (gitignored).
- Required secrets: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or Ollama config
  depending on `LLM_PROVIDER`.
- `DATABASE_URL` when using Postgres checkpoints, audit, or pgvector memory.
- MCP server env vars per `mcp/servers.example.json`.

Document new env vars in [`doc.md`](../doc.md) when added.

## Executor Tool Surface

Default allow-list is read-only: `read_file`, `list_dir`.

- Paths are constrained to the workspace (`tools/code_tools.py`).
- `search_knowledge_base` is opt-in via `EXECUTOR_TOOLS`.
- MCP tools are included when `HARNESS_MCP_INCLUDE_ALL=true` (default).

**Risk:** MCP tools execute external capabilities. Review `mcp/servers.json`
before enabling in shared environments.

## RAG And Prompt Injection

- Retrieved memories are injected into planner prompts without content
  sanitization today.
- **Planned:** guardrails on memory recall (length limits, delimiter fencing,
  source attribution).

## Data Classification

| Data | Location | Retention |
| --- | --- | --- |
| Graph state / checkpoints | SQLite or Postgres | Per thread until deleted |
| RAG documents | `data/rag/` (gitignored) | Until re-ingest |
| Distilled skills | `.cursor/skills/` | Version controlled |
| Audit events | Postgres `agent_audit_log` | Operator-managed |

## Supply Chain

See [`SUPPLY_CHAIN_SECURITY.md`](SUPPLY_CHAIN_SECURITY.md) for dependency
scanning and provenance guidance.

## Reporting

For security issues, follow repository maintainer contact once
[`SECURITY.md`](../SECURITY.md) policy file is added at repo root (upstream
template pattern). Until then, use private maintainer channels.
