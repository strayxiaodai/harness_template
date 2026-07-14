# Thread run artifacts + skills under `app/`

Date: 2026-07-13  
Status: approved for planning  
Surface: FastAPI harness run/stream/resume; on-disk notes under `app/threads/`;
distilled skills under `app/skills/`  
Related:

- [`docs/IMPLEMENTATION.md`](../../IMPLEMENTATION.md) — agent loop, stream API, skills routes
- [`skills/store.py`](../../../skills/store.py) — `slugify`, `skills_root`, write/list

## Problem

Harness threads exist as LangGraph checkpoints and console UI state only.
Operators (and later distill / pickup) have no on-disk folder keyed by the
Command → Task text where each stage’s contents and status can be inspected
while a thread runs.

Separately, distilled harness skills currently default to `.cursor/skills/`,
which mixes Cursor agent skills (e.g. impeccable) with harness playbooks.
Harness distill/save should live under `app/skills/` instead.

## Goals

1. On **Start thread** (`POST /run` or `POST /stream`, including skill-run that
   starts a new thread), create `app/threads/<task-slug>/`.
2. Maintain four stage markdown files that record **contents and status** for
   `planner`, `executor`, `learner`, and `actioner`.
3. Update those files as the run progresses (stream updates and resume
   completions).
4. Keep all thread artifact trees **gitignored** (local pickup only).
5. Change default distilled-skill root to `app/skills/` (create the directory
   on first write if missing). `HARNESS_SKILLS_DIR` still overrides.

## Non-goals

- Moving or rewriting Cursor skills under `.cursor/skills/` (e.g. impeccable).
- UI for browsing or editing artifact folders.
- A separate `timeline.json` / `snapshot.json` / `plan.md` surface in v1.
- Writing artifacts from the browser (File System Access API).
- Creating a new folder on every resume of the same `thread_id`.
- Automatic migration of existing playbooks already saved under `.cursor/skills/`.

## Decisions

| Decision | Choice |
| --- | --- |
| Thread root | `app/threads/` (under `app/`, isolated from package modules) |
| Thread folder name | `slugify(task)` via `skills.store.slugify`; collision → `<slug>-<thread_id[:8]>` |
| Stage files | `planner.md`, `executor.md`, `learner.md`, `actioner.md` |
| Meta | `meta.json` with `thread_id`, `task`, `slug`, `started_at`, `dir` |
| Thread git | `app/threads/` in `.gitignore` |
| Thread override | `HARNESS_THREADS_DIR` for tests / custom root |
| Skills root | Default `app/skills/<slug>/SKILL.md` (+ `harness.json`); mkdir parents on write |
| Skills override | `HARNESS_SKILLS_DIR` unchanged |
| Skills git | Tracked (version distilled playbooks); keep `app/skills/.gitkeep` if empty |
| Failure mode | Log warning; never fail the graph run |
| Multi-round | Append `## Round N` when `rounds` increases; rewrite that section if the same round visits again |
| Resume lookup | `app/threads/.index.json` maps `thread_id` → relative slug dir (updated on init) |
| Wiring | Thread helper from `run_harness` / `stream_harness` / `resume_harness`; skills path via `skills_root()` |
| Public API | No new routes in v1 |

## Layout

### Thread artifacts

```text
app/threads/
  .index.json              # { "<thread_id>": "<task-slug>", ... } — also gitignored
  <task-slug>/
    meta.json
    planner.md
    executor.md
    learner.md
    actioner.md
```

Example slug: task `Summarize docs/IMPLEMENTATION.md API section` →
`summarize-docs-implementation-md-api-section` (truncated by `slugify` max length).

### Distilled skills

```text
app/skills/
  .gitkeep
  <skill-slug>/
    SKILL.md
    harness.json
```

`skills_root()` defaults to repo `app/skills` (create on write). Cursor’s
`.cursor/skills/impeccable/` is unrelated and stays put.

## Stage markdown format

Each stage file uses a short YAML-ish status header in markdown, then contents.
On **thread start**, create all four with `status: pending` and empty contents.

```markdown
# planner

- status: pending | running | paused | complete | error
- round: 1
- updated_at: 2026-07-13T22:59:00+00:00

## Round 1

### Contents

- plan:
  - step one
  - step two
- memory_context: ...
```

| File | Primary contents to record |
| --- | --- |
| `planner.md` | `plan`, `memory_context` |
| `executor.md` | tool / execution `result` (and any tool summaries present on state) |
| `learner.md` | `learning` (verdict, lessons), `learning_candidates`, `suggested_step`, `approved` |
| `actioner.md` | action score / HITL outcome, `refine_from`, memory commit summary when present |

**Status mapping**

| Situation | Status |
| --- | --- |
| Folder created, node not yet run this round | `pending` |
| Stream chunk for this node in flight (optional) | `running` |
| HITL pause after this node (or action-review for actioner) | `paused` |
| Node update applied successfully | `complete` |
| Stream/run error while this node was active | `error` |

If a lightweight `running` write is costly, it is acceptable to jump from
`pending` → `complete` / `paused` / `error` on the node boundary only.

## Write triggers

| Event | Action |
| --- | --- |
| `run_harness` / `stream_harness` start | Resolve dir → write `meta.json` → seed four `.md` as `pending` |
| Stream `updates` chunk for node `X` | Write `X.md` Round N with payload + status (`complete`, or `paused` if interrupt) |
| Stream `final` / `run_harness` return | Refresh all four stage files from latest snapshot values |
| `resume_harness` return | Resolve dir via `.index.json[thread_id]`; refresh stages from new snapshot |
| Plan override on resume | Reflect new plan in `planner.md` Round N contents |

**Folder resolution on resume:** Read `threads_root()/.index.json`. If
`thread_id` is missing, skip quietly (do not create a folder — `ResumeRequest`
has no task).

## Components

```text
app/services/thread_artifacts.py
  threads_root() -> Path
  resolve_thread_dir(task, thread_id) -> Path
  init_thread_artifacts(task, thread_id, plan) -> Path
  record_node_update(thread_dir, node, round, payload, status)
  refresh_from_snapshot(thread_dir, snapshot_values, status_hints)

skills/store.py
  skills_root() -> Path   # default: <repo>/app/skills
```

Call sites: `app/services/harness.py` (`run_harness`, `stream_harness`,
`resume_harness`). Keep writes side-effect only; do not change
`RunResponse` shape.

Reuse `skills.store.slugify` for thread folder naming. Do not write thread
artifacts into package dirs (`api`, `core`, `frontend`, `services`, `db`,
`schemas`, `skills`).

## Error handling

- Disk / permission errors: `logger.warning`, continue run.
- Unknown node names in stream chunks: ignore (only the four stage files).
- Empty task: existing API validation already requires task for start; do not
  invent a folder without a task.

## Testing

- Unit tests with temp `HARNESS_THREADS_DIR`:
  - init creates four files + meta
  - collision suffix when slug exists
  - node update writes planner/executor/learner/actioner contents + status
  - write failure does not raise into harness
- Skills store: default `skills_root()` resolves under `app/skills`; write creates
  the directory; existing `HARNESS_SKILLS_DIR` / patched-root tests still pass
- Extend or add harness service tests with patched artifact helper if useful.

## Docs

- Document `app/threads/` + `HARNESS_THREADS_DIR` in `docs/IMPLEMENTATION.md`.
- Update skills path docs from `.cursor/skills/` → `app/skills/` in
  `IMPLEMENTATION.md`, `ARCHITECTURE.md`, `SECURITY.md`, and API docstring in
  `app/api/skills.py`.
- Add `app/threads/` to root `.gitignore`.
- Add tracked `app/skills/.gitkeep`.
- History entry when implementation lands.

## Out of scope follow-ups

- Console link to open the thread folder.
- Feeding stage markdown back into distill automatically.
- Pruning old thread folders.
- One-shot migrator for playbooks already under `.cursor/skills/`.
