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
| Agent loop (planner → executor → learner → actioner) | Implemented | `agent/`, `graph/` |
| Loop quality scoring + action-review HITL gate | Implemented | `agent/actioner.py` |
| RAG (hybrid retrieve, memory ingest, rerank, inject) | Implemented | `rag/`, `context/` |
| FastAPI `/run`, `/resume`, `/stream`, `/health` | Implemented | `app/api/` |
| Thread artifact list (`GET /threads`) + StatusBar attach | Implemented | `app/api/threads.py`, `app/services/thread_artifacts.py` |
| Skill distillation + save eligibility gate | Implemented | `skills/`, `app/api/skills.py`, `app/skills/` |
| Thread run artifacts (stage markdown) | Implemented | `app/services/thread_artifacts.py`, `app/threads/` |
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
├── agent/           # LangGraph nodes + HITL helpers
│   ├── planner.py / executor.py / learner.py / actioner.py / memorize.py
│   ├── memory_review.py   # action_review resume mapping + pending stash
│   └── clarification.py   # shared clarification helper (not yet wired into nodes)
├── graph/           # builder, routing, state, schemas
├── rag/             # ingest, stores, retrieve, inject
│   └── ingest/memory_extract.py  # extract_memory_candidates / commit_approved_memories
├── app/             # FastAPI + React frontend
│   ├── api/         # /health, /run, /resume, /stream, /skills, /threads
│   ├── services/    # harness, snapshot, state, thread_artifacts, resume_overrides
│   ├── skills/      # distilled playbooks (`<slug>/SKILL.md`); tracked
│   ├── threads/     # per-thread stage markdown (gitignored; created at runtime)
│   └── frontend/    # developer console (Vite :5173)
├── harness_mcp/     # MCP client for executor tools
├── skills/          # distill, store, eligibility (library code; not the on-disk store)
├── memory/          # checkpointer lifespan
├── docs/            # knowledge base (this file)
└── tests/           # pytest suite
```

**Example — list top-level packages from the executor:**

```bash
export EXECUTOR_TOOLS=read_file,list_dir,write_thread_file,read_thread_file
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
planner → executor → learner → actioner → (route)
                ↑___________________|
```

One **round** = planner → executor → learner → actioner. The actioner increments
`rounds`, sets `refine_from` from the learner, and on pass scores / HITL /
commits memories before routing to `planner` or `END`. On fail it soft-skips
(score 0, no commit) and still routes.

Ownership of memory write (all inside actioner on the pass path):

| Step | Memory role |
|------|-------------|
| Extract / merge | `learning_candidates` ∪ `extract_memory_candidates` |
| Optional HITL | `action_review` interrupt → `approved_memories` |
| Commit | `commit_round_memories` upserts, advances cursor, clears lists |

**Example — round 1 walkthrough:**

| Step | Node | Key state after |
|------|------|-----------------|
| 1 | `planner` | `plan: ["read IMPLEMENTATION.md", "summarize API"]` |
| 2 | `executor` | `execution`, `tool_calls`, `result` |
| 3 | `learner` | `approved: false`, `learning.verdict: "fail"`, lessons |
| 4 | `actioner` | soft-skip or score+HITL+commit; `refine_from: "planner"` or `"finish"` |
| 5 | route | → `planner` or `END` |

### Human-in-the-loop (HITL)

Two interrupt mechanisms:

1. **Node interrupts** — `interrupt_after` on `planner`, `executor`, and
   `learner` when `human_in_the_loop: true`. Memory commit runs inside actioner;
   it commits approved memories after the actioner returns.
2. **Action-review interrupt** — actioner calls in-node `interrupt()` when HITL
   is on and either pending memories exist or `loop_score >= 80`, so the
   operator can review/edit memories and see skill-preview readiness in one
   pause. During this pause, checkpoint `next` is typically still `actioner`
   and `snapshot.interrupts[0].value.kind == "action_review"`.

Action-review candidates (and the loop score shown in the interrupt) are
stashed in-process by `(thread_id, memory_cursor)` before interrupting
(`agent/memory_review.py`). That keeps local/dev checkpointer resumes
idempotent when LangGraph re-enters the actioner from the top — pending rows
and score are reused instead of re-extracting / re-scoring. Shared
multi-process deployments need shared pending-memory storage.

`ask_clarification()` in `agent/clarification.py` is a reusable
`kind: clarification` helper for structured Q&A pauses. It is **not** wired
into planner / executor / learner / actioner structured outputs in the current
tree (schemas and nodes omit clarification fields). The console still has a
Workplace surface for clarification payloads if emitted.

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

Resume a **node-boundary** pause with a bare thread id (no `interrupt_resume`):

```bash
curl -s -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "hitl-demo"}' | jq
```

For an **action-review** dynamic interrupt, pass `interrupt_resume` (see
`POST /resume` below).

### Graph builder

```python
from langgraph.checkpoint.memory import MemorySaver
from graph.builder import compile_with_checkpointer

# Auto-run graph (no per-node pause)
graph_auto = compile_with_checkpointer(MemorySaver())

# HITL graph (pause after planner, executor, learner)
graph_step = compile_with_checkpointer(
    MemorySaver(),
    human_in_the_loop=True,
)
```

`HITL_PAUSE_NODES`: `planner`, `executor`, `learner`. Actioner uses in-node
`interrupt()` for `action_review` on the pass path; soft-skips on fail without
`interrupt_after`.

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
| `learning` | Serialized `LearningResult` verdict + lessons |
| `learning_candidates` | Learner-proposed memory rows for actioner merge |
| `tool_calls` | Compact executor tool records |
| `approved` | Learner pass/fail |
| `refine_from` | `planner` \| `finish` |
| `loop_score` | 0–100 quality score from actioner |
| `skill_preview_ready` | `loop_score >= 80` |
| `skill_slug` / `skill_context` | Loaded skill playbook |
| `memory_cursor` | RAG ingest bookmark in `messages` |
| `memory_context` | Formatted recall block for prompts |
| `pending_memories` | Actioner-extracted candidates awaiting HITL review |
| `approved_memories` | Candidate memories approved for actioner commit |

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
  "role": "learner",
  "approved": false,
  "execution": {
    "summary": "Read runs.py; tracing not present yet.",
    "changes": ["Identified insertion point in app/core/app.py"],
    "risks": ["No test for trace header propagation"],
    "verification": ["curl /health still returns 200"]
  },
  "learning": {
    "verdict": "fail",
    "reason": "No tracing middleware implemented",
    "suggested_step": "planner"
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

Executor and learner run a tool-calling phase, then a **fresh** structured
summarize call. The summarize prompt uses plain-text tool evidence rather than
live `ToolMessage` / tool-call `AIMessage` rows — otherwise Ollama's default
`json_schema` method often keeps emitting tool calls (empty content) and
raises LangChain `OUTPUT_PARSING_FAILURE`.

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

`graph/routing.py` — `route_after_action` runs after `actioner`
(`planner`|`finish` only). Soft-skip / finish prefer `learning.verdict` via
`learning_passed(state)` so a stale top-level `approved` bit cannot disagree
with an operator learning override.

```python
def route_after_action(state: AgentState) -> ActionRoute:
    if learning_passed(state):
        return "finish"
    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"
    refine_from = state.get("refine_from", "planner")
    if refine_from == "finish":
        return "finish"
    # planner, legacy executor, or unknown → planner
    return "planner"
```

`DEFAULT_MAX_ROUNDS = 3`.

**Example — routing scenarios:**

| `learning.verdict` / `approved` | `rounds` | `max_rounds` | `refine_from` | Route |
|--------------------------------|----------|--------------|---------------|-------|
| pass (`approved` true) | 1 | 3 | `finish` | `finish` |
| fail | 3 | 3 | `planner` | `finish` (budget) |
| fail | 1 | 3 | `executor` (legacy) | `planner` |
| fail | 1 | 3 | `planner` | `planner` |
| fail | 1 | 3 | `finish` | `finish` |

---

## Agent Nodes

| Node | LLM? | Key outputs |
|------|------|-------------|
| `planner_agent` | Yes | `plan`, `memory_context`, messages |
| `executor_agent` | Yes | `execution`, `result`, `tool_calls` |
| `learner_agent` | Yes | `approved`, `learning`, `learning_candidates` |
| `actioner_agent` | Yes (score + extract + commit) | soft-skip on fail; on pass: score, HITL, `commit_round_memories` |
| `commit_round_memories` | No (helper) | Called by actioner after approve; advances cursor, clears lists |

Helpers used by those nodes:

| Helper | Module | Role |
|--------|--------|------|
| `learning_passed` | `graph/routing.py` | Soft-skip / route from `learning.verdict` (fallback `approved`) |
| `apply_resume_overrides` | `app/services/resume_overrides.py` | Merge learning lessons, sync `approved`, mirror `refine_from` → `suggested_step` |
| `extract_memory_candidates` | `rag/ingest/memory_extract.py` | Extract + filter + id (`m0`…) — **no store** |
| `map_resume_to_approved` / `stash_pending` / `load_score` | `agent/memory_review.py` | HITL resume mapping; pending + score cache for interrupt re-entry |
| `commit_approved_memories` | `rag/ingest/memory_extract.py` | Embed + upsert approved rows; clear pending/approved |

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
  "suggested_step": "planner",
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
  "last_role": "actioner",
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

**How the harness chooses resume input** (`app/services/harness.py`):

| Condition | Graph input |
|-----------|-------------|
| `interrupt_resume` present | `Command(resume=interrupt_resume)` |
| Else active `snapshot.interrupts` | `Command(resume=True)` (bare continue / keep-all for action review) |
| Else node-boundary pause only | `None` (continue after `interrupt_after`) |

**Overrides** are normalized via `apply_resume_overrides` before
`aupdate_state`: learning patches **merge** onto existing lessons (not
replace), `approved` syncs from `learning.verdict`, and `refine_from` also
updates `learning.suggested_step` so the actioner keeps the operator's route
choice. Soft-skip / routing also prefer `learning.verdict` over a stale
`approved` bit.

**Node-boundary resume** — omit `interrupt_resume` (or pass `null`) when paused
after planner / executor / learner. A bare `{ "thread_id": "..." }` works.

**Dynamic interrupt resume** — when paused inside actioner on `action_review`,
pass `interrupt_resume` with the operator's memory decisions. Prefer an
explicit memories list from the console; bare resume still **keeps all**
pending candidates. Clarification pauses (when emitted) resume with
`interrupt_resume: { "answers": [...] }` — do not send answers as a top-level
`ResumeRequest` field.

`RunResponse.interrupt` carries the active dynamic-interrupt payload (for
example `kind: "action_review"` with pending memories) so the console can
render Workplace without reading the raw checkpoint snapshot.

| `interrupt_resume` | Effect on pending memories |
| --- | --- |
| omitted / `null` / `{}` / missing `memories` | **Keep all** pending candidates as extracted |
| `{ "memories": [] }` | Store nothing |
| `{ "memories": [...] }` | Per-id keep / edit / drop (see example) |

**Request — node-boundary with overrides:**

```json
{
  "thread_id": "hitl-demo",
  "timeout_seconds": 120,
  "overrides": {
    "plan": ["clarify requirements", "add tracing middleware"],
    "learning": {
      "verdict": "fail",
      "reason": "Operator override: replan before execution",
      "suggested_step": "planner"
    }
  }
}
```

**Request — action-review keep / edit / drop:**

```json
{
  "thread_id": "hitl-demo",
  "interrupt_resume": {
    "memories": [
      {
        "id": "m0",
        "keep": true,
        "content": "User prefers focused pytest verification.",
        "memory_type": "preference",
        "importance": 0.9
      },
      { "id": "m1", "keep": false }
    ]
  }
}
```

Resume rows with `keep: true` may override `content`, `memory_type`, and
`importance`; pending ids omitted from `memories` are dropped when any array was
sent.

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
| `GET` | `/threads` | List on-disk thread artifacts (`app/threads/`) for console attach |
| `GET` | `/skills` | List distilled skills |
| `GET` | `/skills/{slug}` | Load one skill body |
| `POST` | `/skills/distill` | Thread → SKILL.md preview or save |
| `POST` | `/skills/save` | Persist a previewed draft |

**Eligibility** (`skills/eligibility.py`):

- `rounds >= 1` (one full loop completed)
- `execution` and/or `learning` present
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

Writes to `app/skills/<slug>/SKILL.md` (override with `HARNESS_SKILLS_DIR`).

### Thread run artifacts

On `POST /run` or `POST /stream` (Start thread / skill-run),
`app/services/harness.py` calls `app/services/thread_artifacts.py` to create a
local folder keyed by the Command → Task text (slugified via
`skills.store.slugify`). Skill-only starts with an empty task use `skill_slug`
as the label.

```text
app/threads/
  .index.json                 # thread_id → slug
  <task-slug>/
    meta.json                 # thread_id, task, slug, started_at, plan
    planner.md
    executor.md
    learner.md
    actioner.md
```

Collision: if `<task-slug>/` already exists, the folder becomes
`<task-slug>-<thread_id[:8]>` (hyphens stripped from the id prefix).

Each stage markdown records **status** (`pending` | `running` | `paused` |
`complete` | `error`) and **contents** for that node. Multi-round runs append
`## Round N` sections (same round rewritten; older rounds preserved).

**Example — `planner.md` after round 1:**

```markdown
# planner

- status: complete
- round: 1
- updated_at: 2026-07-14T06:12:00+00:00

## Round 1

### Contents

- plan:
  - read IMPLEMENTATION.md
  - summarize API
- memory_context:
  _(none)_
```

| Event | Write |
|-------|--------|
| Start `/run` or `/stream` | mkdir + `meta.json` + four `.md` (`pending`) + index entry |
| Stream `updates` chunk for a stage node | update that node's `.md` |
| Final snapshot / `/run` return | refresh all four from response fields |
| `/resume` | lookup via `.index.json`; refresh (skip quietly if no index entry) |

Disk failures are logged and **never** fail the graph run. Public list-only API:
`GET /threads` returns summaries from `.index.json` + each `meta.json`
(`thread_id`, `task`, `slug`, `started_at`, `plan`). Stage markdown remains
file-inspect only (no browse/edit routes).

**Console attach:** StatusBar thread picker loads `GET /threads`, then sets
`thread_id` + Task + Plan from the selected summary without hydrating the
LangGraph checkpoint or wiping the timeline. Resume/Distill still use the
existing `/resume` and skills paths when a checkpoint exists.

| Env | Default | Purpose |
|-----|---------|---------|
| `HARNESS_THREADS_DIR` | `app/threads` | Artifact root (tests / custom path) |
| `HARNESS_SKILLS_DIR` | `app/skills` | Distilled skills root |

The whole `app/threads/` tree is gitignored (local pickup only). Distilled
skills under `app/skills/<slug>/SKILL.md` (+ `harness.json`) are tracked.
Do not add `app/skills/__init__.py` — it is a data directory, not a package.
Cursor agent skills under `.cursor/skills/` (e.g. impeccable) are unrelated.

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
- [thread demo-1] Learner flagged missing trace ID in response

Task: Add request tracing...
```

### Write path (actioner commit)

1. **Score / soft-skip (actioner)** — fail path soft-skips when
   `learning_passed` is false (score 0, no HITL/commit). Pass path scores once;
   on `action_review` interrupt, score + pending are stashed so LangGraph
   re-entry reuses them instead of re-scoring.
2. **Extract (actioner, pass)** — merge `learning_candidates` with
   `extract_memory_candidates(state)` from `messages[memory_cursor:]`, apply
   importance filter, assign stable ids (`m0`, `m1`, …); **no store** yet.
3. **Approve (actioner, pass)** —
   - HITL off (or no interrupt needed): `approved_memories = map_resume_to_approved(pending, True)`.
   - HITL on + (candidates **or** `skill_preview_ready`):
     `interrupt(kind="action_review")`, then map the resume value.
4. **Commit (actioner helper)** — `commit_round_memories` embeds/upserts only
   approved rows (skip store when empty), always advances `memory_cursor`, and
   clears `pending_memories` / `approved_memories`. RAG disabled or service
   missing uses the same soft-skip shape (cursor advanced + lists cleared).

**Example — action-review resume keeps one edited memory and drops one:**

```json
{
  "thread_id": "hitl-demo",
  "interrupt_resume": {
    "memories": [
      {
        "id": "m0",
        "keep": true,
        "content": "User prefers focused pytest verification.",
        "memory_type": "preference",
        "importance": 0.9
      },
      { "id": "m1", "keep": false }
    ]
  }
}
```

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
| `EXECUTOR_TOOLS` | Tool allow-list | `read_file,list_dir,write_thread_file,read_thread_file` |
| `HARNESS_SCRIPT_IMAGE` | Docker image for learner script runs | `python:3.12-slim` |
| `HARNESS_SCRIPT_TIMEOUT_SECONDS` | Per-script Docker timeout | `30` |
| `HARNESS_SCRIPT_OUTPUT_BYTES` | Stdout/stderr cap per stream | `32768` |
| `HARNESS_DOCKER_BIN` | Docker CLI binary | `docker` |

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
| `write_thread_file` | Yes | Write `scripts/*.py` or `manifest.json` for the current thread |
| `read_thread_file` | Yes | Read under `app/threads/<slug>/` |
| `search_knowledge_base` | No | Hybrid doc search (RAG) |
| `mcp__{server}__{tool}` | When MCP enabled | External MCP tools |

**Learner-only tools** (not in `EXECUTOR_TOOLS`):

| Tool | Description |
|------|-------------|
| `run_thread_script` | Run a manifest-listed `.py` under `scripts/` inside Docker S2 (`--network=none`, read-only mount). No host-Python fallback. |

**Example — write_thread_file:**

```json
{"path": "validate.py", "content": "assert True\n"}
```

Writes to `app/threads/<slug>/scripts/validate.py`. Update `scripts/manifest.json` so the learner can run it.

**Example — run_thread_script (learner):**

```json
{"path": "validate.py"}
```

Registry: `tools/registry.py`. Max tool iterations per executor/learner pass: `5`.

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

### Skills and thread artifacts

| Env | Default | Purpose |
|-----|---------|---------|
| `HARNESS_SKILLS_DIR` | `app/skills` | Distilled skill library root |
| `HARNESS_THREADS_DIR` | `app/threads` | Per-thread stage markdown root (gitignored) |

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

Console layout and Workplace interrupt kinds are detailed in
[`FRONTEND.md`](FRONTEND.md). Workplace status tracks Command/StatusBar
`RunPhase` (ready / running / awaiting human / complete / error) when no step
is selected; GraphSpine owns the active-node indicator. For action review,
`useResumeDraft` seeds editable rows from `interrupt.value.memories` and
Continue sends `interrupt_resume: { memories: [...] }` (keep / drop / edit).
Clarification Continue sends `interrupt_resume: { answers: [...] }`. Distill /
skill preview controls stay in the Command column.

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

# 2. Auto run (also writes app/threads/<task-slug>/ stage markdown)
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w1","task":"Summarize docs/IMPLEMENTATION.md API section","max_rounds":2}'
ls app/threads/*/planner.md

# 3. HITL run + node-boundary resume (planner/executor/learner pause)
curl -s -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w2","task":"Review API","human_in_the_loop":true}'
curl -s -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w2"}'

# 3b. Action-review resume (when paused inside actioner)
curl -s -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id":"w2",
    "interrupt_resume":{
      "memories":[
        {"id":"m0","keep":true,"content":"Edited fact","memory_type":"fact","importance":0.8},
        {"id":"m1","keep":false}
      ]
    }
  }'

# 4. Stream
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"w3","task":"List agent nodes"}'

# 5. Threads + skills
curl -s http://localhost:8000/threads
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
| `test_api.py` | `/health`, `/run`, `/resume`, `/stream`, skill eligibility, learning override sync |
| `test_resume_overrides.py` | `apply_resume_overrides` merge / approved / refine_from |
| `test_graph.py` | routing (`learning_passed`), workflow compile, `HITL_PAUSE_NODES` (no memorize node) |
| `test_actioner.py` | soft-skip, score cache on re-entry, action-review interrupt, auto-approve, merge+commit |
| `test_action_review_api.py` | E2E: action_review → `/resume` keep/edit/drop → actioner commit |
| `test_planner.py` / `test_executor.py` / `test_learner.py` | node outputs |
| `test_memory_review.py` | `map_resume_to_approved` and pending/score stash helpers |
| `test_rag_*.py` / `test_memory_pipeline.py` | RAG read/write and approved-memory commit |
| `test_clarification.py` | clarification helper unit tests (helper not wired into agents yet) |
| `test_mcp.py` | MCP tool registration |
| `test_skills_*.py` | distill, inject, eligibility |
| `test_thread_artifacts.py` | `list_threads` F1–F9 + stage write helpers |
| `test_skills_store_root.py` | default `skills_root()` → `app/skills` |
| `test_thread_artifacts.py` | init, collision slug, stage markdown write, disk-error soft-fail |
| `test_harness_thread_artifacts.py` | run / stream / resume wiring into `app/threads/` |

**Example — HITL memory path:**

```bash
pytest tests/test_actioner.py tests/test_memory_review.py tests/test_action_review_api.py -v
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
