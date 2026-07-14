"""On-disk per-thread stage notes under app/threads/."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

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


def resolve_thread_dir(
    task: str,
    thread_id: str,
    *,
    root: Path | None = None,
) -> Path:
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
    Index key is preferred for ``thread_id`` when meta disagrees.
    """
    base = root or threads_root()
    index = _read_index(base)
    rows: list[ThreadSummaryDict] = []
    for thread_id, slug in index.items():
        path = base / slug
        meta_path = path / "meta.json"
        if not path.is_dir() or not meta_path.is_file():
            logger.warning(
                "thread index skip missing dir/meta: %s -> %s",
                thread_id,
                slug,
            )
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
        plan = (
            [str(p) for p in plan_raw] if isinstance(plan_raw, list) else []
        )
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


def _format_value(value: Any) -> str:
    if value is None:
        return "_(none)_"
    if isinstance(value, str):
        return value if value.strip() else "_(empty)_"
    return json.dumps(value, indent=2, default=str)


def _stage_keys(node: str) -> tuple[str, ...]:
    if node == "planner":
        return ("plan", "memory_context")
    if node == "executor":
        return ("result", "execution", "tool_calls")
    if node == "learner":
        return (
            "learning",
            "learning_candidates",
            "suggested_step",
            "approved",
            "learner_tool_calls",
            "script_runs",
        )
    return (
        "loop_score",
        "skill_preview_ready",
        "refine_from",
        "pending_memories",
        "approved_memories",
        "memory_cursor",
    )


def _stage_payload(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    keys = _stage_keys(node)
    out: dict[str, Any] = {}
    for key in keys:
        if key in payload:
            out[key] = payload[key]
    return out


def _extract_round_sections(text: str) -> list[tuple[int, str]]:
    """Parse existing ``## Round N`` blocks as (round, raw body) pairs."""
    sections: list[tuple[int, str]] = []
    for match in re.finditer(
        r"## Round (\d+)\n\n(.*?)(?=\n## Round |\Z)",
        text,
        flags=re.S,
    ):
        sections.append((int(match.group(1)), match.group(2).strip()))
    return sections


def _render_round_body(body: dict[str, Any]) -> str:
    if "_raw" in body and len(body) == 1:
        return str(body["_raw"]).rstrip() + "\n"
    if not body:
        return "### Contents\n\n_(none)_\n"
    lines = ["### Contents", ""]
    for key, value in body.items():
        if key == "_raw":
            lines.append(str(value))
            continue
        lines.append(f"- {key}:")
        rendered = _format_value(value)
        for sub in rendered.splitlines() or ["_(none)_"]:
            lines.append(f"  {sub}")
    return "\n".join(lines).rstrip() + "\n"


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
        lines.append(_render_round_body(body).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _safe_write(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.warning("failed to write thread artifact %s: %s", path, exc)


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
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("failed to read thread artifact %s: %s", path, exc)
            existing = ""
        for r, raw in _extract_round_sections(existing):
            if r != round_num:
                sections.append((r, {"_raw": raw}))
    sections.append((round_num, body))
    sections.sort(key=lambda item: item[0])
    _safe_write(
        path,
        _render_stage_file(
            node,
            status=status,
            round_num=round_num,
            sections=sections,
        ),
    )


def refresh_from_snapshot(
    thread_dir: Path,
    values: dict[str, Any],
    *,
    status_hints: dict[str, str] | None = None,
) -> None:
    """Refresh all four stage files from checkpoint/snapshot values."""
    hints = status_hints or {}
    round_num = max(int(values.get("rounds") or 1), 1)
    for node in _STAGE_NODES:
        record_node_update(
            thread_dir,
            node=node,
            round_num=round_num,
            payload=values,
            status=hints.get(node, "complete"),
        )
