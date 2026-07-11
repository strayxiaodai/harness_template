# Action-review API E2E test

Date: 2026-07-11  
Status: approved for planning  
Surface: pytest + FastAPI `TestClient` against real HITL graph  
Related: [`2026-07-11-action-review-memory-hitl-design.md`](2026-07-11-action-review-memory-hitl-design.md)

## Problem

Unit tests will cover extract, resume mapping, and memorize commit in isolation.
Nothing yet proves the operator path through the HTTP resume surface: interrupt
payload → `POST /resume` with `interrupt_resume.memories` → store only kept
edits → clear pending state → no second memorize-only HITL pause.

## Goals

1. One API-level integration test for the memories-only `action_review` happy
   path: keep + edit + drop → commit.
2. Use a real HITL-compiled graph and checkpointer, not a fully mocked graph.
3. Drive resume through FastAPI so `interrupt_resume` → `Command(resume=…)`
   wiring is exercised.
4. Assert store side effects and cleared `pending_memories` /
   `approved_memories` after memorize.

## Non-goals

- Cold `/run` from START through planner / executor / reviewer boundary pauses
- Bare resume keep-all, `{ "memories": [] }`, skill+memories combo, clarification
  then action review
- Workplace / frontend draft builders
- Live LLM or real embedding/vector backends

## Approach

**Seeded HITL graph + `/resume`.**

Compile the real workflow with `human_in_the_loop=True` and `MemorySaver`.
Seed the checkpoint past the reviewer so the next node is `actioner`, invoke
until the dynamic `action_review` interrupt, then `POST /resume` with an
edit/keep/drop payload. Stub score, extract, clarification, and store seams.

This avoids three prior `interrupt_after` resumes while still proving the
memory-review commit path the operator actually uses.

## Fixture & stubs

### Graph

- `compile_with_checkpointer(MemorySaver(), human_in_the_loop=True)`
- Mount as `app.state.graph_step` for `TestClient`
- After the feature lands, `HITL_PAUSE_NODES` must not include `memorize`; the
  test’s post-resume assertions catch a mistaken second memorize pause

### Reaching `action_review`

1. `aupdate_state(config, values, as_node="reviewer")` so `next == ("actioner",)`
2. `ainvoke(None, config)` so actioner extracts and calls `interrupt()`
3. Optional helper: `seed_action_review_interrupt(graph, thread_id, …)` in the
   test module (extract to `tests/helpers/` only if reused)

### Stubs (monkeypatch)

| Seam | Behavior |
| --- | --- |
| `score_loop` | Fixed score below skill threshold (e.g. 50) → `skill_preview_ready=False` |
| Memory extract used by actioner | Return two fixed candidates; no LLM |
| Clarification helper | Never interrupt |
| Memorize store / embed path | Spy recording written memories |
| Planner / executor / reviewer | Not executed (seeded past them) |

### Seeded state (essentials)

- `human_in_the_loop=True`
- `messages`: at least one turn after `memory_cursor`
- `memory_cursor`: index before those messages
- `review.suggested_step`: `"finish"` so post-memorize routing ends the loop
- Other fields as required for a valid `AgentState` checkpoint

### Stub candidates

```text
m0: content="User prefers pytest", memory_type=preference, importance=0.8
m1: content="Project uses FastAPI", memory_type=fact, importance=0.6
```

## Scenario

**Test file:** `tests/test_action_review_api.py`  
**Test name:** `test_action_review_resume_keeps_edits_drops_and_commits`

### Arrange

1. Build HITL graph, apply stubs, mount on app state
2. Seed past reviewer; invoke until paused
3. Read interrupt from checkpoint / snapshot (same shape the API returns)

### Assert — before resume

1. Interrupted; interrupt `kind == "action_review"`, `node == "actioner"`
2. `memories` contains `m0` and `m1` with stubbed fields
3. `skill_preview_ready is False`
4. Store spy not called
5. `pending_memories` length 2; `approved_memories` empty or unset

### Act

```http
POST /resume
{
  "thread_id": "<seeded>",
  "interrupt_resume": {
    "memories": [
      {
        "id": "m0",
        "keep": true,
        "content": "User prefers pytest (edited)",
        "memory_type": "preference",
        "importance": 0.9
      },
      { "id": "m1", "keep": false }
    ]
  }
}
```

### Assert — after resume

1. HTTP 200; run complete (`next` empty / status complete — not waiting on memorize)
2. Store spy called with exactly one memory; content is the edited `m0` string
   (not original `m0`, not `m1`)
3. Checkpoint: `pending_memories == []`, `approved_memories == []`
4. `memory_cursor == len(messages)`
5. No live interrupt that is memorize-only / empty pause for memory

### Failures this catches

- Store before operator resume
- Drop ignored or edit ignored
- Stale pending/approved left after memorize
- Second HITL stop solely on memorize after the decision already happened

## Boundaries with other tests

| Concern | Where |
| --- | --- |
| Resume mapping edge cases (`True`, `[]`, bad fields) | `tests/test_actioner.py` |
| Memorize soft-fail / cursor advance | `tests/test_memory_pipeline.py` |
| `HITL_PAUSE_NODES` membership | `tests/test_graph.py` |
| Workplace draft → `interrupt_resume` | Frontend unit tests (when added) |
| Fully mocked `/run` / `/resume` shapes | `tests/test_api.py` (unchanged role) |

## Verification

```bash
pytest tests/test_action_review_api.py::test_action_review_resume_keeps_edits_drops_and_commits -v
```

When implementing the HITL feature, add a one-line pointer under Verification in
the parent design doc to this test as the API gate for keep/edit/drop → commit.

## Success criteria

1. Test fails before action-review + commit-only memorize exist; passes after.
2. Resume path uses real `graph_step` + checkpointer, not `_mock_graph`.
3. Assertions cover interrupt shape, edited keep, dropped row omitted from store,
   cleared pending/approved, cursor advance, and no second memorize HITL pause.
4. No live network / LLM / embedding calls.
