# Enterprise LangGraph Harness — Implementation

> **Onboarding:** start with [`README.md`](../README.md) and [`AGENTS.md`](../AGENTS.md).
> **Product/design:** [`PRODUCT.md`](PRODUCT.md), [`DESIGN.md`](DESIGN.md).
> **Process/ops:** [`docs/README.md`](README.md).

This document is the **as-built implementation guide**: graph loop, state, API,
RAG, skills, tools, and configuration. Each section includes a concrete example.

---

## Implementation Status

| Area | Status | Location |
|------|--------|----------|
| Agent loop (planner → executor → reviewer → actioner → memorize) | Implemented | `agent/`, `graph/` |
| Loop quality scoring + action-review HITL gate | Implemented | `agent/actioner.py` |
| RAG (hybrid retrieve, memory ingest, rerank, inject) | Implemented | `rag/`, `context/` |
| FastAPI `/run`, `/resume`, `/stream`, `/health` | Implemented | `app/api/` |
| Skill distillation + save eligibility gate | Implemented | `skills/`, `app/api/skills.py` |
| MCP executor tools | Implemented | `harness_mcp/` |
| SQLite checkpoints (default) / Postgres (optional) | Implemented | `memory/checkpoint.py` |
| React developer console | Implemented | `app/frontend/` |
| Audit logger (Postgres when pool set) | Implemented | `audit/logger.py` |
| Docker Compose stack | Planned | `docker-compose.yml` |

**Example — check what is running:**

```bash
curl -s http://localhost:8000/health | jq
# {"status":"ok"}
```

---

## Project Layout

```text
harness_template/
├── agent/           # LangGraph nodes
├── graph/           # builder, routing, state, schemas
├── rag/             # ingest, stores, retrieve, inject
├── app/             # FastAPI + React frontend
│   ├── api/         # /health, /run, /resume, /stream, /skills
│   ├── services/    # harness, snapshot, state
│   └── frontend/    # developer console (Vite :5173)
├── harness_mcp/     # MCP client for executor tools
├── skills/          # distill, store, eligibility
├── memory/          # checkpointer lifespan
├── docs/            # knowledge base (this file)
└── tests/           # pytest suite
```

**Example — list top-level packages from the executor:**

```bash
export EXECUTOR_TOOLS=read_file,list_dir
# Inside a graph run, executor may call:
# list_dir(path="agent")  →  ["actioner.py", "executor.py", ...]
```

### Import convention

Source modules live at the repository root. Tests register namespace aliases in
`tests/conftest.py` (e.g. `from app.graph.routing import route_after_action`).

---

## Architecture

### Agent loop

```text
planner → executor → reviewer → actioner → memorize → (route)
                ↑___________________|
```

One **round** = all five nodes. The actioner increments `rounds` and sets
`refine_from` from the reviewer. Memorize writes RAG memories before routing.

**Example — round 1 walkthrough:**

| Step | Node | Key state after |
|------|------|-----------------|
| 1 | `planner` | `plan: ["read IMPLEMENTATION.md", "summarize API"]` |
| 2 | `executor` | `execution`, `tool_calls`, `result` |
| 3 | `reviewer` | `approved: false`, `review.verdict: "fail"` |
| 4 | `actioner` | `rounds: 1`, `loop_score: 72`, `refine_from: "executor"` |
| 5 | `memorize` | `memory_cursor` advanced |
| 6 | route | → `executor` (same plan, new attempt) |

### Human-in-the-loop (HITL)

Two interrupt mechanisms:

1. **Node interrupts** — `interrupt_after` on `planner`, `executor`, `reviewer`,
   `memorize` when `human_in_the_loop: true`.
2. **Action-review interrupt** — actioner calls `interrupt()` when HITL is on
   and either pending memories exist or `loop_score >= 80`, so the operator can
   review memories and preview a skill from one pause.

Action-review memory candidates are stashed in-process by
`(thread_id, memory_cursor)` before interrupting. This keeps local/dev
checkpointer resumes idempotent when LangGraph re-enters the actioner from the
top; shared multi-process deployments need shared pending-memory storage.

**Example — start a HITL thread:**

```bash
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "hitl-demo",
    "task": "Review the harness API design",
    "max_rounds": 3,
    "human_in_the_loop": true
  }' | jq
```

```json
{
  "thread_id": "hitl-demo",
  "status": "awaiting_human",
  "approved": false,
  "needs_human": true,
  "next_action": "executor",
  "last_role": "planner",
  "rounds": 0,
  "max_rounds": 3,
  "skill_eligible": false,
  "skill_ineligible_reason": "Complete at least one harness loop..."
}
```

Resume with:

```bash
curl -s -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "hitl-demo"}' | jq
```

### Graph builder

```python
from langgraph.checkpoint.memory import MemorySaver
from graph.builder import compile_with_checkpointer

# Auto-run graph (no per-node pause)
graph_auto = compile_with_checkpointer(MemorySaver())

# HITL graph (pause after planner, executor, reviewer, memorize)
graph_step = compile_with_checkpointer(
    MemorySaver(),
    human_in_the_loop=True,
)
```

`HITL_PAUSE_NODES`: `planner`, `executor`, `reviewer`, `memorize`.

---

## Core State

Defined in `graph/state.py` as `AgentState`.

| Field | Purpose |
|-------|---------|
| `thread_id` | Stable thread identifier (mirrors LangGraph config) |
| `task` | User goal for this thread |
| `plan` | Current plan steps (`list[str]`) |
| `rounds` / `max_rounds` | Completed loops vs budget |
| `execution` | Serialized `ExecutorResult` |
| `review` | Serialized `ReviewResult` |
| `tool_calls` | Compact executor tool records |
| `approved` | Reviewer pass/fail |
| `refine_from` | `planner` \| `executor` \| `finish` |
| `loop_score` | 0–100 quality score from actioner |
| `skill_preview_ready` | `loop_score >= 80` |
| `skill_slug` / `skill_context` | Loaded skill playbook |
| `memory_cursor` | RAG ingest bookmark in `messages` |
| `memory_context` | Formatted recall block for prompts |

**Example — checkpoint values mid-run:**

```json
{
  "thread_id": "demo-1",
  "task": "Add request tracing to the API",
  "plan": [
    "Inspect app/api/runs.py",
    "Add middleware or dependency for trace IDs",
    "Document env vars in docs/IMPLEMENTATION.md"
  ],
  "rounds": 1,
  "max_rounds": 3,
  "role": "reviewer",
  "approved": false,
  "execution": {
    "summary": "Read runs.py; tracing not present yet.",
    "changes": ["Identified insertion point in app/core/app.py"],
    "risks": ["No test for trace header propagation"],
    "verification": ["curl /health still returns 200"]
  },
  "review": {
    "verdict": "fail",
    "reason": "No tracing middleware implemented",
    "suggested_step": "executor"
  },
  "tool_calls": [
    {
      "iteration": 0,
      "tool": "read_file",
      "args": {"path": "app/api/runs.py"},
      "status": "ok"
    }
  ],
  "loop_score": 0,
  "human_in_the_loop": false,
  "memory_context": "(no relevant memories)",
  "memory_cursor": 4
}
```

---

## Structured Schemas

Pydantic models in `graph/schemas.py`. Nodes use `llm.with_structured_output(...)`.

### PlanResult

```json
{
  "steps": [
    "Read docs/IMPLEMENTATION.md API section",
    "List existing /run request fields",
    "Propose tracing fields for RunResponse"
  ],
  "rationale": "Need API surface before implementation."
}
```

### ExecutorResult

```json
{
  "summary": "Mapped run endpoints and response schema.",
  "changes": ["Documented RunRequest/RunResponse in docs"],
  "risks": ["Examples may drift from Pydantic models"],
  "verification": ["pytest tests/test_api.py passes"]
}
```

### ReviewResult

```json
{
  "verdict": "pass",
  "reason": "API examples match app/schemas/run.py",
  "suggested_step": "finish"
}
```

### ActionScoreResult

```json
{
  "score": 85,
  "rationale": "Clear execution evidence and passing verification steps."
}
```

---

## Routing

`graph/routing.py` — `route_after_action` runs after `memorize`.

```python
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

**Example — routing scenarios:**

| `approved` | `rounds` | `max_rounds` | `refine_from` | Route |
|----------|----------|--------------|---------------|-------|
| `true` | 1 | 3 | `executor` | `finish` |
| `false` | 3 | 3 | `executor` | `finish` (budget) |
| `false` | 1 | 3 | `executor` | `executor` |
| `false` | 1 | 3 | `planner` | `planner` |
| `false` | 1 | 3 | `finish` | `finish` |

---

## Agent Nodes

| Node | LLM? | Key outputs |
|------|------|-------------|
| `planner_agent` | Yes | `plan`, `memory_context`, messages |
| `executor_agent` | Yes | `execution`, `result`, `tool_calls` |
| `reviewer_agent` | Yes | `approved`, `review` |
| `actioner_agent` | Yes (score) | `rounds`, `refine_from`, `loop_score`, `skill_preview_ready` |
| `memorize_agent` | Yes (extract) | `memory_cursor` |

**Example — planner return patch:**

```python
{
    "role": "planner",
    "plan": ["step 1", "step 2"],
    "memory_context": "Prior thread recalled: ...",
    "memory_context_round": 0,
    "messages": [AIMessage(content="Plan rationale: ...\nSteps: ...")],
}
```

**Example — actioner audit payload:**

```json
{
  "suggested_step": "executor",
  "approved": false,
  "loop_score": 85,
  "skill_preview_ready": true,
  "score_rationale": "Strong verification evidence.",
  "pending_memory_count": 1,
  "approved_memory_count": 1,
  "action_review_interrupted": true
}
```

When HITL is on and memories or a skill preview need review, the actioner
interrupt payload:

```json
{
  "kind": "action_review",
  "node": "actioner",
  "score": 85,
  "threshold": 80,
  "skill_preview_ready": true,
  "message": "Review memories before they are stored. Skill preview is available.",
  "memories": [
    {
      "id": "m0",
      "content": "User prefers focused pytest verification.",
      "memory_type": "preference",
      "importance": 0.8
    }
  ]
}
```

---

## HTTP API

Base URL: `http://localhost:8000`. Schemas: `app/schemas/`.

### `GET /health`

```bash
curl -s http://localhost:8000/health
```

```json
{"status": "ok"}
```

### `POST /run`

Run the graph to completion (auto graph) or until the next HITL interrupt.

**Request (`RunRequest`):**

```json
{
  "thread_id": "demo-1",
  "task": "Create a plan for adding request tracing",
  "plan": [],
  "max_rounds": 3,
  "timeout_seconds": 120,
  "human_in_the_loop": false,
  "skill_slug": null
}
```

Either `task` or `skill_slug` is required.

**Response (`RunResponse`) — complete:**

```json
{
  "thread_id": "demo-1",
  "status": "complete",
  "approved": true,
  "needs_human": false,
  "result": "Tracing plan documented in docs/IMPLEMENTATION.md",
  "next_action": null,
  "last_role": "memorize",
  "rounds": 1,
  "max_rounds": 3,
  "skill_eligible": true,
  "skill_ineligible_reason": null
}
```

**Example — run with a saved skill:**

```bash
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "skill-run-1",
    "task": "",
    "skill_slug": "add-request-tracing",
    "human_in_the_loop": true
  }' | jq
```

Skill body is injected into planner/executor prompts via `skills/inject.py`.

### `POST /resume`

Resume a HITL thread. Optional `overrides` patch checkpoint state first.

**Request:**

```json
{
  "thread_id": "hitl-demo",
  "timeout_seconds": 120,
  "overrides": {
    "plan": ["clarify requirements", "add tracing middleware"],
    "review": {
      "verdict": "fail",
      "reason": "Operator override: replan before execution",
      "suggested_step": "planner"
    }
  }
}
```

**Response — still paused:**

```json
{
  "thread_id": "hitl-demo",
  "status": "awaiting_human",
  "approved": false,
  "needs_human": true,
  "next_action": "executor",
  "last_role": "planner",
  "rounds": 0,
  "max_rounds": 3,
  "skill_eligible": false,
  "skill_ineligible_reason": "Complete at least one harness loop..."
}
```

Returns **409** if the thread was not started with `human_in_the_loop: true`.

### `POST /stream`

Server-Sent Events (`stream_mode="updates"`). Ends with a `final` snapshot.

```bash
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "stream-1", "task": "Review the architecture"}'
```

**Example SSE chunks:**

```text
data: {"planner": {"role": "planner", "plan": ["..."]}}

data: {"executor": {"role": "executor", "result": "...", "tool_calls": [...]}}

data: {"final": {"thread_id": "stream-1", "status": "complete", "approved": true, ...}}
```

On failure:

```text
data: {"error": "graph run timed out"}
```

### Skills API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/skills` | List distilled skills |
| `GET` | `/skills/{slug}` | Load one skill body |
| `POST` | `/skills/distill` | Thread → SKILL.md preview or save |
| `POST` | `/skills/save` | Persist a previewed draft |

**Eligibility** (`skills/eligibility.py`):

- `rounds >= 1` (one full loop completed)
- `execution` and `review` present
- `skill_preview_ready` (`loop_score >= 80`)

**Example — distill preview (no write):**

```bash
curl -s -X POST http://localhost:8000/skills/distill \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-1",
    "name": "add-request-tracing",
    "refine": true,
    "save": false
  }' | jq
```

```json
{
  "thread_id": "demo-1",
  "slug": "add-request-tracing",
  "path": null,
  "saved": false,
  "created": true,
  "refined": false,
  "description": "Add request tracing to the harness API",
  "name": "add-request-tracing",
  "body": "# Add request tracing\n\n...",
  "status": "complete"
}
```

**Example — save after preview:**

```bash
curl -s -X POST http://localhost:8000/skills/save \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-1",
    "slug": "add-request-tracing",
    "name": "add-request-tracing",
    "description": "Add request tracing to the API",
    "body": "# Add request tracing\n\n..."
  }' | jq
```

Writes to `.cursor/skills/<slug>/SKILL.md`.

---

## RAG

| Corpus | Index (default) | Index (postgres) |
|--------|-------------------|------------------|
| Documents | FAISS + BM25 under `data/rag/` | unchanged |
| Memories | FAISS under `data/rag/memory/` | `memory_entries` + pgvector |

### Read path (planner)

`context/pipeline.py`: rewrite → memory search → rerank → inject.

**Example — memory block in planner prompt:**

```text
Relevant memories:
- [thread demo-1] Prior run documented RunRequest fields in docs/IMPLEMENTATION.md
- [thread demo-1] Reviewer flagged missing trace ID in response

Task: Add request tracing...
```

### Write path (memorize)

`messages[memory_cursor:]` → LLM extract → embed → store.

**Example — ingest docs corpus:**

```bash
python -m rag.ingest --source ./docs
```

**Example — search documents from Python:**

```python
import asyncio
from rag.service import init_rag_service

init_rag_service()
svc = init_rag_service()
print(asyncio.run(svc.search_documents_text("checkpoint backends")))
```

### Doc search (executor tool)

Enable hybrid search in the executor:

```bash
export EXECUTOR_TOOLS=read_file,list_dir,search_knowledge_base
```

**Example tool result:**

```text
Retrieved documents:
- [docs/IMPLEMENTATION.md] Checkpoints (SQLite default) ...
- [docs/LANGGRAPH.md] CHECKPOINT_BACKEND=postgres ...
```

### RAG configuration

`config/settings.yaml` + environment:

| Variable | Purpose | Example |
|----------|---------|---------|
| `RAG_ENABLED` | Kill switch | `true` |
| `RAG_INDEX_DIR` | Index directory | `data/rag` |
| `EMBEDDING_PROVIDER` | `openai` or `ollama` | `ollama` |
| `EMBEDDING_MODEL` | Model name | `BGE-M3:latest` |
| `RAG_MEMORY_BACKEND` | `faiss` or `postgres` | `faiss` |
| `DATABASE_URL` | Postgres memory + audit | `postgresql://...` |
| `EXECUTOR_TOOLS` | Tool allow-list | `read_file,list_dir,search_knowledge_base` |

**Postgres memory pool (optional):**

```python
from rag.stores.memory_pg import set_memory_pool
set_memory_pool(audit_pool)  # same pool as audit logger
```

Apply `migrations/002_rag_memory.sql` when using pgvector memory.

---

## Executor Tools

| Tool | Default | Description |
|------|---------|-------------|
| `read_file` | Yes | Read workspace file (max 128 KiB) |
| `list_dir` | Yes | List directory entries |
| `search_knowledge_base` | No | Hybrid doc search (RAG) |
| `mcp__{server}__{tool}` | When MCP enabled | External MCP tools |

**Example — read_file:**

```json
{"path": "app/schemas/run.py", "max_bytes": 4096}
```

**Example — list_dir:**

```json
{"path": "agent"}
```

→ `["actioner.py", "executor.py", "memorize.py", "planner.py", "reviewer.py"]`

Registry: `tools/registry.py`. Max tool iterations per executor pass: `5`.

---

## MCP Integration

External tools via Model Context Protocol. See [`mcp/README.md`](../mcp/README.md).

**Example — enable Context7:**

```bash
cp mcp/servers.example.json mcp/servers.json
export HARNESS_MCP_ENABLED=true
pip install -e ".[mcp]"
uvicorn app.main:app --reload --port 8000
```

**Example — registered tool name:**

```text
mcp__context7__resolve-library-id
```

MCP tools are auto-included in the executor allow-list when
`HARNESS_MCP_INCLUDE_ALL=true` (default).

---

## Audit Logging

`audit/logger.py` → `agent_audit_log` when a Postgres pool is set via
`set_audit_pool(pool)`. Without a pool, events are skipped at debug level.

**Example — write from executor:**

```python
await write_audit_event(
    thread_id=state["thread_id"],
    round_number=1,
    node="executor",
    event_type="tool_call",
    payload={"tool": "read_file", "status": "ok", "args": {"path": "IMPLEMENTATION.md"}},
)
```

**Example — SQL row:**

```sql
SELECT thread_id, node, event_type, payload->>'tool', created_at
FROM agent_audit_log
WHERE thread_id = 'demo-1'
ORDER BY created_at;
```

| `event_type` | Source |
|--------------|--------|
| `tool_call` | executor |
| `route_decision` | actioner |
| `rag_memory_write` | planned |
| `rag_memory_recall` | planned |

Migration: `migrations/001_create_agent_audit_log.sql`.

---

## Configuration

### LLM

```bash
export LLM_PROVIDER=openai          # openai | anthropic | ollama
export OPENAI_API_KEY=sk-...
# Ollama local:
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen3.6:27b
```

### Checkpoints

| Backend | Env | Storage |
|---------|-----|---------|
| SQLite (default) | — | `data/checkpoints/langgraph.db` |
| Memory | `CHECKPOINT_BACKEND=memory` | in-process (tests) |
| Postgres | `CHECKPOINT_BACKEND=postgres` + `DATABASE_URL` | shared DB |

**Example — SQLite dev (default):**

```bash
uvicorn app.main:app --reload --port 8000
# CHECKPOINT_SQLITE_PATH=data/checkpoints/langgraph.db  (optional override)
```

**Example — Postgres:**

```bash
pip install -r requirements-postgres.txt
export CHECKPOINT_BACKEND=postgres
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agents
uvicorn app.main:app --reload --port 8000
```

### Frontend (console)

```bash
cd app/frontend && npm install && npm run dev
# http://localhost:5173  →  API at http://localhost:8000
```

---

## Requirements

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt       # pytest + SQLite checkpoints
pip install -r requirements-rag.txt       # optional cross-encoder rerank
pip install -r requirements-postgres.txt  # pgvector + Postgres checkpoints
pip install -e ".[mcp]"                   # optional MCP client
```

---

## Running Locally

### Start stack

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Full curl walkthrough

```bash
# 1. Health
curl -s http://localhost:8000/health

# 2. Auto run
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w1","task":"Summarize docs/IMPLEMENTATION.md API section","max_rounds":2}'

# 3. HITL run + resume
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w2","task":"Review API","human_in_the_loop":true}'
curl -s -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w2"}'

# 4. Stream
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w3","task":"List agent nodes"}'

# 5. Skills
curl -s http://localhost:8000/skills
curl -s http://localhost:8000/skills/my-skill-slug
```

---

## Testing

```bash
pytest tests/ -q -k "not live"
pytest tests/test_api.py -v
pytest tests/test_graph.py -v
```

| File | Covers |
|------|--------|
| `test_api.py` | `/health`, `/run`, `/resume`, `/stream`, skill eligibility |
| `test_graph.py` | routing, workflow compile |
| `test_actioner.py` | rounds, loop score, skill preview interrupt |
| `test_planner.py` / `test_executor.py` / `test_reviewer.py` | node outputs |
| `test_rag_*.py` / `test_memory_pipeline.py` | RAG read/write |
| `test_mcp.py` | MCP tool registration |
| `test_skills_*.py` | distill, inject, eligibility |

**Example — run one node test file:**

```bash
pytest tests/test_actioner.py -v
```

Integration tests (`@pytest.mark.integration`) require external services and are
excluded by `-k "not live"`.

---

## Planned Infrastructure

- Docker Compose: Postgres, Redis, API healthchecks
- `test_compose_integration.py`

## Production Notes

- Authentication and rate limiting on API routes
- Prompt-injection guardrails on retrieved memories
- Manifest validation at startup (embedding model vs index)
- Shared Postgres pool for audit + pgvector memory
- CI: pytest gate, lint, type checking

## Roadmap

1. Docker Compose and integration tests
2. RAG audit events (`rag_memory_write`, `rag_memory_recall`)
3. Redis-backed cancellation between graph steps
4. Authentication and rate limiting on API routes
