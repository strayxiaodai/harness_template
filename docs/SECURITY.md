# Security

Secure defaults for this harness. Items marked **planned** are documented but
not implemented.

## Threat Model (local dev)

| Threat | Current mitigation | Gap |
| --- | --- | --- |
| Unauthenticated API abuse | Localhost assumption | **planned:** auth + rate limits |
| Workspace escape via tools | `is_relative_to(workspace)` in `read_file` | No write tools yet |
| MCP tool abuse | Operator configures `mcp/servers.json` | Review before shared deploy |
| Prompt injection via RAG | None | **planned:** recall guardrails |
| Secret leakage in git | `.env` gitignored | Document all env vars in `IMPLEMENTATION.md` |
| LLM key exposure | Env vars only | Never log request bodies with keys |

## Authentication And Authorization

**Current:** API routes are **unauthenticated**. Localhost development only.

**Planned:**

```text
Authorization: Bearer <token>
→ middleware on /run, /resume, /stream, /skills/*
```

Plus rate limiting on graph invocation endpoints and tightened CORS in production.

## Secrets And Environment Variables

| Variable | Secret? | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Yes | Required when `LLM_PROVIDER=anthropic` |
| `DATABASE_URL` | Yes | Contains credentials |
| `HARNESS_MCP_SERVERS` | May contain tokens | Inline JSON override |
| `LLM_PROVIDER` | No | `openai` \| `anthropic` \| `ollama` |
| `EXECUTOR_TOOLS` | No | Comma-separated allow-list |

**Example — local `.env` (never commit):**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# DATABASE_URL=postgresql://user:pass@localhost:5432/agents
```

Document new variables in [`IMPLEMENTATION.md`](IMPLEMENTATION.md) when added.

## Executor Tool Surface

Default allow-list: `read_file`, `list_dir` (read-only).

```python
# tools/code_tools.py — path traversal blocked
target = (workspace / path).resolve()
if not target.is_relative_to(workspace):
    raise ValueError("path escapes the workspace")
```

| Tool | Risk level | Enable |
| --- | --- | --- |
| `read_file` | Low | Default |
| `list_dir` | Low | Default |
| `search_knowledge_base` | Low | `EXECUTOR_TOOLS=...,search_knowledge_base` |
| `mcp__*__*` | **High** | `HARNESS_MCP_ENABLED=true` |

Review `mcp/servers.json` before enabling MCP in shared or production
environments.

## RAG And Prompt Injection

Retrieved memories are injected into planner/executor prompts without
sanitization today.

**Planned controls:**

- Max recall length per thread
- Delimiter fencing (`<memory>...</memory>`)
- Source attribution and importance threshold (partially in `config/settings.yaml`)

## Data Classification

| Data | Location | Sensitivity | Retention |
| --- | --- | --- | --- |
| Graph checkpoints | SQLite / Postgres | May contain task text, tool output | Until deleted |
| RAG document index | `data/rag/` (gitignored) | Ingested repo docs | Until re-ingest |
| Thread memories | FAISS or pgvector | Extracted from runs | Operator-managed |
| Distilled skills | `.cursor/skills/` | Version controlled | Git history |
| Audit events | Postgres `agent_audit_log` | Tool args may include paths | Operator-managed |

**Example — audit row may contain paths:**

```json
{"tool": "read_file", "args": {"path": "config/settings.yaml"}, "status": "ok"}
```

Redact sensitive paths in histories per [`HISTORY_GUIDE.md`](HISTORY_GUIDE.md).

## Supply Chain

See [`SUPPLY_CHAIN_SECURITY.md`](SUPPLY_CHAIN_SECURITY.md).

## Reporting

Open a private issue with the maintainer for security vulnerabilities. Do not
file public issues for undisclosed exploits.
