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
