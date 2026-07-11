# Action-End Memory Review HITL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make memorization an actioner-owned option with HITL editable preview in the center Workplace, while memorize only commits approved memories.

**Architecture:** Split extract (candidates, no store) from commit (upsert). Actioner extracts into `pending_memories`, pauses once with `kind: action_review` when HITL and (candidates or skill-preview ready), maps resume → `approved_memories`. Memorize upserts approved rows, advances cursor, clears pending/approved. Frontend Workplace + resume draft send `interrupt_resume.memories`. Remove `memorize` from `HITL_PAUSE_NODES`.

**Tech Stack:** LangGraph `interrupt()`, existing RAG extract/store, FastAPI resume `interrupt_resume`, React Workplace / `useResumeDraft`.

**Spec:** [`docs/superpowers/specs/2026-07-11-action-review-memory-hitl-design.md`](../specs/2026-07-11-action-review-memory-hitl-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `rag/ingest/memory_extract.py` | `extract_memory_candidates`, `commit_approved_memories`; keep `run_memory_ingest` as thin wrapper or deprecate callers |
| `agent/memory_review.py` | `map_resume_to_approved`, `action_review_message`, interrupt payload builder |
| `agent/actioner.py` | Extract → optional `action_review` interrupt → set approved |
| `agent/memorize.py` | Commit `approved_memories` only; clear pending/approved |
| `graph/state.py` | `pending_memories`, `approved_memories` |
| `graph/builder.py` | Drop `memorize` from `HITL_PAUSE_NODES` |
| `app/frontend/src/lib/actionReview.ts` | Parse interrupt + draft helpers |
| `app/frontend/src/hooks/useResumeDraft.ts` | Memory drafts + `interrupt_resume` in payload |
| `app/frontend/src/hooks/useConsole.ts` | Pass `interrupt_resume` to `/resume` |
| `app/frontend/src/components/Workplace.tsx` | Action review panel |
| `docs/IMPLEMENTATION.md`, `ARCHITECTURE.md`, `FRONTEND.md` | Behavior sync |
| `docs/histories/2026-07/…` | History after code lands |

---

### Task 1: Candidate extract + resume mapping helpers

**Files:**
- Modify: `rag/ingest/memory_extract.py`
- Create: `agent/memory_review.py`
- Test: `tests/test_memory_pipeline.py`, `tests/test_memory_review.py`

- [ ] **Step 1: Write failing tests for extract candidates and resume map**

```python
# tests/test_memory_review.py
from __future__ import annotations

from agent.memory_review import map_resume_to_approved


def test_bare_resume_keeps_all_pending() -> None:
    pending = [
        {
            "id": "m0",
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]
    assert map_resume_to_approved(pending, True) == [
        {
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]


def test_empty_memories_stores_nothing() -> None:
    pending = [
        {
            "id": "m0",
            "content": "x",
            "memory_type": "fact",
            "importance": 0.5,
        },
    ]
    assert map_resume_to_approved(pending, {"memories": []}) == []


def test_keep_edit_and_drop() -> None:
    pending = [
        {
            "id": "m0",
            "content": "old",
            "memory_type": "fact",
            "importance": 0.5,
        },
        {
            "id": "m1",
            "content": "drop me",
            "memory_type": "fact",
            "importance": 0.5,
        },
    ]
    resume = {
        "memories": [
            {
                "id": "m0",
                "keep": True,
                "content": "new",
                "memory_type": "preference",
                "importance": 0.9,
            },
            {"id": "m1", "keep": False},
        ],
    }
    assert map_resume_to_approved(pending, resume) == [
        {
            "content": "new",
            "memory_type": "preference",
            "importance": 0.9,
        },
    ]


def test_omitted_id_when_list_provided_is_drop() -> None:
    pending = [
        {
            "id": "m0",
            "content": "a",
            "memory_type": "fact",
            "importance": 0.5,
        },
        {
            "id": "m1",
            "content": "b",
            "memory_type": "fact",
            "importance": 0.5,
        },
    ]
    resume = {"memories": [{"id": "m0", "keep": True, "content": "a"}]}
    assert map_resume_to_approved(pending, resume) == [
        {"content": "a", "memory_type": "fact", "importance": 0.5},
    ]
```

```python
# append to tests/test_memory_pipeline.py
@pytest.mark.asyncio
async def test_extract_memory_candidates_does_not_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = RagSettings(
        enabled=True,
        index_dir=tmp_path / "rag",  # type: ignore[operator]
    )
    state = _state(
        messages=[HumanMessage(content="I prefer pytest")],
        memory_cursor=0,
    )
    monkeypatch.setattr(
        memory_extract_module,
        "extract_memories",
        AsyncMock(
            return_value=ExtractionResult(
                memories=[
                    ExtractedMemory(
                        content="User prefers pytest",
                        memory_type="preference",
                        importance=0.9,
                    ),
                ],
            ),
        ),
    )
    store = MemoryStore()
    candidates = await memory_extract_module.extract_memory_candidates(
        state,
        settings=settings,
    )
    assert candidates == [
        {
            "id": "m0",
            "content": "User prefers pytest",
            "memory_type": "preference",
            "importance": 0.9,
        },
    ]
    assert store._entries == {} or len(await store.search("test-thread", [0.0] * 32, top_k=5)) == 0
```

(If `MemoryStore` has no `_entries`, assert search with a fake embedding returns empty instead.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_review.py tests/test_memory_pipeline.py::test_extract_memory_candidates_does_not_store -v`  
Expected: FAIL (import / missing symbol)

- [ ] **Step 3: Implement helpers**

```python
# agent/memory_review.py
"""Map HITL action-review resume payloads to approved memories."""

from __future__ import annotations

from typing import Any

MEMORY_TYPES = frozenset({"fact", "preference", "entity", "summary"})


def action_review_message(
    *,
    has_memories: bool,
    skill_preview_ready: bool,
) -> str:
    """Pick interrupt message copy from the design matrix."""
    if has_memories and skill_preview_ready:
        return (
            "Review memories before they are stored. "
            "Skill preview is available."
        )
    if has_memories:
        return "Review memories before they are stored."
    return (
        "Loop score qualifies for skill preview. "
        "Nothing to store this round."
    )


def map_resume_to_approved(
    pending: list[dict[str, Any]],
    resume_value: Any,
) -> list[dict[str, Any]]:
    """Apply keep/drop/edit rules from the action_review resume value."""
    if resume_value is True or resume_value is None:
        return [_strip_id(item) for item in pending]
    if not isinstance(resume_value, dict):
        return [_strip_id(item) for item in pending]
    if "memories" not in resume_value:
        return [_strip_id(item) for item in pending]

    raw_list = resume_value.get("memories")
    if not isinstance(raw_list, list):
        return [_strip_id(item) for item in pending]
    if len(raw_list) == 0:
        return []

    by_id = {
        str(row.get("id")): row
        for row in raw_list
        if isinstance(row, dict) and row.get("id") is not None
    }
    approved: list[dict[str, Any]] = []
    for item in pending:
        mid = str(item.get("id", ""))
        row = by_id.get(mid)
        if row is None or not row.get("keep"):
            continue
        content = str(row.get("content", item.get("content", ""))).strip()
        if not content:
            continue
        memory_type = str(row.get("memory_type", item.get("memory_type", "fact")))
        if memory_type not in MEMORY_TYPES:
            memory_type = str(item.get("memory_type", "fact"))
        try:
            importance = float(row.get("importance", item.get("importance", 0.5)))
        except (TypeError, ValueError):
            importance = float(item.get("importance", 0.5))
        importance = max(0.0, min(1.0, importance))
        approved.append(
            {
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
            },
        )
    return approved


def _strip_id(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": str(item.get("content", "")),
        "memory_type": str(item.get("memory_type", "fact")),
        "importance": float(item.get("importance", 0.5)),
    }
```

```python
# rag/ingest/memory_extract.py — add:

async def extract_memory_candidates(
    state: AgentState,
    *,
    settings: RagSettings | None = None,
) -> list[dict[str, object]]:
    """Extract filtered memory candidates without writing to the store."""
    cfg = settings or load_rag_settings()
    if not cfg.enabled:
        return []
    cursor = state.get("memory_cursor", 0)
    new_messages = collect_new_messages(state["messages"], since_index=cursor)
    if not new_messages:
        return []
    extracted = await extract_memories(new_messages)
    filtered = [
        memory
        for memory in extracted.memories
        if memory.importance >= cfg.extract.min_importance
    ]
    return [
        {
            "id": f"m{index}",
            "content": memory.content,
            "memory_type": memory.memory_type,
            "importance": memory.importance,
        }
        for index, memory in enumerate(filtered)
    ]


async def commit_approved_memories(
    state: AgentState,
    *,
    memory_store: MemoryStore,
    settings: RagSettings | None = None,
) -> dict[str, object]:
    """Upsert approved_memories and advance memory_cursor."""
    from rag.schemas import ExtractedMemory

    cfg = settings or load_rag_settings()
    cursor_update = {"memory_cursor": len(state.get("messages", []))}
    raw = state.get("approved_memories") or []
    if not isinstance(raw, list) or not raw:
        return {
            **cursor_update,
            "pending_memories": [],
            "approved_memories": [],
        }

    memories: list[ExtractedMemory] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        memories.append(
            ExtractedMemory(
                content=content,
                memory_type=item.get("memory_type", "fact"),  # type: ignore[arg-type]
                importance=float(item.get("importance", 0.5)),
            ),
        )
    if not memories:
        return {
            **cursor_update,
            "pending_memories": [],
            "approved_memories": [],
        }

    embeddings = get_embeddings(cfg)
    await memory_store.upsert_memories(
        state["thread_id"],
        memories,
        embeddings,
    )
    memory_store.save(cfg.index_dir)
    return {
        **cursor_update,
        "pending_memories": [],
        "approved_memories": [],
    }
```

Refactor `run_memory_ingest` to: extract candidates → set temporary approved without ids → `commit_approved_memories` **or** leave it for tests and switch memorize to `commit_approved_memories` only (preferred). Update existing ingest tests if behavior of `run_memory_ingest` changes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_review.py tests/test_memory_pipeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rag/ingest/memory_extract.py agent/memory_review.py tests/test_memory_review.py tests/test_memory_pipeline.py
git commit -m "Add memory candidate extract and action-review resume mapping."
```

---

### Task 2: State fields + memorize commit-only

**Files:**
- Modify: `graph/state.py`
- Modify: `agent/memorize.py`
- Test: `tests/test_memory_pipeline.py`

- [ ] **Step 1: Write failing memorize commit tests**

```python
@pytest.mark.asyncio
async def test_memorize_commits_approved_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent import memorize as memorize_module

    mock_service = MagicMock()
    mock_service.memory_store = MemoryStore()
    mock_service.save_memory_store = MagicMock()
    commit = AsyncMock(
        return_value={
            "memory_cursor": 2,
            "pending_memories": [],
            "approved_memories": [],
        },
    )
    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(memorize_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(memorize_module, "commit_approved_memories", commit)

    state = _state(
        messages=[HumanMessage(content="hi"), AIMessage(content="ok")],
        approved_memories=[
            {
                "content": "User said hi",
                "memory_type": "fact",
                "importance": 0.7,
            },
        ],
        pending_memories=[{"id": "m0", "content": "x"}],
    )
    result = await memorize_module.memorize_agent(state)
    assert result["role"] == "memorize"
    assert result["memory_cursor"] == 2
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_memorize_skips_store_when_approved_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent import memorize as memorize_module

    mock_service = MagicMock()
    mock_service.save_memory_store = MagicMock()
    commit = AsyncMock(
        return_value={
            "memory_cursor": 1,
            "pending_memories": [],
            "approved_memories": [],
        },
    )
    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(memorize_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(memorize_module, "commit_approved_memories", commit)

    result = await memorize_module.memorize_agent(
        _state(messages=[HumanMessage(content="x")], approved_memories=[]),
    )
    assert result["memory_cursor"] == 1
    mock_service.save_memory_store.assert_called_once()
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_memory_pipeline.py::test_memorize_commits_approved_only tests/test_memory_pipeline.py::test_memorize_skips_store_when_approved_empty -v`

- [ ] **Step 3: Update state + memorize**

```python
# graph/state.py — add to AgentState:
    pending_memories: NotRequired[list[dict[str, object]]]
    approved_memories: NotRequired[list[dict[str, object]]]
```

```python
# agent/memorize.py — use commit_approved_memories instead of run_memory_ingest;
# on failure still set memory_cursor + clear lists:
        return {
            "role": "memorize",
            "memory_cursor": len(state.get("messages", [])),
            "pending_memories": [],
            "approved_memories": [],
        }
```

Update `test_memorize_agent_runs_memory_ingest` to mock `commit_approved_memories`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_memory_pipeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add graph/state.py agent/memorize.py tests/test_memory_pipeline.py
git commit -m "Make memorize commit approved memories only."
```

---

### Task 3: Actioner extract + `action_review` interrupt

**Files:**
- Modify: `agent/actioner.py`
- Modify: `tests/test_actioner.py`

- [ ] **Step 1: Rewrite skill-preview interrupt test + add memory cases**

Replace `assert payload["kind"] == "skill_preview"` with `action_review`. Add:

```python
@pytest.mark.asyncio
async def test_actioner_interrupts_for_pending_memories_when_hitl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=40, rationale="low")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(
            return_value=[
                {
                    "id": "m0",
                    "content": "prefers pytest",
                    "memory_type": "preference",
                    "importance": 0.8,
                },
            ],
        ),
    )
    interrupt = MagicMock(return_value={"memories": []})
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)

    result = await actioner_module.actioner_agent(
        _state(human_in_the_loop=True),
    )

    interrupt.assert_called_once()
    payload = interrupt.call_args.args[0]
    assert payload["kind"] == "action_review"
    assert payload["memories"][0]["id"] == "m0"
    assert result["approved_memories"] == []
    assert result["pending_memories"][0]["id"] == "m0"


@pytest.mark.asyncio
async def test_actioner_auto_approves_when_hitl_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents import actioner as actioner_module

    pending = [
        {
            "id": "m0",
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]
    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=90, rationale="ok")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=pending),
    )
    interrupt = MagicMock()
    monkeypatch.setattr(actioner_module, "interrupt", interrupt)

    result = await actioner_module.actioner_agent(_state(human_in_the_loop=False))

    interrupt.assert_not_called()
    assert result["approved_memories"] == [
        {
            "content": "prefers pytest",
            "memory_type": "preference",
            "importance": 0.8,
        },
    ]
```

Also: when HITL + score≥80 + empty candidates, interrupt still fires with `memories: []`.

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_actioner.py -v`  
Expected: FAIL on kind / new tests

- [ ] **Step 3: Implement actioner flow**

After scoring (+ existing clarification):

1. Prefer `state.get("pending_memories")` if already a nonempty list (idempotent re-entry); else call `extract_memory_candidates` (catch exceptions → `[]`).
2. Build interrupt payload via helpers when HITL and (pending or skill ready).
3. `resume_value = interrupt(payload)` then `approved = map_resume_to_approved(pending, resume_value)`.
4. Else auto: `approved = map_resume_to_approved(pending, True)`.
5. Audit includes `pending_memory_count`, `approved_memory_count`, `action_review_interrupted`.
6. Return includes `pending_memories`, `approved_memories`.

Import extract from `rag.ingest.memory_extract` and mapping from `agent.memory_review`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_actioner.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/actioner.py tests/test_actioner.py
git commit -m "Pause actioner for editable memory review under HITL."
```

---

### Task 4: Remove memorize from HITL pause list

**Files:**
- Modify: `graph/builder.py`
- Modify: `tests/test_graph.py`
- Modify: docs references in Task 6

- [ ] **Step 1: Update failing assertion**

```python
    assert HITL_PAUSE_NODES == [
        "planner",
        "executor",
        "reviewer",
    ]
```

- [ ] **Step 2: Run fail, then fix builder**

```python
HITL_PAUSE_NODES: list[str] = [
    "planner",
    "executor",
    "reviewer",
]
```

- [ ] **Step 3: Run**

Run: `pytest tests/test_graph.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add graph/builder.py tests/test_graph.py
git commit -m "Stop pausing HITL after memorize; decision lives in actioner."
```

---

### Task 5: Frontend action-review helpers + resume wiring

**Files:**
- Create: `app/frontend/src/lib/actionReview.ts`
- Modify: `app/frontend/src/types/api.ts`
- Modify: `app/frontend/src/hooks/useResumeDraft.ts`
- Modify: `app/frontend/src/hooks/useConsole.ts`
- Modify: `app/frontend/src/App.tsx`

- [ ] **Step 1: Add types + helper**

```ts
// types — add:
export type MemoryType = 'fact' | 'preference' | 'entity' | 'summary'

export interface PendingMemory {
  id: string
  content: string
  memory_type: MemoryType
  importance: number
}

export interface MemoryResumeRow {
  id: string
  keep: boolean
  content?: string
  memory_type?: MemoryType
  importance?: number
}
```

```ts
// app/frontend/src/lib/actionReview.ts
import type { InterruptPayload, PendingMemory } from '../types/api'

export function isActionReviewInterrupt(
  interrupt: InterruptPayload | null,
): boolean {
  const value = interrupt?.value
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  return (value as Record<string, unknown>).kind === 'action_review'
}

export function actionReviewMemories(
  interrupt: InterruptPayload | null,
): PendingMemory[] {
  if (!isActionReviewInterrupt(interrupt)) {
    return []
  }
  const record = interrupt!.value as Record<string, unknown>
  const memories = record.memories
  if (!Array.isArray(memories)) {
    return []
  }
  return memories.filter(
    (m): m is PendingMemory =>
      typeof m === 'object' &&
      m !== null &&
      typeof (m as PendingMemory).id === 'string' &&
      typeof (m as PendingMemory).content === 'string',
  )
}

export function actionReviewMeta(interrupt: InterruptPayload | null): {
  score?: number
  threshold?: number
  skillPreviewReady: boolean
  message: string
} {
  if (!isActionReviewInterrupt(interrupt)) {
    return { skillPreviewReady: false, message: '' }
  }
  const record = interrupt!.value as Record<string, unknown>
  return {
    score: typeof record.score === 'number' ? record.score : undefined,
    threshold:
      typeof record.threshold === 'number' ? record.threshold : undefined,
    skillPreviewReady: Boolean(record.skill_preview_ready),
    message: String(record.message ?? ''),
  }
}
```

- [ ] **Step 2: Extend `useResumeDraft`**

Seed `memoryDrafts: Record<string, MemoryResumeRow>` from `actionReviewMemories` (keep: true by default). Reset on `interrupt?.id` change.

`buildPayload` return type:

```ts
{
  overrides?: ResumeOverrides
  answers?: ClarificationAnswer[]
  interrupt_resume?: { memories: MemoryResumeRow[] }
}
```

When `isActionReviewInterrupt`, always include `interrupt_resume.memories` from drafts (even if empty list).

- [ ] **Step 3: Wire `useConsole.resume`**

```ts
async (
  overrides?: ResumeOverrides,
  answers?: ClarificationAnswer[],
  interrupt_resume?: unknown,
) => {
  ...
  const response = await postResume({
    thread_id: threadId,
    overrides: overrides ?? undefined,
    answers: answers ?? undefined,
    interrupt_resume: interrupt_resume ?? undefined,
  })
```

Update `App.tsx` continue handler:

```ts
const { overrides, answers, interrupt_resume } = buildPayload()
void resume(overrides, answers, interrupt_resume)
```

- [ ] **Step 4: Build**

Run: `cd app/frontend && npm run build`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/lib/actionReview.ts app/frontend/src/types/api.ts \
  app/frontend/src/hooks/useResumeDraft.ts app/frontend/src/hooks/useConsole.ts \
  app/frontend/src/App.tsx
git commit -m "Wire action-review memory drafts into resume payload."
```

---

### Task 6: Workplace action-review UI

**Files:**
- Modify: `app/frontend/src/components/Workplace.tsx` + `.css`
- Modify: `app/frontend/src/App.tsx` (pass memory draft setters)
- Modify: inspector auto-collapse condition to include `isActionReviewInterrupt`

- [ ] **Step 1: Add Action review panel**

Priority: clarification → action_review → step → idle.

Panel contents per spec: title, score, skill note, editable rows (keep checkbox, content textarea, type select, importance), empty copy, primary Continue.

Wire props from `useResumeDraft` memory draft state.

Inspector collapse: `clarifying || actionReviewing`.

- [ ] **Step 2: Build**

Run: `cd app/frontend && npm run build`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/frontend/src/components/Workplace.tsx app/frontend/src/components/Workplace.css \
  app/frontend/src/App.tsx app/frontend/src/components/InspectorStack.tsx \
  app/frontend/src/components/CenterColumn.tsx
git commit -m "Show editable action-review memories in center Workplace."
```

---

### Task 7: Docs + history

**Files:**
- Modify: `docs/IMPLEMENTATION.md`, `docs/ARCHITECTURE.md`, `docs/FRONTEND.md`
- Create: `docs/histories/2026-07/YYYYMMDD-HHmm-action-review-memory-hitl.md`
- Run: `graphify update .`

- [ ] **Step 1: Update IMPLEMENTATION**

- Loop: actioner owns extract + optional `action_review`; memorize commits
- HITL: replace skill-preview bullet with `action_review`; `HITL_PAUSE_NODES` without memorize
- State table: `pending_memories`, `approved_memories`
- Resume example with `interrupt_resume.memories`

- [ ] **Step 2: Update ARCHITECTURE + FRONTEND** briefly

- [ ] **Step 3: History entry** per `docs/HISTORY_GUIDE.md`

- [ ] **Step 4: graphify update**

```bash
graphify update .
```

- [ ] **Step 5: Full verify + commit**

```bash
pytest tests/test_actioner.py tests/test_memory_pipeline.py tests/test_memory_review.py tests/test_graph.py -v
cd app/frontend && npm run build
```

```bash
git add docs/ graphify-out/
git commit -m "Document action-review memory HITL behavior."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Extract without store in actioner | 1, 3 |
| Editable HITL keep/drop/edit | 1, 5, 6 |
| One `action_review` interrupt (incl. skill) | 3 |
| HITL off auto-approve | 3 |
| Memorize commit-only + clear lists | 2 |
| Remove memorize from pause nodes | 4 |
| Bare resume keep-all / `[]` store none | 1, 5 |
| Workplace center UI | 6 |
| Docs | 7 |

## Self-review notes

- No TBD placeholders; resume mapping rules match the approved spec.
- Frontend must pass `interrupt_resume` (today `useConsole` omits it — Task 5).
- Existing `skill_preview` kind assertions must flip to `action_review` (Task 3).
