# Learner loop + fold memorize into actioner + stage UI

Date: 2026-07-13  
Status: approved for planning  
Surface: LangGraph topology, FastAPI `RunResponse`, harness console  
Related:

- [`2026-07-11-action-review-memory-hitl-design.md`](2026-07-11-action-review-memory-hitl-design.md) (HITL memory review)
- [`2026-07-11-center-workplace-timeline-drawer-design.md`](2026-07-11-center-workplace-timeline-drawer-design.md) (Workplace payloads)

This file supersedes the earlier draft titled
`2026-07-13-fold-memorize-into-actioner-design.md` (now a stub pointer).

## Problem

1. **Memorize is a peer graph node**, so the console exposes five stages. Memory
   commit should be part of **action**, not a separate operator-facing step.
2. **Reviewer is check-only.** Operators want a **learner** that keeps full
   review functions and also learns / challenges whether the round is good
   enough to make actioner work meaningful (lessons + memory candidates).
3. **Refine can jump straight to executor.** Desired policy: after actioner,
   continue always returns to **planner**; only `END` finishes the thread.
4. **Stage results often missing in UI:** no `interrupt` on `RunResponse`,
   sparse HITL resume timeline steps, Workplace omits actioner (and will omit
   learner) payloads.

## Goals

1. Operator-facing loop: `planner → executor → learner → actioner`.
2. Rename/evolve `reviewer` → `learner` with review + lessons + learning
   candidates.
3. Fold memory commit into `actioner`; remove `memorize` graph node.
4. Actioner always runs after learner (soft-skip on fail); on pass, score +
   HITL + commit.
5. `route_after_action`: `planner | END` only (no direct executor branch).
6. Expose `interrupt` + compact state slice on `RunResponse`; hydrate console
   timeline/Workplace so each stage can show results.

## Non-goals

- Hard-skip graph edges that bypass actioner on fail (rejected; soft-skip
  chosen instead).
- Changing RAG backends, extract importance thresholds, or Distill UI placement.
- Clarification interrupt redesign.
- Nested LangGraph subgraph under actioner.
- Full message history on API responses.

## Decisions

| Decision | Choice |
| --- | --- |
| Stages | `planner`, `executor`, `learner`, `actioner` |
| Reviewer rename | Node/module/prompts/UI: `reviewer` → `learner` |
| Learner output | Verdict fields + `lessons` + `learning_candidates` |
| Fail → actioner | Soft-skip: actioner still runs; no score HITL/commit; route only |
| Pass → actioner | Score → merge candidates ∪ extract → HITL → commit → route |
| Memorize | Helper inside actioner; no graph node |
| Post-action route | `planner` (continue) or `END` (approved / finish / max rounds) |
| `suggested_step` / `refine_from` | `planner \| finish` only; map legacy `executor` → `planner` |
| HITL pause nodes | `planner`, `executor`, `learner` |
| Fail `loop_score` | `0`, `skill_preview_ready: false` |
| Soft-skip memory lists | Leave `pending_memories` / `approved_memories` unchanged |
| Learning state key | `learning` record (replaces `review` on state) |
| Timeline steps | Store **node patch** per step; `accumulated` stays merged |
| API | `interrupt` + compact stage fields on `RunResponse` |

## Graph topology

```text
START → planner → executor → learner → actioner → (route_after_action)
                                                    ├─ planner
                                                    └─ END
```

```text
HITL_PAUSE_NODES = planner | executor | learner
```

Action-review remains in-node `interrupt()` inside actioner (pass path only).

### Route rules (`route_after_action`)

| Condition | Next |
| --- | --- |
| `approved` is true | `END` |
| `refine_from == "finish"` | `END` |
| `rounds >= max_rounds` | `END` |
| else | `planner` |

Never route to `executor` from actioner.

## Learner (ex-reviewer)

### Responsibilities

1. **Challenge** — same strict review as today: correctness, security, scope,
   testability.
2. **Verdict** — `pass` / `fail`, reason, `suggested_step` ∈ `{planner, finish}`.
3. **Learn** — structured lessons and optional memory-shaped candidates for
   actioner.

Prompt order: challenge first; then emit lessons; on pass, also propose
`learning_candidates` when durable learnings exist. On fail, lessons may
describe what is missing; candidates may be empty.

### Structured output (`LearningResult`)

```text
verdict: pass | fail
reason: str
suggested_step: planner | finish
lessons:
  worked: list[str]
  failed: list[str]
  risks: list[str]
  next_time: list[str]
learning_candidates: list[PendingMemory-shaped dict]
  # id, content, memory_type, importance — same as action-review rows
```

### State writes

```text
role: "learner"
approved: verdict == "pass"
learning: { verdict, reason, suggested_step, lessons }
learning_candidates: [...]
```

Single cutover rename: stop writing `review` / `role: "reviewer"`. In-memory
local threads may break; no dual-read required for v1.

### HITL

`interrupt_after` includes `learner` (replacing `reviewer`).

## Actioner

### Soft-skip path (`approved` is false)

1. Do **not** call score LLM.
2. Do **not** extract/merge memories; do **not** interrupt; do **not** commit.
3. Set `role: "actioner"`, increment `rounds`,
   `refine_from` from `learning.suggested_step` (normalize any legacy
   `executor` → `planner`), `loop_score: 0`, `skill_preview_ready: false`.
4. Leave `pending_memories` / `approved_memories` unchanged.
5. Return; router sends to `planner` or `END` per rules.

### Pass path (`approved` is true)

1. Score loop (LLM + heuristic fallback), include **lessons** in score context.
2. Build pending: merge `learning_candidates` with extract-from-messages
   (dedupe by normalized content; stable ids `m0…`).
3. If HITL and (pending or `skill_preview_ready`): `interrupt(action_review)`.
4. Map resume → `approved_memories`.
5. **Commit** via helper extracted from today’s `memorize_agent`
   (`commit_round_memories` in `agent/memorize.py`).
6. Advance `memory_cursor`; clear pending/approved; audit `route_decision`.
7. Return `role: "actioner"` with score fields + `refine_from` + `rounds`.

Commit soft-failure: warn, still advance cursor and clear lists (parity with
today’s memorize node).

## API

### `RunResponse.interrupt`

From `snapshot.interrupts[0]` when present (`id` + `value`), else `null`.
Surfaced on `/run`, `/resume`, and stream `final`.

### Compact state slice

Optional fields from checkpoint values (no messages):

| Field | Stage |
| --- | --- |
| `plan` | planner |
| `execution`, `tool_calls` | executor |
| `learning`, `learning_candidates` | learner |
| `result` | existing |
| `refine_from`, `loop_score`, `skill_preview_ready`, `memory_cursor` | actioner |

Also update resume override `refine_from` allowlist to `planner | finish`
(drop `executor`, or accept and normalize to `planner`).

Frontend builds timeline **patches** from stream node updates and from this
slice on resume/final.

## Console UI

### Spine / types

`GRAPH_NODES = ['planner', 'executor', 'learner', 'actioner']`

### Workplace

Priority:

1. Clarification interrupt  
2. Action-review interrupt  
3. Selected timeline step (patch payloads)  
4. Idle  

| Node | Primary blocks |
| --- | --- |
| planner | Plan |
| executor | Execution, Tools |
| learner | Verdict, reason, suggested_step, lessons, candidate count |
| actioner | Loop score, refine_from, skill_preview_ready, memory_cursor / commit note |

### Timeline

Each step stores the **node patch** (+ `role`). Previews are node-aware.
`accumulated` remains merged for Distill / eligibility.

Skill eligibility and frontend checks that today look for `review` must read
`learning` (and still require executor output / completed loop + score gate).

## Module / file impact (expected)

| Area | Change |
| --- | --- |
| `graph/builder.py` | learner node; drop memorize; route from actioner |
| `graph/routing.py` | `planner \| END` only |
| `agent/reviewer.py` → `agent/learner.py` | Rename + lessons/candidates |
| `agent/actioner.py` | Soft-skip vs pass+commit; consume `learning` |
| `agent/memorize.py` | Helper only (`commit_round_memories`) |
| `graph/schemas.py` / `graph/state.py` | `LearningResult`, state keys |
| `config/prompts.yaml` | `learner` prompt |
| `app/schemas/run.py` + `snapshot.py` | `interrupt` + state slice |
| Frontend types, spine, Workplace, timeline, resume hydrate | learner + patches |
| Docs / tests | Full rename + topology |

## Tests

- Graph: no memorize node; route never returns `executor`.
- Learner: pass/fail, lessons, candidates, `approved` mapping.
- Actioner soft-skip: fail → no commit/interrupt; `loop_score == 0`.
- Actioner pass: merge candidates + extract; HITL; commit once.
- API: interrupt present during action_review; null when complete.
- Skill eligibility: fail soft-skip does not unlock Distill; pass + score
  threshold unchanged in spirit.
- Console mapping: resume hydrate includes learner/actioner fields.

## Success criteria

1. Four graph nodes: planner, executor, learner, actioner.
2. Continue after actioner always re-enters planner unless END.
3. Fail rounds do not store memories or open action-review.
4. Pass rounds can HITL memories (learner + extract) and commit inside actioner.
5. Workplace/timeline can show each stage’s primary results, including action
   review when `interrupt` is present.
6. Docs match as-built.

## Migration notes

- Replace `review` with `learning` in one cutover.
- Map any remaining `suggested_step: "executor"` to `"planner"` at normalize
  boundaries (learner output + actioner refine_from + resume overrides).
- Update GraphSpine refine-loop UX: loop target is always planner when shown.
