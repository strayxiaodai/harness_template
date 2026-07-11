# Action-Review API E2E Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one API-level integration test that proves HITL `action_review` keep/edit/drop resume stores only the edited kept memory, clears pending/approved, and does not pause again on memorize.

**Architecture:** Compile a real HITL graph with `MemorySaver`, seed the checkpoint past `reviewer`, stub score/extract/clarification/commit seams, invoke until `action_review` interrupt, then `POST /resume` with `interrupt_resume.memories` via FastAPI `TestClient`. Assert interrupt shape, store spy, cleared state, and complete status.

**Tech Stack:** pytest, FastAPI TestClient, LangGraph `MemorySaver` + `interrupt()`, existing `resume_harness` / `interrupt_resume` wiring.

**Spec:** [`docs/superpowers/specs/2026-07-11-action-review-api-e2e-test-design.md`](../specs/2026-07-11-action-review-api-e2e-test-design.md)

**Prerequisite:** Backend from [`2026-07-11-action-review-memory-hitl.md`](2026-07-11-action-review-memory-hitl.md) must be in place: `pending_memories` / `approved_memories`, `extract_memory_candidates`, `map_resume_to_approved` / `action_review` interrupt in actioner, `commit_approved_memories` in memorize, `memorize` removed from `HITL_PAUSE_NODES`. Frontend tasks are not required for this test.

---

## File map

| File | Responsibility |
|------|----------------|
| `tests/test_action_review_api.py` | Seed helper + the single E2E test |
| `docs/superpowers/specs/2026-07-11-action-review-memory-hitl-design.md` | One-line Verification pointer to this test |
| `docs/histories/2026-07/YYYYMMDD-HHmm-action-review-api-e2e-test.md` | History after the test lands |

Do not modify `tests/test_api.py` beyond optional import/shared fixture reuse if natural; prefer a dedicated module.

---

### Task 1: Write the failing E2E test

**Files:**
- Create: `tests/test_action_review_api.py`

- [ ] **Step 1: Create the test module with seed helper and stubs**

```python
"""API E2E: action_review interrupt → resume keep/edit/drop → memorize commit."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from graph.schemas import ActionScoreResult


CANDIDATES: list[dict[str, Any]] = [
    {
        "id": "m0",
        "content": "User prefers pytest",
        "memory_type": "preference",
        "importance": 0.8,
    },
    {
        "id": "m1",
        "content": "Project uses FastAPI",
        "memory_type": "fact",
        "importance": 0.6,
    },
]

EDITED_CONTENT = "User prefers pytest (edited)"


def _seed_values(**overrides: object) -> dict[str, Any]:
    """Minimal AgentState values for seeding past reviewer."""
    messages = [HumanMessage(content="I prefer pytest over unittest")]
    base: dict[str, Any] = {
        "thread_id": "action-review-e2e",
        "task": "Ship memory review",
        "messages": messages,
        "plan": ["extract", "review", "store"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "reviewer",
        "approved": False,
        "human_in_the_loop": True,
        "memory_cursor": 0,
        "pending_memories": [],
        "approved_memories": [],
        "review": {
            "verdict": "pass",
            "reason": "ok",
            "suggested_step": "finish",
        },
        "execution": {
            "summary": "done",
            "changes": [],
            "risks": [],
            "verification": ["ok"],
        },
    }
    base.update(overrides)
    return base


async def seed_action_review_interrupt(
    graph: Any,
    *,
    thread_id: str,
) -> Any:
    """Seed past reviewer and run until actioner's action_review interrupt."""
    config = {"configurable": {"thread_id": thread_id}}
    await graph.aupdate_state(config, _seed_values(thread_id=thread_id), as_node="reviewer")
    await graph.ainvoke(None, config)
    return await graph.aget_state(config)


@pytest.fixture
def action_review_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """HITL graph with stubbed score/extract/clarification/commit."""
    pytest.importorskip("langgraph")
    from langgraph.checkpoint.memory import MemorySaver

    from agent import actioner as actioner_module
    from agent import clarification as clarification_module
    from agent import memorize as memorize_module
    from app.main import app
    from graph.builder import compile_with_checkpointer
    from rag.ingest import memory_extract as memory_extract_module

    commit_spy = AsyncMock(
        return_value={"memory_cursor": 1, "pending_memories": [], "approved_memories": []},
    )
    monkeypatch.setattr(
        actioner_module,
        "score_loop",
        AsyncMock(return_value=ActionScoreResult(score=50, rationale="ok")),
    )
    monkeypatch.setattr(
        actioner_module,
        "extract_memory_candidates",
        AsyncMock(return_value=list(CANDIDATES)),
    )
    # Prefer patching the name actioner imports; adjust if extract lives only on memory_extract.
    if hasattr(memory_extract_module, "extract_memory_candidates"):
        monkeypatch.setattr(
            memory_extract_module,
            "extract_memory_candidates",
            AsyncMock(return_value=list(CANDIDATES)),
        )
    monkeypatch.setattr(
        clarification_module,
        "ask_clarification",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())
    monkeypatch.setattr(memorize_module, "commit_approved_memories", commit_spy)
    # If memorize still gates on RAG settings/service, force the commit path:
    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: MagicMock(enabled=True),
    )
    monkeypatch.setattr(
        memorize_module,
        "get_rag_service",
        lambda: MagicMock(save_memory_store=MagicMock()),
    )

    graph = compile_with_checkpointer(MemorySaver(), human_in_the_loop=True)
    app.state.graph_step = graph
    app.state.graph_auto = graph
    client = TestClient(app, raise_server_exceptions=True)
    client.commit_spy = commit_spy  # type: ignore[attr-defined]
    client.graph = graph  # type: ignore[attr-defined]
    return client


@pytest.mark.asyncio
async def test_action_review_resume_keeps_edits_drops_and_commits(
    action_review_client: TestClient,
) -> None:
    """Keep+edit m0, drop m1; store once; clear pending; no memorize HITL pause."""
    graph = action_review_client.graph  # type: ignore[attr-defined]
    commit_spy = action_review_client.commit_spy  # type: ignore[attr-defined]
    thread_id = "action-review-e2e"

    snap = await seed_action_review_interrupt(graph, thread_id=thread_id)
    interrupts = tuple(getattr(snap, "interrupts", None) or ())
    assert interrupts, "expected action_review interrupt before resume"
    value = getattr(interrupts[0], "value", {}) or {}
    assert value.get("kind") == "action_review"
    assert value.get("node") == "actioner"
    assert value.get("skill_preview_ready") is False
    memories = value.get("memories") or []
    assert {m["id"] for m in memories} == {"m0", "m1"}
    assert commit_spy.await_count == 0
    pending = (snap.values or {}).get("pending_memories") or []
    assert len(pending) == 2

    response = action_review_client.post(
        "/resume",
        json={
            "thread_id": thread_id,
            "interrupt_resume": {
                "memories": [
                    {
                        "id": "m0",
                        "keep": True,
                        "content": EDITED_CONTENT,
                        "memory_type": "preference",
                        "importance": 0.9,
                    },
                    {"id": "m1", "keep": False},
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body.get("interrupt") is None
    assert body.get("next_action") in (None, "")

    commit_spy.assert_awaited()
    # Inspect approved list passed into commit (adjust arg name to real signature).
    call_kwargs = commit_spy.await_args.kwargs
    call_args = commit_spy.await_args.args
    approved = call_kwargs.get("approved_memories")
    if approved is None and call_args:
        # commit_approved_memories(state, ...) may read state["approved_memories"]
        state_arg = call_args[0]
        if isinstance(state_arg, dict):
            approved = state_arg.get("approved_memories")
    assert approved is not None
    assert len(approved) == 1
    assert approved[0]["content"] == EDITED_CONTENT
    assert all(row.get("content") != "Project uses FastAPI" for row in approved)

    final = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = final.values or {}
    assert values.get("pending_memories") in ([], None)
    assert values.get("approved_memories") in ([], None)
    assert values.get("memory_cursor") == len(values.get("messages") or [])
    assert not (getattr(final, "interrupts", None) or ())
    assert not (final.next or ())
```

Notes for the implementer:

- Patch whatever symbol actioner actually calls after the parent plan lands (`actioner.extract_memory_candidates` vs `memory_extract.extract_memory_candidates`).
- `commit_approved_memories` signature from the parent plan may be `(state, *, memory_store=..., settings=...)` — assert on the state dict’s `approved_memories` or the dedicated kwarg accordingly.
- If `ask_clarification` is imported into actioner as a bound name, patch `actioner_module.ask_clarification` instead of (or in addition to) `clarification_module.ask_clarification`.
- Sync fixture: if `TestClient` + async seed is awkward, use `anyio`/`asyncio.run` inside a sync test, or keep `@pytest.mark.asyncio` and call the ASGI app via httpx AsyncClient — prefer matching `tests/test_api.py` style (sync TestClient) with `asyncio.get_event_loop().run_until_complete(seed...)` only if the suite already does that; otherwise mark asyncio and use httpx AsyncClient for `/resume`.

Preferred sync shape if asyncio fixture fights TestClient:

```python
def test_action_review_resume_keeps_edits_drops_and_commits(
    action_review_client: TestClient,
) -> None:
    import asyncio

    graph = action_review_client.graph
    snap = asyncio.get_event_loop().run_until_complete(
        seed_action_review_interrupt(graph, thread_id="action-review-e2e"),
    )
    # ... same assertions + client.post ...
```

Use whatever pattern already works in this repo’s pytest + asyncio config (`pytest-asyncio` mode).

- [ ] **Step 2: Run the test and confirm it fails for the right reason**

Run: `pytest tests/test_action_review_api.py::test_action_review_resume_keeps_edits_drops_and_commits -v`

Expected before parent feature: FAIL (missing symbols / no `action_review` interrupt / `memorize` still in pause list / store not commit-only).

Expected after parent feature but before this test is tuned: may FAIL on stub path or assertion detail — fix stubs until the failure is a real product gap, then fix product or test.

- [ ] **Step 3: Commit the failing test (optional red if team prefers green-only CI)**

If the branch already has the HITL feature green, skip a red commit and proceed to Task 2. Otherwise:

```bash
git add tests/test_action_review_api.py
git commit -m "test: add failing action_review API E2E for keep/edit/drop"
```

---

### Task 2: Make the E2E test pass

**Files:**
- Modify only as needed: `tests/test_action_review_api.py` (stub paths)
- If the test exposes a real product gap: fix per parent plan (`agent/actioner.py`, `agent/memorize.py`, `graph/builder.py`) — do not invent alternate behavior

- [ ] **Step 1: Align stubs with real import sites**

Open `agent/actioner.py` and `agent/memorize.py` after the feature lands. Patch the exact names used at call sites. Re-run until pre-resume assertions pass (interrupt kind, two memories, spy not called).

- [ ] **Step 2: Align commit assertion with `commit_approved_memories`**

Inspect the call: either approved list argument or `state["approved_memories"]` after resume mapping. Assert edited content only.

- [ ] **Step 3: Confirm no second HITL pause**

If `status != "complete"` and `next_action == "memorize"` or interrupt after memorize, verify `HITL_PAUSE_NODES` no longer includes `"memorize"` (`tests/test_graph.py` should already assert this from the parent plan).

- [ ] **Step 4: Run green**

Run: `pytest tests/test_action_review_api.py::test_action_review_resume_keeps_edits_drops_and_commits -v`  
Expected: PASS

Also run a quick neighbor gate:

```bash
pytest tests/test_action_review_api.py tests/test_api.py tests/test_graph.py tests/test_actioner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_action_review_api.py
git commit -m "test: prove action_review resume keep/edit/drop via /resume"
```

---

### Task 3: Docs cross-links + history

**Files:**
- Modify: `docs/superpowers/specs/2026-07-11-action-review-memory-hitl-design.md` (Verification section)
- Create: `docs/histories/2026-07/YYYYMMDD-HHmm-action-review-api-e2e-test.md` (use current local time)

- [ ] **Step 1: Add Verification pointer in parent design**

Under `## Verification`, add:

```markdown
- API E2E gate: `pytest tests/test_action_review_api.py::test_action_review_resume_keeps_edits_drops_and_commits -v`
  (design: `docs/superpowers/specs/2026-07-11-action-review-api-e2e-test-design.md`)
```

- [ ] **Step 2: Write history entry**

```markdown
## [YYYY-MM-DD HH:MM] | Task: Action-review API E2E test

### User Query
> Design and add a test covering the whole action_review → /resume → memorize process

### Changes Overview
- Area: tests / HITL memory review
- Key actions: Seeded HITL graph + POST /resume keep/edit/drop assertions

### Design Intent
Prove the HTTP operator path without cold /run through planner/executor/reviewer; unit tests keep edge cases.

### Files Modified
- `tests/test_action_review_api.py`
- `docs/superpowers/specs/2026-07-11-action-review-memory-hitl-design.md`
- `docs/superpowers/specs/2026-07-11-action-review-api-e2e-test-design.md`
```

- [ ] **Step 3: Commit**

```bash
git add \
  docs/superpowers/specs/2026-07-11-action-review-memory-hitl-design.md \
  docs/histories/2026-07/*-action-review-api-e2e-test.md
git commit -m "docs: point HITL verification at action_review API E2E test"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
| --- | --- |
| Seeded HITL graph + `/resume` | Task 1–2 |
| Memories-only `action_review` (score &lt; threshold) | Task 1 stubs `score=50` |
| Keep/edit/drop payload | Task 1 Act section |
| Store only edited kept row | Task 1–2 assertions |
| Clear pending/approved + cursor | Task 1 post-assert |
| No second memorize HITL pause | Task 1 status/interrupt + Task 2 pause-list |
| No cold `/run` / no frontend | Non-goals honored |
| Parent Verification pointer | Task 3 |

No TBD placeholders. Stub symbol names may need a one-line adjust after parent plan import sites are final — that is explicit in Task 2 Step 1, not an open design question.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-11-action-review-api-e2e-test.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with executing-plans checkpoints  

**Which approach?**
