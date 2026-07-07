"""Tests for harness skill distillation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.context import format_thread_context
from skills.distill import SkillNotEligibleError, distill_skill_from_thread, save_skill_draft
from skills.schemas import SkillDraft
from skills.store import list_skills, read_skill, slugify, write_skill


def test_slugify_normalizes_text() -> None:
    """slugify produces kebab-case slugs."""
    assert slugify("Add SQLite Checkpoints!") == "add-sqlite-checkpoints"


def test_format_thread_context_includes_task_and_plan() -> None:
    """Thread context includes key harness fields."""
    text = format_thread_context(
        {
            "task": "ship feature",
            "plan": ["step one", "step two"],
            "result": "done",
            "rounds": 1,
            "max_rounds": 3,
            "approved": True,
            "thread_id": "t-1",
        },
    )
    assert "ship feature" in text
    assert "step one" in text
    assert "done" in text


def test_write_and_list_skill(tmp_path: Path) -> None:
    """write_skill persists SKILL.md and harness provenance."""
    path = write_skill(
        "demo-skill",
        name="demo-skill",
        description="Demo distilled skill",
        body="# Demo\n\nDo the thing.",
        thread_id="thread-1",
        task="demo task",
        rounds=2,
        root=tmp_path,
    )
    assert path.is_file()
    name, description, body = read_skill("demo-skill", root=tmp_path)
    assert name == "demo-skill"
    assert description == "Demo distilled skill"
    assert "Do the thing." in body

    summaries = list_skills(root=tmp_path)
    assert len(summaries) == 1
    assert summaries[0].slug == "demo-skill"
    assert summaries[0].thread_count == 1


def _snapshot(values: dict[str, Any], *, next_nodes: tuple[str, ...] = ()) -> MagicMock:
    snap = MagicMock()
    snap.values = values
    snap.next = next_nodes
    return snap


@pytest.mark.asyncio
async def test_distill_skill_from_thread_creates_skill(tmp_path: Path) -> None:
    """distill_skill_from_thread writes a new skill from checkpoint state."""
    graph = MagicMock()
    graph.aget_state = AsyncMock(
        return_value=_snapshot(
            {
                "thread_id": "thread-abc",
                "task": "Add health endpoint",
                "plan": ["inspect api", "add route"],
                "result": "health route added",
                "rounds": 1,
                "max_rounds": 3,
                "approved": True,
                "execution": {"summary": "added route"},
                "review": {"verdict": "pass", "reason": "ok"},
                "loop_score": 85,
                "skill_preview_ready": True,
            },
        ),
    )

    draft = SkillDraft(
        name="add-health-endpoint",
        description="Add a FastAPI health endpoint to the harness API.",
        body="# Add health endpoint\n\n1. Inspect `api/server.py`.\n2. Add `GET /health`.",
    )

    with (
        patch("skills.store.skills_root", return_value=tmp_path),
        patch("skills.distill._draft_skill", AsyncMock(return_value=draft)),
    ):
        result = await distill_skill_from_thread(
            graph,
            thread_id="thread-abc",
            save=True,
        )

    assert result.created is True
    assert result.refined is False
    assert result.saved is True
    assert result.slug == "add-health-endpoint"
    assert Path(result.path).is_file()
    _, description, body = read_skill("add-health-endpoint", root=tmp_path)
    assert "health endpoint" in description.lower()
    assert "GET /health" in body


@pytest.mark.asyncio
async def test_distill_skill_preview_does_not_write(tmp_path: Path) -> None:
    """distill_skill_from_thread with save=False returns draft without writing."""
    graph = MagicMock()
    graph.aget_state = AsyncMock(
        return_value=_snapshot(
            {
                "thread_id": "thread-abc",
                "task": "Preview only",
                "rounds": 1,
                "max_rounds": 3,
                "approved": True,
                "review": {"verdict": "pass", "reason": "ok"},
                "loop_score": 85,
                "skill_preview_ready": True,
            },
        ),
    )

    draft = SkillDraft(
        name="preview-only",
        description="Preview skill",
        body="# Preview\n\nNot saved yet.",
    )

    with (
        patch("skills.store.skills_root", return_value=tmp_path),
        patch("skills.distill._draft_skill", AsyncMock(return_value=draft)),
    ):
        result = await distill_skill_from_thread(
            graph,
            thread_id="thread-abc",
            save=False,
        )

    assert result.saved is False
    assert result.path is None
    assert result.body == "# Preview\n\nNot saved yet."
    assert not (tmp_path / "preview-only" / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_distill_rejects_thread_before_first_loop() -> None:
    """distill_skill_from_thread rejects threads that have not finished a loop."""
    graph = MagicMock()
    graph.aget_state = AsyncMock(
        return_value=_snapshot(
            {
                "thread_id": "thread-early",
                "task": "Too early",
                "rounds": 0,
                "plan": ["step one"],
            },
        ),
    )

    with pytest.raises(SkillNotEligibleError):
        await distill_skill_from_thread(graph, thread_id="thread-early")


@pytest.mark.asyncio
async def test_save_skill_draft_writes_file(tmp_path: Path) -> None:
    """save_skill_draft persists a preview without calling the LLM."""
    graph = MagicMock()
    graph.aget_state = AsyncMock(
        return_value=_snapshot(
            {
                "thread_id": "thread-abc",
                "task": "Save draft",
                "rounds": 1,
                "max_rounds": 3,
                "approved": True,
                "review": {"verdict": "pass", "reason": "ok"},
                "loop_score": 85,
                "skill_preview_ready": True,
            },
        ),
    )

    with patch("skills.store.skills_root", return_value=tmp_path):
        result = await save_skill_draft(
            graph,
            thread_id="thread-abc",
            slug="saved-skill",
            name="saved-skill",
            description="Saved from preview",
            body="# Saved\n\nPersisted.",
        )

    assert result.saved is True
    assert Path(result.path or "").is_file()
    _, description, body = read_skill("saved-skill", root=tmp_path)
    assert description == "Saved from preview"
    assert "Persisted." in body


@pytest.mark.asyncio
async def test_distill_skill_refines_existing_skill(tmp_path: Path) -> None:
    """distill_skill_from_thread merges when refine is enabled."""
    write_skill(
        "shared-skill",
        name="shared-skill",
        description="Original",
        body="# Original\n\nStep A.",
        thread_id="old-thread",
        task="old task",
        rounds=1,
        root=tmp_path,
    )

    graph = MagicMock()
    graph.aget_state = AsyncMock(
        return_value=_snapshot(
            {
                "thread_id": "new-thread",
                "task": "shared skill",
                "plan": ["step b"],
                "result": "done",
                "rounds": 2,
                "max_rounds": 3,
                "approved": True,
                "execution": {"summary": "step b"},
                "review": {"verdict": "pass", "reason": "ok"},
                "loop_score": 88,
                "skill_preview_ready": True,
            },
        ),
    )

    draft = SkillDraft(
        name="shared-skill",
        description="Refined shared skill",
        body="# Shared skill\n\nStep A.\n\nStep B.",
    )

    with (
        patch("skills.store.skills_root", return_value=tmp_path),
        patch("skills.distill._draft_skill", AsyncMock(return_value=draft)),
    ):
        result = await distill_skill_from_thread(
            graph,
            thread_id="new-thread",
            refine=True,
            save=True,
        )

    assert result.created is False
    assert result.refined is True
    assert result.saved is True
    summaries = list_skills(root=tmp_path)
    assert summaries[0].thread_count == 2
