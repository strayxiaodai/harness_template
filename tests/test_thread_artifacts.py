"""Tests for on-disk thread stage artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.services.thread_artifacts as ta

STAGE_FILES = ("planner.md", "executor.md", "learner.md", "actioner.md")


@pytest.fixture()
def threads_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HARNESS_THREADS_DIR at a temp folder."""
    root = tmp_path / "threads"
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(root))
    return root


def test_init_creates_meta_and_four_stage_files(threads_dir: Path) -> None:
    """init seeds meta.json, four pending stage files, and index entry."""
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
    """Second init with same task gets a slug-thread_id suffix directory."""
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


def test_record_node_update_writes_planner_contents(threads_dir: Path) -> None:
    """Node update writes status, round, and stage payload into planner.md."""
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
    """Unknown graph nodes do not alter stage markdown files."""
    path = ta.init_thread_artifacts(task="x", thread_id="t-x", plan=[])
    ta.record_node_update(
        path,
        node="unknown",
        round_num=1,
        payload={},
        status="complete",
    )
    assert "status: pending" in (path / "planner.md").read_text(encoding="utf-8")


def test_refresh_from_snapshot_updates_all_stages(threads_dir: Path) -> None:
    """Snapshot refresh updates all four stage markdown files."""
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
        status_hints={
            "planner": "complete",
            "executor": "complete",
            "learner": "complete",
            "actioner": "complete",
        },
    )
    assert "one" in (path / "planner.md").read_text(encoding="utf-8")
    assert "done" in (path / "executor.md").read_text(encoding="utf-8")
    assert "pass" in (path / "learner.md").read_text(encoding="utf-8")
    assert "0.9" in (path / "actioner.md").read_text(encoding="utf-8")


def test_disk_errors_do_not_raise(
    threads_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSError during stage write is logged and swallowed."""
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


def test_list_threads_empty(threads_dir: Path) -> None:
    """F1: Empty root yields an empty list."""
    assert ta.list_threads() == []


def test_list_threads_sorted_by_started_at(threads_dir: Path) -> None:
    """F2+F3: Summaries from index+meta; newest started_at first."""
    threads_dir.mkdir(parents=True, exist_ok=True)
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
    threads_dir.mkdir(parents=True, exist_ok=True)
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
    threads_dir.mkdir(parents=True, exist_ok=True)
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
    threads_dir.mkdir(parents=True, exist_ok=True)
    (threads_dir / ".index.json").write_text(
        json.dumps({"id-ghost": "no-such-dir"}) + "\n",
        encoding="utf-8",
    )
    assert ta.list_threads() == []


def test_list_threads_prefers_index_thread_id(threads_dir: Path) -> None:
    """F7: Index key wins when meta.thread_id disagrees."""
    threads_dir.mkdir(parents=True, exist_ok=True)
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
    threads_dir.mkdir(parents=True, exist_ok=True)
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
