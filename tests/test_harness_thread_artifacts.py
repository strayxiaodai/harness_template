"""Tests that harness run/stream write thread stage artifacts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.schemas.run import ResumeRequest, RunRequest, RunResponse
from app.services.harness import resume_harness, run_harness, stream_harness


def _run_response(**kwargs: object) -> RunResponse:
    base = {
        "thread_id": "t1",
        "status": "complete",
        "approved": True,
        "needs_human": False,
        "rounds": 1,
        "max_rounds": 3,
        "plan": ["p"],
        "result": "done",
    }
    base.update(kwargs)
    return RunResponse(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_run_harness_inits_thread_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_harness creates app/threads folder with stage markdown files."""
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path / "threads"))
    request = MagicMock(spec=Request)
    graph = MagicMock()

    async def fake_invoke(*_a: object, **_k: object) -> None:
        return None

    with (
        patch("app.services.harness.graph_for_request", return_value=graph),
        patch("app.services.harness.invoke_with_timeout", side_effect=fake_invoke),
        patch(
            "app.services.harness.snapshot_to_response",
            new=AsyncMock(return_value=_run_response()),
        ),
    ):
        body = RunRequest(thread_id="t1", task="Wire harness artifacts")
        await run_harness(request, body)

    planners = list((tmp_path / "threads").glob("*/planner.md"))
    assert planners, "expected planner.md under thread artifacts"
    assert "Wire harness artifacts" in (
        planners[0].parent / "meta.json"
    ).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_stream_harness_records_node_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stream_harness writes node patches into stage markdown files."""
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path / "threads"))
    request = MagicMock(spec=Request)
    graph = MagicMock()

    async def fake_astream(*_a: object, **_k: object):
        yield {"planner": {"plan": ["step-one"], "rounds": 1}}

    graph.astream = fake_astream

    with (
        patch("app.services.harness.graph_for_request", return_value=graph),
        patch(
            "app.services.harness.snapshot_to_response",
            new=AsyncMock(return_value=_run_response(plan=["step-one"])),
        ),
    ):
        body = RunRequest(thread_id="t-stream", task="Stream artifact write")
        chunks = [chunk async for chunk in stream_harness(request, body)]

    assert any("final" in c for c in chunks)
    text = next((tmp_path / "threads").glob("*/planner.md")).read_text(
        encoding="utf-8",
    )
    assert "step-one" in text


@pytest.mark.asyncio
async def test_resume_harness_refreshes_existing_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resume_harness updates stage files when thread is indexed."""
    threads = tmp_path / "threads"
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(threads))

    import app.services.thread_artifacts as ta

    path = ta.init_thread_artifacts(
        task="Resume artifacts",
        thread_id="t-resume",
        plan=["old"],
    )

    request = MagicMock(spec=Request)
    graph = MagicMock()
    snapshot = MagicMock()
    snapshot.values = {"human_in_the_loop": True, "plan": ["old"]}
    snapshot.interrupts = ()
    graph.aget_state = AsyncMock(return_value=snapshot)
    request.app.state.graph_step = graph

    async def fake_invoke(*_a: object, **_k: object) -> None:
        return None

    with (
        patch("app.services.harness.invoke_with_timeout", side_effect=fake_invoke),
        patch(
            "app.services.harness.snapshot_to_response",
            new=AsyncMock(
                return_value=_run_response(
                    thread_id="t-resume",
                    plan=["new-plan"],
                    result="resumed",
                ),
            ),
        ),
    ):
        body = ResumeRequest(thread_id="t-resume")
        await resume_harness(request, body)

    text = (path / "planner.md").read_text(encoding="utf-8")
    assert "new-plan" in text
