# Thread Run Artifacts + `app/skills` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Start thread, create `app/threads/<task-slug>/` with four stage markdown files updated through the run, and store distilled skills under `app/skills/` by default.

**Architecture:** A small `app/services/thread_artifacts.py` helper (init + node/snapshot writes, `.index.json` resume lookup) is called from `run_harness` / `stream_harness` / `resume_harness`. Skill library default root changes in `skills.store.skills_root()` to `app/skills` (mkdir on write). Disk failures never fail the graph.

**Tech Stack:** Python pathlib/json, FastAPI harness services, existing `skills.store.slugify`, pytest with tmp dirs / env overrides.

**Spec:** [`docs/superpowers/specs/2026-07-13-thread-run-artifacts-design.md`](../specs/2026-07-13-thread-run-artifacts-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `skills/store.py` | Default `skills_root()` → `app/skills` |
| `app/skills/.gitkeep` | Keep empty tracked skills library |
| `app/services/thread_artifacts.py` | Thread folder init, stage `.md` writes, index |
| `app/services/harness.py` | Call artifact helpers on run/stream/resume |
| `.gitignore` | Ignore `app/threads/` |
| `tests/test_thread_artifacts.py` | Unit tests for artifacts helper |
| `tests/test_skills_store_root.py` | Default skills root path (or extend distill tests) |
| `docs/IMPLEMENTATION.md` | Threads + skills path + `HARNESS_*_DIR` |
| `docs/ARCHITECTURE.md` | Skills path row |
| `docs/SECURITY.md` | Skills path row |
| `app/api/skills.py` | Docstring path update |
| `docs/histories/2026-07/…` | History entry |

---

### Task 1: Default distilled skills to `app/skills`

**Files:**
- Modify: `skills/store.py`
- Create: `app/skills/.gitkeep`
- Test: `tests/test_skills_store_root.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_skills_store_root.py
from __future__ import annotations

import os
from pathlib import Path

from skills.store import skills_root, write_skill


def test_skills_root_defaults_under_app_skills() -> None:
    """Default root is <repo>/app/skills when HARNESS_SKILLS_DIR is unset."""
    os.environ.pop("HARNESS_SKILLS_DIR", None)
    root = skills_root()
    assert root.name == "skills"
    assert root.parent.name == "app"
    assert root.is_absolute()


def test_write_skill_creates_app_skills_dir(tmp_path: Path, monkeypatch) -> None:
    """write_skill creates the skills directory if missing."""
    missing = tmp_path / "skills-lib"
    assert not missing.exists()
    monkeypatch.setenv("HARNESS_SKILLS_DIR", str(missing))
    write_skill(
        "demo",
        name="demo",
        description="d",
        body="body",
        thread_id="t1",
        task="task",
        rounds=1,
        root=missing,
    )
    assert (missing / "demo" / "SKILL.md").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skills_store_root.py::test_skills_root_defaults_under_app_skills -v`

Expected: FAIL (root still `.cursor/skills`)

- [ ] **Step 3: Minimal implementation**

In `skills/store.py`, change `skills_root()`:

```python
def skills_root() -> Path:
    """Return the directory where distilled skills are written."""
    override = os.getenv("HARNESS_SKILLS_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT / "app" / "skills"
```

Create empty `app/skills/.gitkeep`.

Do **not** add `app/skills/__init__.py` (data dir only, not a package).

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_skills_store_root.py tests/test_skills_distill.py -q`

Expected: PASS

- [ ] **Step 5: Commit** (if user requested commits)

```bash
git add skills/store.py app/skills/.gitkeep tests/test_skills_store_root.py
git commit -m "$(cat <<'EOF'
fix skills library default root to app/skills.

EOF
)"
```

---

### Task 2: Thread artifacts helper — init + index

**Files:**
- Create: `app/services/thread_artifacts.py`
- Create: `tests/test_thread_artifacts.py`

- [ ] **Step 1: Write failing tests for init**

```python
# tests/test_thread_artifacts.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import thread_artifacts as ta

STAGE_FILES = ("planner.md", "executor.md", "learner.md", "actioner.md")


@pytest.fixture()
def threads_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "threads"
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(root))
    return root


def test_init_creates_meta_and_four_stage_files(threads_dir: Path) -> None:
    path = ta.init_thread_artifacts(
        task="Summarize API docs",
        thread_id="thread-aaaabbbb-cccc",
        plan=["read docs", "summarize"],
    )
    assert path.parent == threads_dir.resolve()
    assert (path / "meta.json").is_file()
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["thread_id"] == "thread-aaaabbbb-cccc"
    assert meta["task"] == "Summarize API docs"
    for name in STAGE_FILES:
        text = (path / name).read_text(encoding="utf-8")
        assert "status: pending" in text
    index = json.loads((threads_dir / ".index.json").read_text(encoding="utf-8"))
    assert index["thread-aaaabbbb-cccc"] == path.name


def test_collision_appends_thread_id_prefix(threads_dir: Path) -> None:
    first = ta.init_thread_artifacts(
        task="Same Task",
        thread_id="11111111-aaaa",
        plan=[],
    )
    second = ta.init_thread_artifacts(
        task="Same Task",
        thread_id="22222222-bbbb",
        plan=[],
    )
    assert first != second
    assert second.name.endswith("22222222")
```

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/test_thread_artifacts.py::test_init_creates_meta_and_four_stage_files tests/test_thread_artifacts.py::test_collision_appends_thread_id_prefix -v`

Expected: FAIL (module missing)

- [ ] **Step 3: Implement init + index**

Create `app/services/thread_artifacts.py`:

```python
"""On-disk per-thread stage notes under app/threads/."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skills.store import slugify

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STAGE_NODES = ("planner", "executor", "learner", "actioner")
_INDEX_NAME = ".index.json"


def threads_root() -> Path:
    """Return the directory where thread artifact folders live."""
    override = os.getenv("HARNESS_THREADS_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT / "app" / "threads"


def _index_path(root: Path | None = None) -> Path:
    return (root or threads_root()) / _INDEX_NAME


def _read_index(root: Path | None = None) -> dict[str, str]:
    path = _index_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("failed to read thread index %s: %s", path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _write_index(index: dict[str, str], root: Path | None = None) -> None:
    base = root or threads_root()
    base.mkdir(parents=True, exist_ok=True)
    _index_path(base).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pending_stage_markdown(node: str) -> str:
    now = datetime.now(UTC).isoformat()
    return (
        f"# {node}\n\n"
        f"- status: pending\n"
        f"- round: 0\n"
        f"- updated_at: {now}\n\n"
        f"## Contents\n\n_(none yet)_\n"
    )


def resolve_thread_dir(task: str, thread_id: str, *, root: Path | None = None) -> Path:
    """Choose a non-colliding directory for a new thread."""
    base = root or threads_root()
    base.mkdir(parents=True, exist_ok=True)
    slug = slugify(task)
    candidate = base / slug
    if not candidate.exists():
        return candidate
    short = thread_id.replace("-", "")[:8]
    return base / f"{slug}-{short}"


def init_thread_artifacts(
    task: str,
    thread_id: str,
    plan: list[str] | None = None,
    *,
    root: Path | None = None,
) -> Path:
    """Create thread folder, meta, pending stage files, and index entry."""
    base = root or threads_root()
    path = resolve_thread_dir(task, thread_id, root=base)
    path.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    meta = {
        "thread_id": thread_id,
        "task": task,
        "slug": path.name,
        "started_at": now,
        "dir": str(path),
        "plan": list(plan or []),
    }
    (path / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )
    for node in _STAGE_NODES:
        (path / f"{node}.md").write_text(
            _pending_stage_markdown(node),
            encoding="utf-8",
        )
    index = _read_index(base)
    index[thread_id] = path.name
    _write_index(index, base)
    return path


def lookup_thread_dir(thread_id: str, *, root: Path | None = None) -> Path | None:
    """Resolve an existing thread folder from .index.json."""
    base = root or threads_root()
    slug = _read_index(base).get(thread_id)
    if not slug:
        return None
    path = base / slug
    return path if path.is_dir() else None
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_thread_artifacts.py::test_init_creates_meta_and_four_stage_files tests/test_thread_artifacts.py::test_collision_appends_thread_id_prefix -v`

Expected: PASS

- [ ] **Step 5: Commit** (if requested)

```bash
git add app/services/thread_artifacts.py tests/test_thread_artifacts.py
git commit -m "$(cat <<'EOF'
Add thread artifact folder init under app/threads.

EOF
)"
```

---

### Task 3: Stage markdown record + snapshot refresh

**Files:**
- Modify: `app/services/thread_artifacts.py`
- Modify: `tests/test_thread_artifacts.py`

- [ ] **Step 1: Write failing tests for node updates**

```python
def test_record_node_update_writes_planner_contents(threads_dir: Path) -> None:
    path = ta.init_thread_artifacts(
        task="Plan work",
        thread_id="t-plan",
        plan=[],
    )
    ta.record_node_update(
        path,
        node="planner",
        round_num=1,
        payload={"plan": ["a", "b"], "memory_context": "prior note"},
        status="complete",
    )
    text = (path / "planner.md").read_text(encoding="utf-8")
    assert "status: complete" in text
    assert "round: 1" in text
    assert "## Round 1" in text
    assert "a" in text
    assert "prior note" in text


def test_record_node_update_ignores_unknown_node(threads_dir: Path) -> None:
    path = ta.init_thread_artifacts(task="x", thread_id="t-x", plan=[])
    ta.record_node_update(
        path,
        node="unknown",
        round_num=1,
        payload={},
        status="complete",
    )
    # four stage files unchanged as pending
    assert "status: pending" in (path / "planner.md").read_text(encoding="utf-8")


def test_refresh_from_snapshot_updates_all_stages(threads_dir: Path) -> None:
    path = ta.init_thread_artifacts(task="full", thread_id="t-full", plan=[])
    ta.refresh_from_snapshot(
        path,
        {
            "rounds": 1,
            "plan": ["one"],
            "result": "done",
            "learning": {"verdict": "pass", "reason": "ok"},
            "learning_candidates": [],
            "approved": True,
            "refine_from": "finish",
            "loop_score": 0.9,
            "skill_preview_ready": True,
        },
        status_hints={"planner": "complete", "executor": "complete",
                      "learner": "complete", "actioner": "complete"},
    )
    assert "one" in (path / "planner.md").read_text(encoding="utf-8")
    assert "done" in (path / "executor.md").read_text(encoding="utf-8")
    assert "pass" in (path / "learner.md").read_text(encoding="utf-8")
    assert "0.9" in (path / "actioner.md").read_text(encoding="utf-8")


def test_disk_errors_do_not_raise(threads_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = ta.init_thread_artifacts(task="err", thread_id="t-err", plan=[])

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)
    ta.record_node_update(
        path,
        node="planner",
        round_num=1,
        payload={"plan": ["x"]},
        status="complete",
    )
```

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/test_thread_artifacts.py -k "record_node or refresh_from or disk_errors" -v`

Expected: FAIL (functions missing)

- [ ] **Step 3: Implement record + refresh**

Append to `thread_artifacts.py`:

```python
def _format_value(value: Any) -> str:
    if value is None:
        return "_(none)_"
    if isinstance(value, str):
        return value if value.strip() else "_(empty)_"
    return json.dumps(value, indent=2, default=str)


def _stage_payload(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    if node == "planner":
        keys = ("plan", "memory_context")
    elif node == "executor":
        keys = ("result", "execution", "tool_calls")
    elif node == "learner":
        keys = (
            "learning",
            "learning_candidates",
            "suggested_step",
            "approved",
        )
    else:  # actioner
        keys = (
            "loop_score",
            "skill_preview_ready",
            "refine_from",
            "pending_memories",
            "approved_memories",
            "memory_cursor",
        )
    return {k: payload.get(k) for k in keys if k in payload or payload.get(k) is not None}


def _render_stage_file(
    node: str,
    *,
    status: str,
    round_num: int,
    sections: list[tuple[int, dict[str, Any]]],
) -> str:
    now = datetime.now(UTC).isoformat()
    lines = [
        f"# {node}",
        "",
        f"- status: {status}",
        f"- round: {round_num}",
        f"- updated_at: {now}",
        "",
    ]
    for r, body in sections:
        lines.append(f"## Round {r}")
        lines.append("")
        lines.append("### Contents")
        lines.append("")
        if not body:
            lines.append("_(none)_")
            lines.append("")
            continue
        for key, value in body.items():
            lines.append(f"- {key}:")
            rendered = _format_value(value)
            for sub in rendered.splitlines() or ["_(none)_"]:
                lines.append(f"  {sub}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _safe_write(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.warning("failed to write thread artifact %s: %s", path, exc)


def _parse_existing_rounds(text: str) -> list[tuple[int, dict[str, Any]]]:
    """Best-effort: keep prior round blocks as opaque single content blobs.

    For simplicity, on rewrite of the same round we replace; for a new round we
    append. Prior rounds are preserved by re-reading ## Round N headers and
    storing raw markdown under key '_raw' when full structured parse is hard.
    """
    # Minimal approach used by implementation: callers pass full section list.
    # See record_node_update for merge logic.
    _ = text
    return []


def record_node_update(
    thread_dir: Path,
    *,
    node: str,
    round_num: int,
    payload: dict[str, Any],
    status: str,
) -> None:
    """Write or update one stage markdown file for a node visit."""
    if node not in _STAGE_NODES:
        return
    path = thread_dir / f"{node}.md"
    body = _stage_payload(node, payload)
    sections: list[tuple[int, dict[str, Any]]] = []
    if path.is_file():
        # Preserve earlier rounds by extracting ## Round N ... blocks as _raw.
        existing = path.read_text(encoding="utf-8")
        import re

        for match in re.finditer(
            r"## Round (\d+)\n\n(.*?)(?=\n## Round |\Z)",
            existing,
            flags=re.S,
        ):
            r = int(match.group(1))
            if r == round_num:
                continue
            sections.append((r, {"_raw": match.group(2).strip()}))
    sections.append((round_num, body))
    sections.sort(key=lambda item: item[0])
    content = _render_stage_file(
        node,
        status=status,
        round_num=round_num,
        sections=sections,
    )
    # Prefer structured contents for the active round; raw kept for older ones.
    # Re-render active round without _raw if present.
    _safe_write(path, content)


def refresh_from_snapshot(
    thread_dir: Path,
    values: dict[str, Any],
    *,
    status_hints: dict[str, str] | None = None,
) -> None:
    """Refresh all four stage files from checkpoint/snapshot values."""
    hints = status_hints or {}
    round_num = int(values.get("rounds") or 1)
    payloads = {
        "planner": values,
        "executor": values,
        "learner": values,
        "actioner": values,
    }
    for node in _STAGE_NODES:
        record_node_update(
            thread_dir,
            node=node,
            round_num=max(round_num, 1),
            payload=payloads[node],
            status=hints.get(node, "complete"),
        )


def safe_init_thread_artifacts(
    task: str,
    thread_id: str,
    plan: list[str] | None = None,
) -> Path | None:
    """init_thread_artifacts that never raises."""
    try:
        return init_thread_artifacts(task, thread_id, plan)
    except OSError as exc:
        logger.warning("failed to init thread artifacts: %s", exc)
        return None
```

When implementing, ensure `_render_stage_file` pretty-prints `_raw` blocks as-is (no extra JSON quotes) so older rounds stay readable.

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_thread_artifacts.py -q`

Expected: PASS

- [ ] **Step 5: Commit** (if requested)

```bash
git add app/services/thread_artifacts.py tests/test_thread_artifacts.py
git commit -m "$(cat <<'EOF'
Record planner/executor/learner/actioner stage markdown per thread.

EOF
)"
```

---

### Task 4: Wire harness run / stream / resume

**Files:**
- Modify: `app/services/harness.py`
- Modify: `tests/test_api.py` or create `tests/test_harness_thread_artifacts.py`

- [ ] **Step 1: Write failing integration-style unit test**

```python
# tests/test_harness_thread_artifacts.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request

from app.schemas.run import RunRequest
from app.services.harness import run_harness, stream_harness


@pytest.mark.asyncio
async def test_run_harness_inits_thread_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path / "threads"))
    app = FastAPI()
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={})
    request = MagicMock(spec=Request)
    request.app = app

    async def fake_invoke(*_a, **_k):
        return None

    with (
        patch("app.services.harness.graph_for_request", return_value=graph),
        patch("app.services.harness.invoke_with_timeout", side_effect=fake_invoke),
        patch(
            "app.services.harness.snapshot_to_response",
            new=AsyncMock(
                return_value=MagicMock(
                    model_dump=lambda: {
                        "thread_id": "t1",
                        "plan": ["p"],
                        "rounds": 1,
                    }
                )
            ),
        ),
    ):
        # snapshot_to_response must return a RunResponse-like object;
        # prefer constructing a real RunResponse in the real test file.
        from app.schemas.run import RunResponse

        with patch(
            "app.services.harness.snapshot_to_response",
            new=AsyncMock(
                return_value=RunResponse(
                    thread_id="t1",
                    status="complete",
                    approved=True,
                    needs_human=False,
                    rounds=1,
                    max_rounds=3,
                    plan=["p"],
                )
            ),
        ):
            body = RunRequest(thread_id="t1", task="Wire harness artifacts")
            await run_harness(request, body)

    assert any((tmp_path / "threads").glob("*/planner.md"))
```

Adjust mocks to match current `invoke_with_timeout` / `graph_for_request` signatures used in `harness.py`.

- [ ] **Step 2: Run test — expect fail** (no folder created)

Run: `pytest tests/test_harness_thread_artifacts.py -v`

Expected: FAIL / assertion no planner.md

- [ ] **Step 3: Wire `harness.py`**

```python
from app.services.thread_artifacts import (
    lookup_thread_dir,
    record_node_update,
    refresh_from_snapshot,
    safe_init_thread_artifacts,
)

# In run_harness, before invoke:
thread_dir = safe_init_thread_artifacts(
    body.task,
    body.thread_id,
    body.plan,
)
# After snapshot_to_response:
if thread_dir is not None:
    try:
        refresh_from_snapshot(
            thread_dir,
            {
                "rounds": response.rounds,
                "plan": response.plan,
                "result": response.result,
                "learning": response.learning,
                "learning_candidates": response.learning_candidates,
                "approved": response.approved,
                "refine_from": response.refine_from,
                "loop_score": response.loop_score,
                "skill_preview_ready": response.skill_preview_ready,
                "execution": response.execution,
                "tool_calls": response.tool_calls,
            },
            status_hints={
                n: ("paused" if response.needs_human and response.next_action == n
                    else "complete")
                for n in ("planner", "executor", "learner", "actioner")
            },
        )
    except OSError:
        pass  # refresh_from_snapshot already logs; belt-and-suspenders

# In stream_harness:
thread_dir = safe_init_thread_artifacts(body.task, body.thread_id, body.plan)
# Inside astream loop, after each chunk:
# chunk is typically { "planner": { ...patch... } }
if thread_dir is not None and isinstance(chunk, dict):
    for node, patch in chunk.items():
        if node in ("planner", "executor", "learner", "actioner") and isinstance(patch, dict):
            rounds = int(patch.get("rounds") or 1)
            record_node_update(
                thread_dir,
                node=node,
                round_num=max(rounds, 1),
                payload=patch,
                status="complete",
            )
# After final snapshot:
# refresh_from_snapshot(...) same as run_harness

# In resume_harness, after success:
thread_dir = lookup_thread_dir(body.thread_id)
if thread_dir is not None:
    refresh_from_snapshot(thread_dir, values_from_response_or_state, ...)
```

Wrap each artifact call in `try/except OSError` or use only the `safe_*` helpers so stream errors for disk never become SSE `error` events.

For HITL pause detection on stream chunks: if you have interrupt info only on final snapshot, set `paused` in the final `refresh_from_snapshot` status hints (acceptable per spec).

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_harness_thread_artifacts.py tests/test_api.py tests/test_thread_artifacts.py -q`

Expected: PASS

- [ ] **Step 5: Commit** (if requested)

```bash
git add app/services/harness.py tests/test_harness_thread_artifacts.py
git commit -m "$(cat <<'EOF'
Wire thread stage artifacts into run, stream, and resume.

EOF
)"
```

---

### Task 5: Gitignore + docs + history

**Files:**
- Modify: `.gitignore`
- Modify: `docs/IMPLEMENTATION.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/SECURITY.md`
- Modify: `app/api/skills.py` (docstring)
- Create: `docs/histories/2026-07/YYYYMMDD-HHmm-thread-run-artifacts.md`

- [ ] **Step 1: Gitignore**

Add:

```gitignore
app/threads/
```

- [ ] **Step 2: Docs**

In `IMPLEMENTATION.md`:

- Skills write path: `.cursor/skills/<slug>/SKILL.md` → `app/skills/<slug>/SKILL.md`
- New subsection **Thread run artifacts**:
  - `app/threads/<task-slug>/{meta.json,planner.md,executor.md,learner.md,actioner.md}`
  - env `HARNESS_THREADS_DIR` override
  - gitignored

In `ARCHITECTURE.md` distilled skills row → `app/skills/<slug>/SKILL.md`.

In `SECURITY.md` distilled skills path → `app/skills/`.

In `app/api/skills.py` save docstring → `app/skills/`.

- [ ] **Step 3: History entry** per `docs/HISTORY_GUIDE.md`

- [ ] **Step 4: Verification**

Run:

```bash
pytest tests/test_thread_artifacts.py tests/test_skills_store_root.py tests/test_skills_distill.py tests/test_harness_thread_artifacts.py tests/test_api.py -q
graphify update .
```

Expected: PASS; graph updated.

- [ ] **Step 5: Commit** (if requested)

```bash
git add .gitignore docs/IMPLEMENTATION.md docs/ARCHITECTURE.md docs/SECURITY.md app/api/skills.py docs/histories/2026-07/
git commit -m "$(cat <<'EOF'
Document app/threads artifacts and app/skills library path.

EOF
)"
```

---

## Spec coverage checklist

| Spec requirement | Task |
| --- | --- |
| `app/threads/<slug>/` on start | 2, 4 |
| Four stage `.md` + status/contents | 3, 4 |
| Update on stream / final / resume | 4 |
| Gitignore threads | 5 |
| `.index.json` resume lookup | 2, 4 |
| Collision suffix | 2 |
| Never fail run on disk errors | 3, 4 |
| Skills default `app/skills/` + mkdir | 1 |
| Docs / history | 5 |
| No migrate of old `.cursor/skills` playbooks | explicit non-goal |

## Plan self-review

- No TBD placeholders in steps.
- `skills_root` / `threads_root` / `record_node_update` / `refresh_from_snapshot` names consistent across tasks.
- Resume without index entry skips quietly (Task 4).
- Do not add `app/skills/__init__.py`.
