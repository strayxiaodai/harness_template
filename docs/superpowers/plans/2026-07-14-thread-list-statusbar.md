# Thread List StatusBar Attach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the console list prior threads under `app/threads/` via `GET /threads` and attach one from the StatusBar (set `thread_id` + Task + Plan) without hydrating checkpoint state.

**Architecture:** Extend `thread_artifacts` with `list_threads()` over `.index.json` + `meta.json`. Expose `GET /threads` like skills. Frontend `useThreads` + StatusBar `<select>` calls `attachThread` on `useConsole` (id + task + plan only). Refresh the list on mount and when a run settles.

**Tech Stack:** FastAPI + Pydantic, existing `thread_artifacts`, React StatusBar + hooks. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-07-14-thread-list-statusbar-design.md`](../specs/2026-07-14-thread-list-statusbar-design.md)

---

## Feature → test matrix (required)

Every shippable feature must have a named test (or smoke id). Do not mark a task done until its row is green.

| ID | Feature | Automated test | Task |
|----|---------|----------------|------|
| F1 | Empty threads root → `[]` | `test_list_threads_empty` | 1 |
| F2 | Index + meta → summaries with task/slug/plan | `test_list_threads_sorted_by_started_at` | 1 |
| F3 | Newest `started_at` first | `test_list_threads_sorted_by_started_at` | 1 |
| F4 | Empty `started_at` sorts last | `test_list_threads_empty_started_at_sorts_last` | 1 |
| F5 | Corrupt / non-object meta skipped | `test_list_threads_skips_corrupt_meta` | 1 |
| F6 | Index points at missing dir → skip | `test_list_threads_skips_missing_dir` | 1 |
| F7 | Prefer index `thread_id` over mismatched meta | `test_list_threads_prefers_index_thread_id` | 1 |
| F8 | Missing `plan` → `[]` | `test_list_threads_missing_plan_defaults_empty` | 1 |
| F9 | `init_thread_artifacts` then list includes row | `test_list_threads_after_init` | 1 |
| F10 | `GET /threads` → `[]` | `test_list_threads_empty` (API) | 2 |
| F11 | `GET /threads` returns JSON summaries | `test_list_threads_returns_summaries` | 2 |
| F12 | `GET /threads` lives on real app (not mocked empty only) | `test_list_threads_reads_harness_dir` | 2 |
| F13 | Attach sets id + task + planText only | `test_apply_attach_preserves_run_state` | 4 |
| F14 | Attach blocked while streaming | `test_should_disable_thread_picker` | 4 |
| F15 | Option label truncates long task | `test_format_thread_select_label` | 4 |
| F16 | StatusBar wiring / pick thread | Manual **S1** | 5–6 |
| F17 | Timeline unchanged after attach | Manual **S2** | 5–6 |
| F18 | Picker disabled during streaming | Manual **S3** | 5–6 |
| F19 | List refresh after Start thread settles | Manual **S4** | 5–6 |
| F20 | New thread still mints UUID + clears run | Manual **S5** (existing reset) | 5–6 |

Manual smoke (S1–S5) runs against local API + Vite; checklist is in Task 6.

Frontend has no Vitest runner today. Attach/disable/label logic lives in a **pure** module `app/frontend/src/lib/threadAttach.ts` verified by a small **Node native test** (`node --test`) on a sibling `.test.mjs` that imports the compiled logic via duplicated assertions in plain JS **or** (preferred) a tiny mirrored Python-free approach: put the same pure helpers’ contracts in `app/frontend/src/lib/threadAttach.ts` and add `tests/test_thread_attach_helpers.py` is **not** viable for TS.

**Chosen approach for F13–F15:** extract pure helpers in `threadAttach.ts` and add `app/frontend/src/lib/threadAttach.test.mjs` run with `node --test` (no new npm deps). Keep helpers dependency-free (plain functions).

---

## File map

| File | Responsibility |
|------|----------------|
| `app/services/thread_artifacts.py` | `list_threads()` scan index → meta |
| `app/schemas/threads.py` | `ThreadSummary` Pydantic model |
| `app/api/threads.py` | `GET /threads` router |
| `app/api/__init__.py` | Export `threads_router` |
| `app/core/app.py` | `include_router(threads_router)` |
| `tests/test_thread_artifacts.py` | Unit tests F1–F9 |
| `tests/test_api.py` | API tests F10–F12 |
| `app/frontend/src/lib/threadAttach.ts` | Pure attach/disable/label helpers |
| `app/frontend/src/lib/threadAttach.test.mjs` | Node tests F13–F15 |
| `app/frontend/src/types/api.ts` | `ThreadSummary` type |
| `app/frontend/src/lib/api.ts` | `fetchThreads` |
| `app/frontend/src/hooks/useThreads.ts` | List state + refresh |
| `app/frontend/src/hooks/useConsole.ts` | `attachThread` using helpers |
| `app/frontend/src/components/StatusBar.tsx` + `.css` | Thread picker UI |
| `app/frontend/src/App.tsx` | Wire hooks + refresh on settle |
| `docs/IMPLEMENTATION.md` | Document `GET /threads` |
| `docs/FRONTEND.md` / `docs/DESIGN.md` | StatusBar picker note if stale |
| `docs/exec-plans/tech-debt-tracker.md` | Close / rewrite thread-list debt row |
| `docs/histories/2026-07/…` | History when code lands |

---

### Task 1: `list_threads()` + unit tests (F1–F9)

**Files:**
- Modify: `app/services/thread_artifacts.py`
- Modify: `tests/test_thread_artifacts.py`

- [ ] **Step 1: Write the failing tests (F1–F9)**

Append to `tests/test_thread_artifacts.py`:

```python
def test_list_threads_empty(threads_dir: Path) -> None:
    """F1: Empty root yields an empty list."""
    assert ta.list_threads() == []


def test_list_threads_sorted_by_started_at(threads_dir: Path) -> None:
    """F2+F3: Summaries from index+meta; newest started_at first."""
    older = threads_dir / "older-task"
    newer = threads_dir / "newer-task"
    older.mkdir()
    newer.mkdir()
    (older / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "id-old",
                "task": "older task",
                "slug": "older-task",
                "started_at": "2026-07-13T10:00:00+00:00",
                "plan": ["a"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (newer / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "id-new",
                "task": "newer task",
                "slug": "newer-task",
                "started_at": "2026-07-14T12:00:00+00:00",
                "plan": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (threads_dir / ".index.json").write_text(
        json.dumps({"id-old": "older-task", "id-new": "newer-task"}) + "\n",
        encoding="utf-8",
    )
    rows = ta.list_threads()
    assert [r["thread_id"] for r in rows] == ["id-new", "id-old"]
    assert rows[0]["task"] == "newer task"
    assert rows[0]["slug"] == "newer-task"
    assert rows[1]["plan"] == ["a"]


def test_list_threads_empty_started_at_sorts_last(threads_dir: Path) -> None:
    """F4: Missing started_at sorts after dated rows."""
    dated = threads_dir / "dated"
    undated = threads_dir / "undated"
    dated.mkdir()
    undated.mkdir()
    (dated / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "id-dated",
                "task": "dated",
                "slug": "dated",
                "started_at": "2026-07-14T01:00:00+00:00",
                "plan": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (undated / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "id-undated",
                "task": "undated",
                "slug": "undated",
                "plan": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (threads_dir / ".index.json").write_text(
        json.dumps({"id-dated": "dated", "id-undated": "undated"}) + "\n",
        encoding="utf-8",
    )
    rows = ta.list_threads()
    assert [r["thread_id"] for r in rows] == ["id-dated", "id-undated"]


def test_list_threads_skips_corrupt_meta(threads_dir: Path) -> None:
    """F5: Corrupt meta for one index entry is skipped."""
    good = threads_dir / "good"
    bad = threads_dir / "bad"
    good.mkdir()
    bad.mkdir()
    (good / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "id-good",
                "task": "ok",
                "slug": "good",
                "started_at": "2026-07-14T01:00:00+00:00",
                "plan": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (bad / "meta.json").write_text("{not-json", encoding="utf-8")
    (threads_dir / ".index.json").write_text(
        json.dumps({"id-good": "good", "id-bad": "bad"}) + "\n",
        encoding="utf-8",
    )
    rows = ta.list_threads()
    assert len(rows) == 1
    assert rows[0]["thread_id"] == "id-good"


def test_list_threads_skips_missing_dir(threads_dir: Path) -> None:
    """F6: Index slug with no directory is skipped."""
    (threads_dir / ".index.json").write_text(
        json.dumps({"id-ghost": "no-such-dir"}) + "\n",
        encoding="utf-8",
    )
    assert ta.list_threads() == []


def test_list_threads_prefers_index_thread_id(threads_dir: Path) -> None:
    """F7: Index key wins when meta.thread_id disagrees."""
    path = threads_dir / "slug-a"
    path.mkdir()
    (path / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "meta-says-other",
                "task": "t",
                "slug": "slug-a",
                "started_at": "2026-07-14T02:00:00+00:00",
                "plan": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (threads_dir / ".index.json").write_text(
        json.dumps({"index-id": "slug-a"}) + "\n",
        encoding="utf-8",
    )
    rows = ta.list_threads()
    assert len(rows) == 1
    assert rows[0]["thread_id"] == "index-id"


def test_list_threads_missing_plan_defaults_empty(threads_dir: Path) -> None:
    """F8: meta without plan yields plan=[]."""
    path = threads_dir / "no-plan"
    path.mkdir()
    (path / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "id-np",
                "task": "t",
                "slug": "no-plan",
                "started_at": "2026-07-14T03:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (threads_dir / ".index.json").write_text(
        json.dumps({"id-np": "no-plan"}) + "\n",
        encoding="utf-8",
    )
    assert ta.list_threads()[0]["plan"] == []


def test_list_threads_after_init(threads_dir: Path) -> None:
    """F9: init_thread_artifacts row is listed."""
    ta.init_thread_artifacts(
        task="From init",
        thread_id="init-thread-1",
        plan=["one", "two"],
    )
    rows = ta.list_threads()
    assert len(rows) == 1
    assert rows[0]["thread_id"] == "init-thread-1"
    assert rows[0]["task"] == "From init"
    assert rows[0]["plan"] == ["one", "two"]
    assert rows[0]["started_at"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_thread_artifacts.py -k list_threads -v
```

Expected: FAIL with `AttributeError: ... list_threads` (or similar).

- [ ] **Step 3: Implement `list_threads`**

Add near other helpers in `app/services/thread_artifacts.py` (after `lookup_thread_dir` is fine):

```python
from typing import TypedDict


class ThreadSummaryDict(TypedDict):
    """On-disk thread list row (API maps to Pydantic ThreadSummary)."""

    thread_id: str
    task: str
    slug: str
    started_at: str
    plan: list[str]


def list_threads(*, root: Path | None = None) -> list[ThreadSummaryDict]:
    """List thread artifact summaries from .index.json + meta.json.

    Newest ``started_at`` first. Corrupt or missing meta entries are skipped.
    """
    base = root or threads_root()
    index = _read_index(base)
    rows: list[ThreadSummaryDict] = []
    for thread_id, slug in index.items():
        path = base / slug
        meta_path = path / "meta.json"
        if not path.is_dir() or not meta_path.is_file():
            logger.warning("thread index skip missing dir/meta: %s -> %s", thread_id, slug)
            continue
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("thread index skip bad meta %s: %s", meta_path, exc)
            continue
        if not isinstance(raw, dict):
            logger.warning("thread index skip non-object meta %s", meta_path)
            continue
        plan_raw = raw.get("plan") or []
        plan = [str(p) for p in plan_raw] if isinstance(plan_raw, list) else []
        rows.append(
            ThreadSummaryDict(
                thread_id=str(thread_id),
                task=str(raw.get("task") or ""),
                slug=str(raw.get("slug") or slug),
                started_at=str(raw.get("started_at") or ""),
                plan=plan,
            )
        )

    # ISO timestamps sort lexicographically; empty started_at sorts last.
    rows.sort(key=lambda r: r["started_at"] or "", reverse=True)
    return rows
```

Prefer index key for `thread_id` (already using `thread_id` from the loop). Ensure `TypedDict` is imported from `typing` alongside existing imports (merge with the file’s current `from typing import Any`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_thread_artifacts.py -k list_threads -v`

Expected: 8 passed (F1–F9).

- [ ] **Step 5: Commit**

```bash
git add app/services/thread_artifacts.py tests/test_thread_artifacts.py
git commit -m "$(cat <<'EOF'
feat: list thread artifact summaries from app/threads index

EOF
)"
```

---

### Task 2: `GET /threads` API (F10–F12)

**Files:**
- Create: `app/schemas/threads.py`
- Create: `app/api/threads.py`
- Modify: `app/api/__init__.py`
- Modify: `app/core/app.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing API tests**

Append to `tests/test_api.py`:

```python
def test_list_threads_empty(client: TestClient) -> None:
    """F10: GET /threads returns [] when the artifact store is empty."""
    with patch(
        "app.api.threads.list_threads",
        return_value=[],
    ):
        response = client.get("/threads")
    assert response.status_code == 200
    assert response.json() == []


def test_list_threads_returns_summaries(client: TestClient) -> None:
    """F11: GET /threads maps summary rows to JSON."""
    rows = [
        {
            "thread_id": "abc",
            "task": "do the thing",
            "slug": "do-the-thing",
            "started_at": "2026-07-14T08:00:00+00:00",
            "plan": ["step"],
        }
    ]
    with patch("app.api.threads.list_threads", return_value=rows):
        response = client.get("/threads")
    assert response.status_code == 200
    assert response.json() == rows


def test_list_threads_reads_harness_dir(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F12: GET /threads reads real HARNESS_THREADS_DIR (unmocked list)."""
    root = tmp_path / "threads"
    root.mkdir()
    slug = root / "live-task"
    slug.mkdir()
    (slug / "meta.json").write_text(
        json.dumps(
            {
                "thread_id": "live-id",
                "task": "live task",
                "slug": "live-task",
                "started_at": "2026-07-14T09:00:00+00:00",
                "plan": ["p1"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".index.json").write_text(
        json.dumps({"live-id": "live-task"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(root))
    response = client.get("/threads")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["thread_id"] == "live-id"
    assert body[0]["task"] == "live task"
    assert body[0]["plan"] == ["p1"]
```

Add `from pathlib import Path`, `import json`, and `import pytest` at top of `test_api.py` if missing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -k list_threads -v`

Expected: FAIL (route missing / 404).

- [ ] **Step 3: Add schema + router + mount**

Create `app/schemas/threads.py`:

```python
"""Schemas for thread artifact list endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ThreadSummary(BaseModel):
    """Summary row for GET /threads."""

    thread_id: str
    task: str
    slug: str
    started_at: str = ""
    plan: list[str] = Field(default_factory=list)
```

Create `app/api/threads.py`:

```python
"""Thread artifact library routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.threads import ThreadSummary
from app.services.thread_artifacts import list_threads

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=list[ThreadSummary])
async def list_thread_artifacts() -> list[ThreadSummary]:
    """List on-disk thread artifacts under app/threads/ for console attach."""
    return [ThreadSummary(**row) for row in list_threads()]
```

Update `app/api/__init__.py` to export `threads_router`. Update `app/core/app.py` to `include_router(threads_router)`.

- [ ] **Step 4: Run API tests**

Run: `pytest tests/test_api.py -k list_threads -v`

Expected: 3 passed (F10–F12).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/threads.py app/api/threads.py app/api/__init__.py app/core/app.py tests/test_api.py
git commit -m "$(cat <<'EOF'
feat: add GET /threads for artifact library listing

EOF
)"
```

---

### Task 3: Frontend API types + `fetchThreads` + `useThreads`

**Files:**
- Modify: `app/frontend/src/types/api.ts`
- Modify: `app/frontend/src/lib/api.ts`
- Create: `app/frontend/src/hooks/useThreads.ts`

- [ ] **Step 1: Add `ThreadSummary` type** in `types/api.ts`
- [ ] **Step 2: Add `fetchThreads`** in `lib/api.ts` (`GET /api/threads`)
- [ ] **Step 3: Create `useThreads`** (mount fetch + `refreshThreads`)
- [ ] **Step 4: `cd app/frontend && npx tsc --noEmit`**
- [ ] **Step 5: Commit** frontend fetch + hook

---

### Task 4: Attach helpers + Node tests (F13–F15) + `attachThread`

**Files:**
- Create: `app/frontend/src/lib/threadAttach.mjs`
- Create: `app/frontend/src/lib/threadAttach.mjs.d.ts`
- Create: `app/frontend/src/lib/threadAttach.ts`
- Create: `app/frontend/src/lib/threadAttach.test.mjs`
- Modify: `app/frontend/src/hooks/useConsole.ts`
- Modify: `app/frontend/package.json` (`"test:attach": "node --test src/lib/threadAttach.test.mjs"`)

- [ ] **Step 1: Write failing Node tests**

`threadAttach.test.mjs` covers:

- **F14** `shouldDisableThreadPicker('streaming') === true`, idle false, busy true
- **F15** `formatThreadSelectLabel` truncates task > 36 chars
- **F13** `applyAttachFields` returns `{ threadId, task, planText }` only; `ATTACH_PRESERVED_KEYS` lists timeline/phase/runResponse/selectedStepId/distillResult

- [ ] **Step 2: Run** `cd app/frontend && node --test src/lib/threadAttach.test.mjs` — expect FAIL (missing module)

- [ ] **Step 3: Implement `threadAttach.mjs` + typed TS re-export; wire `attachThread` via helpers**

```javascript
export function shouldDisableThreadPicker(phase, busy = false) {
  return busy || phase === 'streaming'
}

export function formatThreadSelectLabel(thread, maxLen = 36) {
  const task = (thread.task || '').trim()
  const short = String(thread.thread_id || '').slice(0, 8)
  if (!task) return `${short}…`
  const truncated = task.length > maxLen ? `${task.slice(0, maxLen)}…` : task
  return `${truncated} (${short}…)`
}

export function applyAttachFields(thread) {
  return {
    threadId: thread.thread_id,
    task: thread.task || '',
    planText: Array.isArray(thread.plan) ? thread.plan.join('\n') : '',
  }
}

export const ATTACH_PRESERVED_KEYS = [
  'timeline',
  'phase',
  'runResponse',
  'selectedStepId',
  'distillResult',
]
```

`useConsole.attachThread` must call `shouldDisableThreadPicker` then `applyAttachFields`; must **not** clear timeline/phase/runResponse.

- [ ] **Step 4: Run** `cd app/frontend && npm run test:attach` — Expected: 3 passed

- [ ] **Step 5: Commit** helpers + tests + `attachThread`

---

### Task 5: StatusBar picker + App wiring (manual F16–F20 in Task 6)

**Files:**
- Modify: `app/frontend/src/components/StatusBar.tsx` + `.css`
- Modify: `app/frontend/src/App.tsx`

- [ ] **Step 1: StatusBar `<select>`** using `formatThreadSelectLabel` / `shouldDisableThreadPicker`; synthetic current option; refresh button; error in `title`
- [ ] **Step 2: Wire `useThreads` + `attachThread`; refresh when `phase` is `complete` or `awaiting_human`**
- [ ] **Step 3: `cd app/frontend && npm run test:attach && npm run build`**
- [ ] **Step 4: Commit** StatusBar + App

---

### Task 6: Docs, history, graphify + full gate

- [ ] **Step 1–4:** `IMPLEMENTATION.md`, `FRONTEND.md`/`DESIGN.md`, tech-debt row, history entry
- [ ] **Step 5:** `graphify update .`
- [ ] **Step 6: Automated gate (F1–F15)**

```bash
pytest tests/test_thread_artifacts.py -k list_threads -v
pytest tests/test_api.py -k list_threads -v
cd app/frontend && npm run test:attach && npm run build
```

- [ ] **Step 7: Manual smoke (F16–F20)**

| ID | Check |
|----|--------|
| S1/F16 | StatusBar lists threads from `app/threads/` |
| S2/F17 | Select → Task+Plan fill; timeline/phase unchanged |
| S3/F18 | During Start thread, select disabled |
| S4/F19 | After settle (or ↻), new thread appears |
| S5/F20 | New thread mints UUID + clears run state |

- [ ] **Step 8: Commit docs**

---

## Spec coverage checklist

| Spec requirement | Feature IDs | Task |
|------------------|-------------|------|
| `GET /threads` from index+meta | F1–F12 | 1–2 |
| Sort / skip corrupt / missing | F3–F6 | 1 |
| Attach-only id+task+plan | F13 | 4 |
| Disable while streaming | F14, S3 | 4–6 |
| StatusBar picker | F16, S1 | 5–6 |
| Timeline unchanged | F17, S2 | 6 |
| Refresh on mount / settle | F19, S4 | 5–6 |
| New thread unchanged | F20, S5 | 6 |
| Docs + tech debt | — | 6 |

## Done criteria

Do not mark this plan complete until:

1. F1–F15 automated tests are green
2. S1–S5 manual checks recorded in the history entry
3. Docs + tech-debt row updated

Commit steps remain optional if the user asks to batch commits.
