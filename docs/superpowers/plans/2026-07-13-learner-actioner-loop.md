# Learner Loop + Fold Memorize + Stage UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `planner → executor → learner → actioner` with memorize folded into actioner, continue-only-to-planner routing, and console stage payloads/`interrupt` hydrate.

**Architecture:** Rename reviewer→learner (verdict + lessons + learning_candidates). Actioner soft-skips on fail; on pass scores, merges candidates∪extract, HITL action_review, then `commit_round_memories`. `route_after_action` returns only `planner|finish`. API exposes `interrupt` + compact state; frontend stores timeline node patches and renders learner/actioner Workplace blocks.

**Tech Stack:** LangGraph, Pydantic schemas, FastAPI `RunResponse`, React console (`Workplace`, `useConsole`, `GRAPH_NODES`).

**Spec:** [`docs/superpowers/specs/2026-07-13-learner-actioner-loop-design.md`](../specs/2026-07-13-learner-actioner-loop-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `graph/schemas.py` | `LearningResult`, `LessonsBlock`, candidate item model; drop/replace `ReviewResult` |
| `graph/state.py` | `LearningRecord`, `learning`, `learning_candidates`; remove `review` |
| `graph/routing.py` | `ActionRoute = planner \| finish`; never `executor` |
| `graph/builder.py` | Nodes: drop memorizer; learner; route from actioner; HITL pause list |
| `agent/learner.py` | New (from reviewer); write learning fields |
| `agent/reviewer.py` | Delete after cutover |
| `agent/actioner.py` | Soft-skip vs pass+commit; consume `learning` |
| `agent/memorize.py` | `commit_round_memories` helper only |
| `agent/planner.py` | Prior feedback from `learning` |
| `config/prompts.yaml` | `learner` prompt (replace `reviewer`) |
| `skills/eligibility.py`, `skills/context.py` | Read `learning` not `review` |
| `app/schemas/run.py` | `interrupt`, compact state, refine override `planner\|finish` |
| `app/services/snapshot.py` | Populate interrupt + slice |
| `tests/conftest.py` | Load `app.agents.learner` |
| `app/frontend/src/types/api.ts` | GRAPH_NODES, LearningRecord, RunResponse fields |
| `app/frontend/src/lib/api.ts` | Patch timeline steps; hydrate from RunResponse |
| `app/frontend/src/hooks/useConsole.ts` | Use patch helpers |
| `app/frontend/src/components/Workplace.tsx` | Learner + actioner blocks |
| `app/frontend/src/components/TraceTimeline.tsx` | Node-aware previews |
| `app/frontend/src/components/GraphSpine.tsx` | Refine loop → planner only |
| `docs/IMPLEMENTATION.md`, `ARCHITECTURE.md`, `FRONTEND.md` | As-built sync |
| `docs/histories/2026-07/…` | History entry |

---

### Task 1: Schemas + AgentState for `learning`

**Files:**
- Modify: `graph/schemas.py`
- Modify: `graph/state.py`
- Test: `tests/test_learning_schemas.py` (create)

- [ ] **Step 1: Write failing schema tests**

```python
# tests/test_learning_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from graph.schemas import LearningResult, LessonsBlock


def test_learning_result_accepts_pass_with_lessons() -> None:
    result = LearningResult(
        verdict="pass",
        reason="Looks solid",
        suggested_step="finish",
        lessons=LessonsBlock(
            worked=["tools used"],
            failed=[],
            risks=[],
            next_time=["keep verification"],
        ),
        learning_candidates=[
            {
                "id": "m0",
                "content": "Prefer pytest",
                "memory_type": "preference",
                "importance": 0.8,
            },
        ],
    )
    assert result.verdict == "pass"
    assert result.suggested_step == "finish"
    assert result.learning_candidates[0].content == "Prefer pytest"


def test_learning_result_rejects_executor_suggested_step() -> None:
    with pytest.raises(ValidationError):
        LearningResult(
            verdict="fail",
            reason="Incomplete",
            suggested_step="executor",  # type: ignore[arg-type]
            lessons=LessonsBlock(),
            learning_candidates=[],
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_learning_schemas.py -v`  
Expected: FAIL (LearningResult / LessonsBlock missing)

- [ ] **Step 3: Implement schemas + state**

In `graph/schemas.py`, replace `ReviewResult` with:

```python
class LessonsBlock(BaseModel):
    """Learner lessons attached for actioner scoring and UI."""

    worked: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_time: list[str] = Field(default_factory=list)


class LearningCandidate(BaseModel):
    """Memory-shaped candidate proposed by the learner."""

    id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    memory_type: Literal["fact", "preference", "entity", "summary"]
    importance: float = Field(ge=0.0, le=1.0)


class LearningResult(BaseModel):
    """Structured learner output consumed by the actioner."""

    verdict: Literal["pass", "fail"]
    reason: str = Field(min_length=1)
    suggested_step: Literal["planner", "finish"]
    lessons: LessonsBlock = Field(default_factory=LessonsBlock)
    learning_candidates: list[LearningCandidate] = Field(default_factory=list)
```

In `graph/state.py`:

```python
class LearningRecord(TypedDict):
    """Serialized learner verdict + lessons (no candidates)."""

    verdict: str
    reason: str
    suggested_step: str
    lessons: dict[str, list[str]]


# On AgentState: remove review; add:
    learning: NotRequired[LearningRecord]
    learning_candidates: NotRequired[list[dict[str, object]]]
```

Grep and temporarily keep importing aliases only where Task 3+ will fix — do not leave `ReviewResult` if tests fail; update imports in same commit or Task 3 immediately after.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_learning_schemas.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add graph/schemas.py graph/state.py tests/test_learning_schemas.py
git commit -m "$(cat <<'EOF'
Add LearningResult schema and learning state fields.

EOF
)"
```

---

### Task 2: Route only to planner or finish

**Files:**
- Modify: `graph/routing.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Rewrite routing tests (fail under old behavior)**

```python
# tests/test_graph.py — replace refine cases

def test_route_defaults_to_planner_refinement() -> None:
    """Failed / unmarked loops continue at planner, not executor."""
    assert route_after_action(_state()) == "planner"


def test_route_maps_legacy_executor_refine_to_planner() -> None:
    """Legacy refine_from=executor must continue at planner."""
    assert route_after_action(_state(refine_from="executor")) == "planner"


def test_route_can_resume_at_planner() -> None:
    assert route_after_action(_state(refine_from="planner")) == "planner"


def test_route_respects_round_budget() -> None:
    assert (
        route_after_action(
            _state(rounds=3, max_rounds=3, refine_from="planner"),
        )
        == "finish"
    )
```

Also update `test_create_workflow_has_expected_nodes` expectations in Task 5 (leave failing comment or skip until Task 5 if preferred — better update workflow test only in Task 5).

- [ ] **Step 2: Run routing tests — expect default-to-executor failure**

Run: `pytest tests/test_graph.py::test_route_defaults_to_planner_refinement tests/test_graph.py::test_route_maps_legacy_executor_refine_to_planner -v`  
Expected: FAIL

- [ ] **Step 3: Implement routing**

```python
# graph/routing.py
from typing import Literal

from graph.state import AgentState

ActionRoute = Literal["planner", "finish"]
DEFAULT_MAX_ROUNDS = 3


def route_after_action(state: AgentState) -> ActionRoute:
    """Finish or continue at planner after the actioner step."""
    if state.get("approved"):
        return "finish"

    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"

    refine_from = state.get("refine_from", "planner")
    if refine_from == "finish":
        return "finish"

    # planner, legacy executor, or unknown → planner
    return "planner"
```

- [ ] **Step 4: Run routing unit tests (skip workflow node test if still old)**

Run: `pytest tests/test_graph.py -k "route_" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add graph/routing.py tests/test_graph.py
git commit -m "$(cat <<'EOF'
Route after actioner only to planner or finish.

EOF
)"
```

---

### Task 3: Learner agent + prompts + test rename

**Files:**
- Create: `agent/learner.py`
- Delete: `agent/reviewer.py` (after tests green)
- Modify: `config/prompts.yaml`
- Modify: `tests/test_reviewer.py` → `tests/test_learner.py`
- Modify: `tests/conftest.py`
- Modify: `agent/planner.py` (prior feedback from `learning`)

- [ ] **Step 1: Add failing learner tests**

```python
# tests/test_learner.py (adapt from test_reviewer.py)
async def test_learner_writes_learning_to_state(monkeypatch):
    from app.agents import learner as learner_module
    # stub LearningResult with lessons + empty candidates
    result = await learner_module.learner_agent(_state())
    assert result["role"] == "learner"
    assert result["approved"] is False or True  # per stub
    assert "learning" in result
    assert "lessons" in result["learning"]
    assert "learning_candidates" in result
    assert "review" not in result
```

Include prompt-content test: human message still includes execution + tool calls; system uses learner prompt.

- [ ] **Step 2: Run — expect import failure**

Run: `pytest tests/test_learner.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `agent/learner.py`**

Copy structure from `agent/reviewer.py`:

- `with_structured_output(LearningResult)`
- Prompt key `PROMPTS["learner"]["system"]`
- Return:

```python
return {
    "role": "learner",
    "approved": learning.verdict == "pass",
    "learning": {
        "verdict": learning.verdict,
        "reason": learning.reason,
        "suggested_step": learning.suggested_step,
        "lessons": learning.lessons.model_dump(),
    },
    "learning_candidates": [
        c.model_dump() for c in learning.learning_candidates
    ],
    "messages": [
        AIMessage(
            content=(
                f"Learning {learning.verdict}: {learning.reason}"
            )
        )
    ],
}
```

Update `config/prompts.yaml`:

```yaml
learner:
  system: |
    You are the learner in a Plan → Do → Learn → Act harness loop.
    First challenge the executor result: correctness, security, scope,
    and testability. Choose suggested_step from: planner, finish.
    Then record lessons (worked / failed / risks / next_time).
    When verdict is pass, propose durable learning_candidates worth storing
    (empty list if none). When verdict is fail, candidates may be empty;
    explain what is missing in lessons.failed / next_time.
```

Remove the old `reviewer:` block.

Update planner feedback:

```python
learning = state.get("learning")
feedback = learning["reason"] if learning else "(none)"
```

Update `tests/conftest.py` to load `agent/learner.py` as `app.agents.learner` (mirror reviewer loader). Remove reviewer module load.

- [ ] **Step 4: Delete `agent/reviewer.py` and old `tests/test_reviewer.py`; fix any remaining imports**

Run: `rg -n "reviewer|ReviewResult|\\[\"review\"\\]|\\.get\\(\"review\"\\)" --glob '!docs/**' --glob '!graphify-out/**'` and fix package code.

- [ ] **Step 5: Run learner + planner-related tests**

Run: `pytest tests/test_learner.py tests/test_planner.py -q -k "not live"`  
Expected: PASS (skip planner file if absent)

- [ ] **Step 6: Commit**

```bash
git add agent/learner.py agent/planner.py config/prompts.yaml tests/test_learner.py tests/conftest.py
git rm agent/reviewer.py tests/test_reviewer.py
git commit -m "$(cat <<'EOF'
Replace reviewer with learner agent and prompts.

EOF
)"
```

---

### Task 4: Memorize helper (no graph node contract)

**Files:**
- Modify: `agent/memorize.py`
- Modify: `tests/test_memory_pipeline.py`

- [ ] **Step 1: Update tests to call `commit_round_memories`**

Rename expectations: helper returns cursor + cleared lists **without** requiring `role: "memorize"`. Prefer:

```python
result = await memorize_module.commit_round_memories(state)
assert "memory_cursor" in result
assert result["pending_memories"] == []
assert result["approved_memories"] == []
assert "role" not in result
```

- [ ] **Step 2: Run — expect missing symbol**

Run: `pytest tests/test_memory_pipeline.py -k memorize -v`  
Expected: FAIL

- [ ] **Step 3: Implement helper**

```python
async def commit_round_memories(state: AgentState) -> dict[str, object]:
    """Commit approved memories; return cursor + cleared list updates."""
    # body of today's memorize_agent without role key
    ...
    return {**updates}  # no role
```

Keep `_skip_memorize_updates` but drop `"role": "memorize"`. Optionally leave deprecated `memorize_agent = commit_round_memories` alias deleted — prefer delete `memorize_agent`.

- [ ] **Step 4: Run memory pipeline tests**

Run: `pytest tests/test_memory_pipeline.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/memorize.py tests/test_memory_pipeline.py
git commit -m "$(cat <<'EOF'
Turn memorize into commit_round_memories helper.

EOF
)"
```

---

### Task 5: Actioner soft-skip + pass commit + graph builder

**Files:**
- Modify: `agent/actioner.py`
- Modify: `graph/builder.py`
- Modify: `tests/test_actioner.py`
- Modify: `tests/test_graph.py` (workflow nodes)
- Modify: `tests/test_action_review_api.py` (seed role learner / learning)

- [ ] **Step 1: Add failing actioner tests**

```python
async def test_actioner_soft_skips_when_not_approved(monkeypatch):
    # approved False, learning suggested_step planner
    # spy score_loop, extract, interrupt, commit_round_memories — none called
    result = await actioner_agent(state)
    assert result["loop_score"] == 0
    assert result["skill_preview_ready"] is False
    assert result["refine_from"] == "planner"
    assert result["rounds"] == state["rounds"] + 1


async def test_actioner_pass_merges_learning_candidates_and_commits(monkeypatch):
    # approved True; learning_candidates + extract stub; HITL off
    # commit_round_memories awaited once with approved_memories set
    ...
```

Update existing interrupt tests to stub `learning` instead of `review`, and pass `approved=True`.

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/test_actioner.py -v`  
Expected: FAIL on new soft-skip / merge cases

- [ ] **Step 3: Implement actioner**

Pseudo-structure:

```python
async def actioner_agent(state: AgentState) -> dict[str, object]:
    learning = state.get("learning") or {}
    suggestion = _normalize_step(
        learning.get("suggested_step") or ("finish" if state.get("approved") else "planner")
    )
    next_round = state["rounds"] + 1

    if not state.get("approved"):
        return {
            "role": "actioner",
            "rounds": next_round,
            "refine_from": suggestion,
            "loop_score": 0,
            "skill_preview_ready": False,
        }

    # existing score + extract path, but:
    # pending = merge_candidates(state.get("learning_candidates"), extracted)
    # then interrupt / map / clear_pending as today
    commit_updates = await commit_round_memories({**state, "approved_memories": approved_memories, ...})
    return {
        "role": "actioner",
        "rounds": next_round,
        "refine_from": suggestion,
        "loop_score": score,
        "skill_preview_ready": skill_preview_ready,
        "pending_memories": pending,  # or rely on commit clear
        **commit_updates,
    }
```

Add helpers in `agent/actioner.py` or `agent/memory_review.py`:

```python
def _normalize_step(step: str) -> str:
    if step == "finish":
        return "finish"
    return "planner"  # planner or legacy executor


def merge_learning_and_extract(
    learning_candidates: list[dict],
    extracted: list[dict],
) -> list[dict]:
    """Dedupe by normalized content; assign ids m0.."""
    ...
```

Update `_format_score_context` / `_heuristic_loop_score` to read `learning` instead of `review`.

- [ ] **Step 4: Update `graph/builder.py`**

```python
from agent.actioner import actioner_agent
from agent.executor import executor_agent
from agent.learner import learner_agent
from agent.planner import planner_agent
from graph.routing import route_after_action

HITL_PAUSE_NODES = ["planner", "executor", "learner"]

def create_workflow() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_agent)
    graph.add_node("executor", executor_agent)
    graph.add_node("learner", learner_agent)
    graph.add_node("actioner", actioner_agent)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "learner")
    graph.add_edge("learner", "actioner")
    graph.add_conditional_edges(
        "actioner",
        route_after_action,
        {"planner": "planner", "finish": END},
    )
    return graph
```

- [ ] **Step 5: Fix workflow + action-review E2E seed**

```python
assert set(workflow.nodes) == {"planner", "executor", "learner", "actioner"}
assert HITL_PAUSE_NODES == ["planner", "executor", "learner"]
```

In `tests/test_action_review_api.py` `_seed_values`: `role: "learner"`, replace `review` with `learning` (include lessons). Seed with `as_node="learner"`. Assert commit still happens after resume.

- [ ] **Step 6: Run graph/actioner/api tests**

Run: `pytest tests/test_graph.py tests/test_actioner.py tests/test_action_review_api.py tests/test_memory_review.py -q`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add agent/actioner.py graph/builder.py tests/test_actioner.py tests/test_graph.py tests/test_action_review_api.py
git commit -m "$(cat <<'EOF'
Fold memorize into actioner and wire learner graph.

EOF
)"
```

---

### Task 6: Skills + any remaining Python `review` readers

**Files:**
- Modify: `skills/eligibility.py`
- Modify: `skills/context.py`
- Modify: `tests/test_skills_eligibility.py`
- Grep-fix residual `review` / `reviewer` / `memorize` node references in Python (not docs yet)

- [ ] **Step 1: Update eligibility tests for `learning`**

```python
# Threads need executor or learner output
assert "learner" in reason.lower() or "learning" in reason.lower()
```

Eligibility check:

```python
has_learning = bool(values.get("learning"))
if not has_execution and not has_learning:
    return False, "At least one loop must produce executor and learner output ..."
```

Update loop description string to `planner → executor → learner → actioner`.

- [ ] **Step 2: Run**

Run: `pytest tests/test_skills_eligibility.py -v`  
Expected: PASS after implementation

- [ ] **Step 3: Commit**

```bash
git add skills/eligibility.py skills/context.py tests/test_skills_eligibility.py
git commit -m "$(cat <<'EOF'
Point skill eligibility and context at learning state.

EOF
)"
```

---

### Task 7: API `interrupt` + compact state slice

**Files:**
- Modify: `app/schemas/run.py`
- Modify: `app/services/snapshot.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_action_review_api.py` (expect interrupt on pause responses if covered)

- [ ] **Step 1: Failing snapshot test**

```python
@pytest.mark.asyncio
async def test_snapshot_includes_action_review_interrupt() -> None:
    from app.services.snapshot import snapshot_to_response

    interrupt = MagicMock()
    interrupt.id = "int-1"
    interrupt.value = {
        "kind": "action_review",
        "node": "actioner",
        "memories": [],
        "score": 85,
        "threshold": 80,
        "skill_preview_ready": True,
        "message": "…",
    }
    graph = _mock_graph(
        {
            "approved": True,
            "role": "actioner",
            "rounds": 1,
            "max_rounds": 3,
            "human_in_the_loop": True,
            "plan": ["a"],
            "learning": {
                "verdict": "pass",
                "reason": "ok",
                "suggested_step": "finish",
                "lessons": {
                    "worked": [],
                    "failed": [],
                    "risks": [],
                    "next_time": [],
                },
            },
            "loop_score": 85,
            "skill_preview_ready": True,
        },
        next_nodes=("actioner",),
    )
    snap = await graph.aget_state(...)
    # prefer set interrupts on the MagicMock returned by aget_state
    graph.aget_state = AsyncMock(
        return_value=_snapshot_with_interrupts(values, next_nodes=("actioner",), interrupts=(interrupt,))
    )
    response = await snapshot_to_response(graph, "thread-1")
    assert response.interrupt is not None
    assert response.interrupt.value["kind"] == "action_review"
    assert response.plan == ["a"]
    assert response.loop_score == 85
    assert response.learning is not None
```

Extend `_snapshot` helper to accept `interrupts=()`.

- [ ] **Step 2: Implement schema + snapshot**

`RunResponse` additions (optional/nullable defaults):

```python
class InterruptPayload(BaseModel):
    id: str | None = None
    value: Any = None

class LessonsBlockModel(BaseModel):  # or reuse dict
    ...

class RunResponse(BaseModel):
    # existing fields...
    interrupt: InterruptPayload | None = None
    plan: list[str] | None = None
    execution: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    learning: dict[str, Any] | None = None
    learning_candidates: list[dict[str, Any]] | None = None
    refine_from: str | None = None
    loop_score: int | None = None
    skill_preview_ready: bool | None = None
    memory_cursor: int | None = None
```

`ResumeOverrides.refine_from`: `Literal["planner", "finish"]` only.

In `snapshot_to_response`:

```python
interrupts = tuple(getattr(snapshot, "interrupts", None) or ())
interrupt_payload = None
if interrupts:
    raw = interrupts[0]
    interrupt_payload = InterruptPayload(
        id=getattr(raw, "id", None),
        value=getattr(raw, "value", None),
    )

return RunResponse(
    ...,
    interrupt=interrupt_payload,
    plan=values.get("plan"),
    execution=values.get("execution"),
    tool_calls=values.get("tool_calls"),
    learning=values.get("learning"),
    learning_candidates=values.get("learning_candidates"),
    refine_from=values.get("refine_from"),
    loop_score=values.get("loop_score"),
    skill_preview_ready=values.get("skill_preview_ready"),
    memory_cursor=values.get("memory_cursor"),
)
```

Update `test_action_review_api.py`: after seeding interrupt, call an API that maps snapshot (if `/resume` without advancing isn’t available, add a focused unit test only — streaming/final already uses `snapshot_to_response`). Change assertion that assumed no interrupt field documentation; when paused, interrupt must be non-null if you add a GET or invoke snapshot in the E2E via a small harness helper. Minimal: unit test above is enough; E2E still checks commit after resume.

- [ ] **Step 3: Run API tests**

Run: `pytest tests/test_api.py tests/test_action_review_api.py -q`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/schemas/run.py app/services/snapshot.py tests/test_api.py
git commit -m "$(cat <<'EOF'
Expose interrupt and compact state on RunResponse.

EOF
)"
```

---

### Task 8: Frontend types + timeline patches + resume hydrate

**Files:**
- Modify: `app/frontend/src/types/api.ts`
- Modify: `app/frontend/src/lib/api.ts`
- Modify: `app/frontend/src/hooks/useConsole.ts`
- Modify: `app/frontend/src/lib/skillEligibility.ts`
- Modify: `app/frontend/src/components/GraphSpine.tsx`
- Modify: Command/Workplace refine `<option value="executor">` → remove

- [ ] **Step 1: Update types**

```typescript
export const GRAPH_NODES = [
  'planner',
  'executor',
  'learner',
  'actioner',
] as const

export interface LessonsBlock {
  worked: string[]
  failed: string[]
  risks: string[]
  next_time: string[]
}

export interface LearningRecord {
  verdict: string
  reason: string
  suggested_step: string
  lessons: LessonsBlock
}

// AgentStateSnapshot: remove review?; add learning, learning_candidates, memory_cursor
// RunResponse: interrupt?, plan?, execution?, learning?, loop_score?, ...
// ResumeOverrides.refine_from: 'planner' | 'finish'
```

- [ ] **Step 2: Patch-based timeline helpers in `api.ts`**

```typescript
export function nodePatchFromUpdate(
  node: string,
  patch: AgentStateSnapshot,
): AgentStateSnapshot {
  return { ...patch, role: node }
}

export function payloadToTimelineStep(
  node: string,
  patch: AgentStateSnapshot,
  source: TimelineStep['source'],
): TimelineStep {
  return {
    id: nextStepId(),
    node,
    timestamp: Date.now(),
    state: nodePatchFromUpdate(node, patch),
    source,
  }
}

export function responseToTimelineStep(response: RunResponse): TimelineStep {
  const node = response.last_role || response.next_action || 'unknown'
  const state = patchFromRunResponse(node, response)
  return {
    id: nextStepId(),
    node,
    timestamp: Date.now(),
    state,
    source: 'resume',
  }
}

function patchFromRunResponse(
  node: string,
  response: RunResponse,
): AgentStateSnapshot {
  const base: AgentStateSnapshot = {
    role: response.last_role ?? undefined,
    rounds: response.rounds,
    max_rounds: response.max_rounds,
    approved: response.approved,
    result: response.result ?? undefined,
    refine_from: response.refine_from ?? undefined,
    loop_score: response.loop_score ?? undefined,
    skill_preview_ready: response.skill_preview_ready ?? undefined,
    memory_cursor: response.memory_cursor ?? undefined,
    plan: response.plan ?? undefined,
    execution: response.execution ?? undefined,
    tool_calls: response.tool_calls ?? undefined,
    learning: response.learning ?? undefined,
    learning_candidates: response.learning_candidates ?? undefined,
  }
  // Optionally strip fields not belonging to node; minimum: include all slice fields
  return base
}
```

In `useConsole` stream handler: accumulate with `mergeNodeUpdate` as today, but timeline step must use **patch only**:

```typescript
const step = payloadToTimelineStep(node, patch, 'stream')
localAccumulated = mergeNodeUpdate(node, patch, localAccumulated)
```

- [ ] **Step 3: skillEligibility + GraphSpine**

```typescript
// skillEligibility: look for learning / execution
const fromState = Boolean(state.execution || state.learning)

// GraphSpine: showRefineLoop when refineFrom === 'planner' only
```

Remove executor refine options from `CommandColumn.tsx` / `Workplace.tsx`.

- [ ] **Step 4: `npm run build` in frontend**

Run: `cd app/frontend && npm run build`  
Expected: exit 0

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src
git commit -m "$(cat <<'EOF'
Hydrate console timeline from node patches and RunResponse slice.

EOF
)"
```

---

### Task 9: Workplace + TraceTimeline learner/actioner UI

**Files:**
- Modify: `app/frontend/src/components/Workplace.tsx`
- Modify: `app/frontend/src/components/TraceTimeline.tsx`
- Modify: `app/frontend/src/components/InspectorStack.tsx` if it still renders Review

- [ ] **Step 1: Workplace selected-step blocks**

For `selectedStep.node`:

- `planner` → plan list  
- `executor` → execution + tools  
- `learner` → verdict, reason, suggested_step, lessons lists, candidate count  
- `actioner` → loop_score, refine_from, skill_preview_ready, memory_cursor  

Empty state only if that node’s primaries are missing.

Keep clarification / action_review XOR priority.

- [ ] **Step 2: TraceTimeline `previewForStep`**

```typescript
function previewForStep(step: TimelineStep): string {
  const s = step.state
  switch (step.node) {
    case 'planner':
      return s.plan?.length ? `plan: ${s.plan.length} steps` : '—'
    case 'executor':
      return s.execution?.summary?.slice(0, 120) || s.result?.slice(0, 120) || '—'
    case 'learner':
      return s.learning
        ? `${s.learning.verdict}: ${s.learning.reason}`.slice(0, 120)
        : '—'
    case 'actioner':
      return s.loop_score !== undefined
        ? `score ${s.loop_score} → ${s.refine_from ?? '?'}`
        : '—'
    default:
      return s.role ? `role: ${s.role}` : '—'
  }
}
```

- [ ] **Step 3: Build + lint**

Run: `cd app/frontend && npm run lint && npm run build`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/components
git commit -m "$(cat <<'EOF'
Show learner and actioner payloads in Workplace and timeline.

EOF
)"
```

---

### Task 10: Docs + history + IMPLEMENTATION sync

**Files:**
- Modify: `docs/IMPLEMENTATION.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/DESIGN.md` if spine mentioned
- Create: `docs/histories/2026-07/20260713-HHMM-learner-actioner-loop.md`

- [ ] **Step 1: Update diagrams and tables**

Replace all `planner → executor → reviewer → actioner → memorize` with  
`planner → executor → learner → actioner`.  
Document soft-skip, commit-in-actioner, route planner|END, `RunResponse.interrupt` + state slice, `learning` fields.

- [ ] **Step 2: History entry** per `docs/HISTORY_GUIDE.md`

- [ ] **Step 3: Final verification**

Run:

```bash
pytest tests/ -q -k "not live"
cd app/frontend && npm run build
```

Expected: all PASS / build OK

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "$(cat <<'EOF'
Document learner loop and actioner-owned memorize.

EOF
)"
```

---

## Spec coverage checklist

| Spec requirement | Task(s) |
|------------------|---------|
| Four-node graph, no memorize node | 5 |
| reviewer → learner + lessons/candidates | 1, 3 |
| Soft-skip fail path | 5 |
| Pass path score+HITL+commit | 4, 5 |
| route planner\|END only | 2, 5 |
| normalize executor→planner | 2, 5, 8 |
| RunResponse.interrupt + state slice | 7 |
| Timeline node patches + Workplace | 8, 9 |
| Skill eligibility on learning | 6 |
| Docs | 10 |

## Placeholder / consistency self-review

- Route key remains `"finish"` mapped to `END` (matches existing builder), not a Python `END` return value.
- State key is `learning` (not `review`); frontend + skills must match.
- `commit_round_memories` returns no `role`; actioner sets `role: "actioner"`.
- Soft-skip leaves memory lists unchanged.
- No TBD steps remain in tasks above.
