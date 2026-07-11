# Action-end memory review (HITL)

Date: 2026-07-11  
Status: approved for planning  
Surface: agent loop (`actioner` / `memorize`) + harness console Workplace  
Related: [`2026-07-11-center-workplace-timeline-drawer-design.md`](2026-07-11-center-workplace-timeline-drawer-design.md) (center Workplace placement)

## Problem

Memorization is a mandatory peer graph step after the actioner
(`actioner → memorize → route`). Operators cannot see or edit what will be
stored. Skill-preview HITL already pauses inside the actioner, so memory and
skill decisions are split across timing and surfaces. With node-boundary
`interrupt_after` also on `memorize`, HITL operators can hit a second empty
pause after memory already wrote.

## Goals

1. Treat memorization as an **option under the action step**, not a silent
   always-on write.
2. When HITL is on and action ends, show **candidate memory details** in the
   center Workplace so the operator can keep, drop, or edit before store.
3. Merge skill-preview readiness into the **same** action-end interrupt when
   both apply (one pause).
4. When HITL is off, **auto-store** extracted memories (today’s unattended
   behavior).
5. Keep memorize as a thin **commit** node (embed + upsert + cursor).
6. Avoid a second HITL pause solely for memorize after the decision already
   happened in actioner.

## Non-goals

- Changing memory extract prompts or importance thresholds (reuse existing
  extract path).
- Moving Distill / skill authoring into the center (Command keeps Distill).
- Per-message source highlighting or chat replay in the Workplace.
- Clarification interrupt redesign (still highest Workplace priority; may
  still run *before* action review in the same actioner invocation).
- Adding new RAG backends or changing store layout.

## Decisions

| Decision | Choice |
| --- | --- |
| Topology | Actioner extracts + optional HITL; memorize commits only |
| HITL off | Auto-accept filtered candidates → memorize stores |
| Decision UI | Editable per candidate (keep / drop / edit fields) |
| Skill preview | Same interrupt (`action_review`); Distill stays in Command |
| Empty extract | No memory section; still pause if skill-preview ready |
| Extract failure / RAG off | Empty candidates; do not block the loop |
| Bare resume (`True` / no memories) | **Keep all** pending candidates as extracted |
| `HITL_PAUSE_NODES` | **Remove `memorize`**; keep planner / executor / reviewer |
| Interrupt mechanism | Dynamic `interrupt()` inside actioner (same class as today’s skill preview), not `interrupt_after` on actioner |

## Graph & control flow

```text
planner → executor → reviewer → actioner → memorize → route
                              │
                              └─ HITL on + (candidates ∨ skill_preview_ready):
                                   interrupt(kind=action_review)
```

`HITL_PAUSE_NODES` becomes: `planner`, `executor`, `reviewer`  
(no `memorize`, no `actioner` — actioner uses in-node `interrupt()` only).

### Actioner order of operations

Exact order inside one invocation (clarification may pause earlier):

1. Score the loop (unchanged; may ask clarification via existing helper).
2. If RAG disabled or service missing: treat candidates as `[]` (no extract).
3. Else extract memory **candidates** from `messages[memory_cursor:]` using
   existing extract helpers; apply importance filter; **do not store**.
4. Assign stable ids `m0`…`mN` and write `pending_memories`.
5. Compute `skill_preview_ready` from score (threshold unchanged, 80).
6. If `human_in_the_loop` and (`pending_memories` nonempty **or**
   `skill_preview_ready`):
   - `resume_value = interrupt({ kind: "action_review", ... })`
   - Map `resume_value` → `approved_memories` (see Resume rules).
   - **Do not re-extract** after resume. If LangGraph re-enters the node from
     the top, prefer already-written `pending_memories` in state over a second
     LLM extract for the same cursor (idempotent).
7. Else: `approved_memories = pending_memories` (auto-accept).
8. Always set `rounds`, `refine_from`, `loop_score`, `skill_preview_ready`,
   `pending_memories`, `approved_memories` before return.
9. Emit `role: "actioner"`. Replace standalone `kind: "skill_preview"` —
   new code emits only `action_review`.

### Memorize (commit-only)

1. Read `approved_memories` (list; default `[]` if absent).
2. If nonempty → embed + upsert via existing store path.
3. Always advance `memory_cursor` to `len(messages)` on success or soft
   failure (existing warn-and-continue pattern).
4. Clear `pending_memories` and `approved_memories` to `[]` after commit
   attempt so the next round cannot reuse stale approvals.
5. Emit `role: "memorize"`; routing unchanged (`route_after_action`).

## Schemas

### Pending / approved item (state + interrupt)

```text
PendingMemory:
  id: str                 # "m0", "m1", …
  content: str            # min length 1 after trim
  memory_type: fact | preference | entity | summary
  importance: float       # clamped to [0, 1]

ApprovedMemory:
  content / memory_type / importance   # same as ExtractedMemory (no id)
```

Implement as TypedDict (or small Pydantic models mirrored into state dicts).
`pending_memories` / `approved_memories` are `list[dict]` on `AgentState`.

### Interrupt value

```json
{
  "kind": "action_review",
  "node": "actioner",
  "score": 84,
  "threshold": 80,
  "skill_preview_ready": true,
  "message": "Review memories before they are stored. Skill preview is available.",
  "memories": [
    {
      "id": "m0",
      "content": "User prefers pytest over unittest",
      "memory_type": "preference",
      "importance": 0.8
    }
  ]
}
```

Message templates (pick one):

| Condition | Message |
| --- | --- |
| memories + skill | Review memories before they are stored. Skill preview is available. |
| memories only | Review memories before they are stored. |
| skill only | Loop score qualifies for skill preview. Nothing to store this round. |

### Resume value (`Command(resume=…)`)

Preferred client shape (Workplace Continue):

```json
{
  "memories": [
    {
      "id": "m0",
      "keep": true,
      "content": "User prefers pytest",
      "memory_type": "preference",
      "importance": 0.9
    },
    { "id": "m1", "keep": false }
  ]
}
```

API: `ResumeRequest.interrupt_resume` carries this object (same path as today’s
generic non-clarification resume). Optional later: typed
`ActionReviewResume` on the request; not required for v1 if
`interrupt_resume` is documented.

### Resume mapping rules

Given `pending_memories` in state and `resume_value` from `interrupt()`:

| Resume value | Resulting `approved_memories` |
| --- | --- |
| `True` / `None` / `{}` / missing `memories` | **Keep all** pending (as extracted) |
| `{ "memories": [] }` | Store nothing |
| `{ "memories": [...] }` | For each pending id: if a resume row has `keep: true`, take edited fields (fallback to pending); unknown ids ignored; pending ids omitted from the list are treated as **drop** when any `memories` array was provided |

Field coercion:

- Trim `content`; drop row if empty after trim even if `keep: true`.
- Unknown `memory_type` → keep pending type (or `"fact"` if pending missing).
- `importance` clamped to `[0, 1]`; non-numeric → pending importance.

## Workplace UI

Extend center Workplace priority:

1. `kind === 'clarification'` → clarification form (unchanged)
2. `kind === 'action_review'` → **Action review** workplace
3. Else selected timeline step → payloads
4. Else idle

### Action review panel

- Amber HITL treatment; title **Action review**
- Show loop score (+ threshold when skill-ready)
- If `skill_preview_ready`: short note that Distill / skill preview is
  available in **Command** (no Distill form in center)
- Memory list (if any): keep checkbox (**default on**), editable content,
  type select, importance 0–1
- Empty memories: “Nothing to store this round”
- Primary **Continue** in Workplace; secondary Continue in Command; keyboard
  `r` uses the same draft builder
- Continue payload: `interrupt_resume: { memories: [...] }` with current
  keep/edits. Secondary Continue / `r` without opening edits should still
  send keep-all for current drafts (checkboxes default on), **not** bare
  `True`, so behavior matches the visible UI
- Inspector auto-collapses while this interrupt is active (same helper as
  clarification: treat `action_review` as a workplace HITL kind)

### Draft state

Extend `useResumeDraft` (or sibling hook) to seed memory drafts from
`interrupt.value.memories` when `kind === 'action_review'`, reset on
`interrupt.id` change, and include `interrupt_resume` in `buildPayload`.

## Audit

Actioner `route_decision` audit payload gains:

- `pending_memory_count`
- `approved_memory_count` (after resume / auto path)
- `action_review_interrupted`: bool

Memorize may log existing store success path; no new audit type required for
v1.

## Errors

| Case | Behavior |
| --- | --- |
| RAG disabled / service missing | `pending_memories=[]`; skill-only pause still allowed |
| Extract throws | Log; `pending_memories=[]`; continue |
| Store fails in memorize | Warn, advance cursor, clear pending/approved, continue |
| Bad resume payload | Coerce per rules above; never crash |
| Clarification then action review | Two sequential pauses in one actioner pass if both apply (existing clarification behavior first) |

## Files likely touched

| Area | Files |
| --- | --- |
| Extract without store | `rag/ingest/memory_extract.py` (split or flag), `agent/actioner.py` |
| Commit | `agent/memorize.py` |
| State / schemas | `graph/state.py`, optional `graph/schemas.py` |
| HITL pause list | `graph/builder.py` |
| API resume | `app/schemas/run.py`, `app/services/harness.py` (passthrough) |
| Frontend | `Workplace.tsx`, `useResumeDraft.ts`, `types/api.ts`, small `actionReview.ts` helper |
| Docs | `IMPLEMENTATION.md`, `ARCHITECTURE.md`, `FRONTEND.md` / `DESIGN.md` as needed |
| Tests | `test_actioner.py`, `test_memory_pipeline.py`, `test_graph.py`, frontend unit if present |

## Docs to update (implementation task)

- `docs/IMPLEMENTATION.md` — loop narrative, HITL kinds (`action_review`),
  `HITL_PAUSE_NODES` without memorize, state fields, resume examples
- `docs/ARCHITECTURE.md` — actioner owns memory option; memorize commits
- `docs/FRONTEND.md` / `docs/DESIGN.md` — Workplace interrupt kinds

## Success criteria

1. HITL on + candidates → center shows editable memories **before** any store.
2. Operator can keep, drop, and edit content/type/importance; only kept,
   non-empty rows are upserted.
3. HITL on + skill-preview ready + (optional) memories → **one**
   `action_review` interrupt (no separate `skill_preview` kind).
4. HITL off → filtered candidates auto-approved and stored without pause.
5. Empty extract does not invent memories; skill-only pause still works.
6. After action review, HITL does **not** stop again solely on memorize.
7. Bare / empty resume keeps all pending; explicit `{ "memories": [] }` stores
   nothing.
8. Clarification Workplace priority unchanged; may still precede action review.
9. Stale `pending_memories` / `approved_memories` cleared after memorize.
10. Tests cover: extract+interrupt, HITL-off auto path, resume keep/edit/drop,
    bare resume keep-all, empty+skill pause, pause-list without memorize,
    Workplace `action_review` draft → `interrupt_resume`.

## Verification

- API E2E gate: `pytest tests/test_action_review_api.py::test_action_review_resume_keeps_edits_drops_and_commits -v`
  (design: `docs/superpowers/specs/2026-07-11-action-review-api-e2e-test-design.md`)
- Unit: `pytest tests/test_actioner.py tests/test_memory_pipeline.py tests/test_graph.py -v`
- API: `/resume` with `interrupt_resume.memories`; bare resume keep-all
- Frontend: Workplace action-review panel; primary + secondary Continue; `r`
- Manual matrix: HITL on/off × (memories / none) × (score ≥80 / &lt;80)

## Out of scope follow-ups

- Typed `ActionReviewResume` on `ResumeRequest` (v1 uses `interrupt_resume`)
- Per-memory audit events (`rag_memory_write` already planned elsewhere)
- Editing importance thresholds from the UI
