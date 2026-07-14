# Thread list for StatusBar attach / recovery

Date: 2026-07-14  
Status: approved for planning  
Surface: FastAPI `GET /threads`; harness console StatusBar  
Related:

- [`2026-07-13-thread-run-skills-design.md`](2026-07-13-thread-run-skills-design.md) (`app/threads/` artifacts)
- [`docs/exec-plans/tech-debt-tracker.md`](../../exec-plans/tech-debt-tracker.md) (missing `GET /threads`)
- [`docs/DESIGN.md`](../../DESIGN.md) (StatusBar / Command layout)

## Problem

Operators can only recover a prior run if they still have the `thread_id` in
console memory or disk notes. Artifacts already live under `app/threads/`
(`.index.json` + `meta.json` + stage markdown), but there is no list API and the
StatusBar only shows a truncated id for the *current* thread. Resume, distill,
and “improve this run again” stay awkward.

## Goals

1. `GET /threads` lists existing thread artifact folders under `app/threads/`
   (or `HARNESS_THREADS_DIR`).
2. Console StatusBar exposes a picker of those threads.
3. Selecting a thread **attaches** it for recovery/improvement: set
   `thread_id`, fill Task + Plan from meta — **without** hydrating checkpoint
   state or rebuilding the timeline.
4. Clear the tech-debt row that called for a thread list endpoint (artifact-
   backed, not checkpointer-backed, for v1).

## Non-goals

- Loading LangGraph checkpoint / timeline into the console on select.
- `has_checkpoint` probes or checkpointer enumeration.
- Workplace idle list or Command “Threads” `<details>` panel.
- Browsing / editing stage markdown in the UI.
- Pruning old thread folders.
- New write/delete thread routes.

## Decisions

| Decision | Choice |
| --- | --- |
| Placement | StatusBar picker (replaces static short-id chip) |
| Select behavior | Attach-only: `thread_id` + Task + Plan from list/meta |
| Timeline / phase | Unchanged on attach (no reset, no `/resume`) |
| List source | `app/threads/.index.json` → `meta.json` per slug |
| Checkpoint | Not consulted for list or attach |
| Sort | Newest `started_at` first |
| Corrupt entries | Skip + warn; never fail the whole list with 500 |
| Streaming | Disable picker while `phase === 'streaming'` |
| New thread | Existing reset: new UUID + clear run state; picker shows current |

## API

### `GET /threads`

Response: `ThreadSummary[]`

```json
[
  {
    "thread_id": "bef681c6-6871-4a1f-b7a9-c6a263cb7c7f",
    "task": "write QA test cases for html test",
    "slug": "write-qa-test-cases-for-html-test",
    "started_at": "2026-07-14T08:42:21.307901+00:00",
    "plan": []
  }
]
```

| Field | Source |
| --- | --- |
| `thread_id` | index key (prefer) / `meta.thread_id` |
| `task` | `meta.task` |
| `slug` | index value / `meta.slug` / dir name |
| `started_at` | `meta.started_at` (ISO string) |
| `plan` | `meta.plan` or `[]` |

Resolution order:

1. Read `.index.json` (`thread_id` → relative slug).
2. For each entry, if `threads_root()/slug` is a dir with readable `meta.json`,
   emit a summary.
3. Sort by `started_at` descending (missing timestamps last).

Empty root / missing index → `[]`. Disk errors while reading one meta → skip
that entry and continue.

No `GET /threads/{id}` in v1; the list payload is enough for attach.

## Backend components

```text
app/services/thread_artifacts.py
  list_threads(*, root=None) -> list[ThreadSummary]
  # ThreadSummary may be a TypedDict here; API layer maps to Pydantic

app/schemas/threads.py
  ThreadSummary (Pydantic): thread_id, task, slug, started_at, plan

app/api/threads.py
  GET "" under prefix /threads

app/core/app.py
  include_router(threads_router)
```

Reuse `threads_root()`, `_read_index()`. Do not invent a second index format.

## Frontend

| Piece | Role |
| --- | --- |
| `fetchThreads()` in `lib/api.ts` | `GET /api/threads` |
| `ThreadSummary` in `types/api.ts` | Mirror backend fields |
| `useThreads` hook | Load on mount; `refreshThreads`; expose list + error + loading |
| `StatusBar` | Native `<select>` (or compact picker) of threads; option label = truncated task (fallback short id); title = full task + id |
| `App` / `useConsole` | `attachThread({ threadId, task, plan })` — set id, task, planText; do **not** clear timeline/phase/runResponse |

Behavior details:

- While streaming, select is disabled.
- Current thread that is not yet in the library still appears as the selected
  value (synthetic option: current short id / “Current thread”).
- Refresh **required**: fetch on mount; re-fetch when a `Start thread` / skill
  run finishes successfully (so the new artifact row appears). Optional: a
  small refresh control beside the picker. Focus/visibility re-fetch is not
  required.
- List load failure: keep showing current id; set a quiet `title`/hint on the
  StatusBar control (no modal).

## Error handling

| Case | Behavior |
| --- | --- |
| Missing `app/threads/` | `[]` |
| Bad `.index.json` | Treat as empty index; log warning |
| Bad / missing `meta.json` for one slug | Skip entry; log warning |
| `GET /threads` unexpected failure | 500 with detail; UI keeps current id |

Attach never calls the graph; it only mutates console state.

## Testing

Every feature maps to a named test in the implementation plan matrix (F1–F20).

- Unit (`HARNESS_THREADS_DIR` temp): empty root; sorted by `started_at`; empty
  timestamp last; corrupt meta skip; missing dir skip; index `thread_id`
  preferred; missing `plan` → `[]`; `init` then list
- API: mocked empty/summary JSON; unmocked `HARNESS_THREADS_DIR` read via
  `GET /threads`
- Frontend pure helpers (`threadAttach`): attach fields only; disable while
  streaming; option label truncate — `node --test` (no Vitest)
- Manual smoke S1–S5: StatusBar list, attach preserves timeline, disable while
  running, refresh after settle, New thread reset
- No Playwright requirement for v1

## Docs

- Document `GET /threads` and attach-only StatusBar behavior in
  `docs/IMPLEMENTATION.md` (replace “no public artifact API in v1” for list).
- Note StatusBar picker briefly in `docs/FRONTEND.md` / `docs/DESIGN.md` if
  those StatusBar sections would otherwise be stale.
- Remove or rewrite the tech-debt row:
  `No thread list endpoint | Console uses manual thread_id | GET /threads…`
  → done via artifact list (checkpoint metadata deferred).
- History entry when implementation lands (not at spec time).

## Success criteria

1. Console can list threads present under `app/threads/`.
2. Picking one sets `thread_id` and fills Task + Plan without wiping the
   timeline or calling `/resume`.
3. Operator can then Distill or Continue against that id when the checkpointer
   still has the thread (existing resume path unchanged).
4. Streaming disables the picker; New thread behavior unchanged.

## Out of scope follow-ups

- Checkpoint hydrate into timeline/Workplace.
- `has_checkpoint` badge on each option.
- Command-column Threads panel or Workplace idle list.
- Deduping multiple folders that share one `thread_id` (index is authoritative).
