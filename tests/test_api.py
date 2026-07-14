"""Tests for the FastAPI service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas import ResumeRequest, RunRequest, RunResponse


def _snapshot(
    values: dict[str, Any],
    *,
    next_nodes: tuple[str, ...] = (),
    interrupts: tuple[Any, ...] = (),
) -> MagicMock:
    """Build a fake LangGraph state snapshot."""
    snap = MagicMock()
    snap.values = values
    snap.next = next_nodes
    snap.interrupts = interrupts
    return snap


def _mock_graph(
  values: dict[str, Any],
  *,
  next_nodes: tuple[str, ...] = (),
  interrupts: tuple[Any, ...] = (),
) -> MagicMock:
    """Build a mock compiled graph."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=None)
    graph.aget_state = AsyncMock(
        return_value=_snapshot(
            values,
            next_nodes=next_nodes,
            interrupts=interrupts,
        ),
    )

    async def _astream(*_args: object, **_kwargs: object):
        yield {"planner": {"role": "planner"}}

    graph.astream = _astream
    return graph


@pytest.fixture
def client() -> TestClient:
    """Test client with mocked graphs on app state."""
    from app.main import app

    complete_values = {
        "approved": True,
        "result": "all done",
        "role": "memorize",
        "rounds": 1,
        "max_rounds": 3,
        "human_in_the_loop": False,
    }
    hitl_values = {
        "approved": False,
        "result": "partial",
        "role": "planner",
        "rounds": 0,
        "max_rounds": 3,
        "human_in_the_loop": True,
    }

    app.state.graph_auto = _mock_graph(complete_values)
    app.state.graph_step = _mock_graph(
        hitl_values,
        next_nodes=("executor",),
    )

    return TestClient(app, raise_server_exceptions=True)


def test_health_ok(client: TestClient) -> None:
    """Health endpoint reports ok when graphs are compiled."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_run_returns_complete_response(client: TestClient) -> None:
    """POST /run returns a complete RunResponse."""
    response = client.post(
        "/run",
        json={
            "thread_id": "t1",
            "task": "build feature",
            "max_rounds": 3,
        },
    )
    assert response.status_code == 200
    body = RunResponse.model_validate(response.json())
    assert body.thread_id == "t1"
    assert body.status == "complete"
    assert body.approved is True
    assert body.result == "all done"
    assert body.skill_eligible is False
    assert body.skill_ineligible_reason


@pytest.mark.asyncio
async def test_snapshot_marks_skill_eligible_after_loop() -> None:
    """RunResponse reflects checkpoint eligibility for skill distillation."""
    from app.services.snapshot import snapshot_to_response

    graph = _mock_graph(
        {
            "approved": True,
            "result": "done",
            "role": "memorize",
            "rounds": 1,
            "max_rounds": 3,
            "human_in_the_loop": True,
            "execution": {
                "summary": "shipped",
                "changes": [],
                "risks": [],
                "verification": [],
            },
            "learning": {
                "verdict": "pass",
                "reason": "ok",
                "suggested_step": "finish",
            },
            "loop_score": 85,
            "skill_preview_ready": True,
        },
    )
    response = await snapshot_to_response(graph, "thread-1")
    assert response.skill_eligible is True
    assert response.skill_ineligible_reason is None


@pytest.mark.asyncio
async def test_snapshot_includes_action_review_interrupt() -> None:
    """RunResponse exposes dynamic interrupt and compact learning fields."""
    from app.services.snapshot import snapshot_to_response

    interrupt = MagicMock()
    interrupt.id = "int-1"
    interrupt.value = {
        "kind": "action_review",
        "node": "actioner",
        "memories": [],
        "score": 85,
        "threshold": 80,
        "skill_preview_ready": True,
        "message": "Skill preview is available.",
    }
    graph = _mock_graph(
        {
            "approved": True,
            "role": "actioner",
            "rounds": 1,
            "max_rounds": 3,
            "human_in_the_loop": True,
            "plan": ["a"],
            "learning": {
                "verdict": "pass",
                "reason": "ok",
                "suggested_step": "finish",
                "lessons": {
                    "worked": [],
                    "failed": [],
                    "risks": [],
                    "next_time": [],
                },
            },
            "loop_score": 85,
            "skill_preview_ready": True,
        },
        next_nodes=(),
        interrupts=(interrupt,),
    )
    response = await snapshot_to_response(graph, "thread-1")
    assert response.needs_human is True
    assert response.interrupt is not None
    assert response.interrupt.value["kind"] == "action_review"
    assert response.plan == ["a"]
    assert response.loop_score == 85
    assert response.learning is not None
    assert response.next_action == "actioner"


def test_resume_requires_hitl_thread(client: TestClient) -> None:
    """POST /resume returns 409 for non-HITL threads."""
    from app.main import app

    app.state.graph_step = _mock_graph(
        {
            "approved": False,
            "human_in_the_loop": False,
            "rounds": 1,
            "max_rounds": 3,
            "role": "memorize",
        },
    )

    response = client.post("/resume", json={"thread_id": "t1"})
    assert response.status_code == 409


def test_resume_applies_overrides(client: TestClient) -> None:
    """POST /resume forwards overrides to update_state."""
    from app.main import app

    graph = _mock_graph(
        {
            "approved": False,
            "human_in_the_loop": True,
            "rounds": 0,
            "max_rounds": 3,
            "role": "planner",
        },
        next_nodes=("executor",),
    )
    graph.aupdate_state = AsyncMock()
    app.state.graph_step = graph

    response = client.post(
        "/resume",
        json={
            "thread_id": "t1",
            "overrides": {"plan": ["step one", "step two"]},
        },
    )
    assert response.status_code == 200
    graph.aupdate_state.assert_awaited_once()
    patch = graph.aupdate_state.await_args.args[1]
    assert patch == {"plan": ["step one", "step two"]}


def test_resume_learning_override_syncs_approved(client: TestClient) -> None:
    """Learning overrides merge lessons and sync the approved bit."""
    from app.main import app

    graph = _mock_graph(
        {
            "approved": False,
            "human_in_the_loop": True,
            "rounds": 0,
            "max_rounds": 3,
            "role": "learner",
            "learning": {
                "verdict": "fail",
                "reason": "incomplete",
                "suggested_step": "planner",
                "lessons": {
                    "worked": [],
                    "failed": ["missing tests"],
                    "risks": [],
                    "next_time": [],
                },
            },
        },
        next_nodes=("actioner",),
    )
    graph.aupdate_state = AsyncMock()
    app.state.graph_step = graph

    response = client.post(
        "/resume",
        json={
            "thread_id": "t1",
            "overrides": {
                "learning": {
                    "verdict": "pass",
                    "reason": "Operator override: accept",
                    "suggested_step": "finish",
                },
            },
        },
    )
    assert response.status_code == 200
    patch = graph.aupdate_state.await_args.args[1]
    assert patch["approved"] is True
    assert patch["learning"]["lessons"]["failed"] == ["missing tests"]
    assert patch["learning"]["verdict"] == "pass"


def test_resume_request_rejects_unknown_override_key() -> None:
    """ResumeRequest must reject non-allowlisted override keys."""
    with pytest.raises(ValidationError):
        ResumeRequest(thread_id="t1", overrides={"rounds": 5})  # type: ignore[arg-type]


def test_stream_returns_event_stream(client: TestClient) -> None:
    """POST /stream returns text/event-stream."""
    response = client.post(
        "/stream",
        json={"thread_id": "t2", "task": "stream me"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data:" in response.text


def test_run_request_validation() -> None:
    """RunRequest enforces bounds on max_rounds and task/skill requirements."""
    with pytest.raises(ValidationError):
        RunRequest(thread_id="t", task="x", max_rounds=0)
    with pytest.raises(ValidationError):
        RunRequest(thread_id="t", task="")
    RunRequest(thread_id="t", skill_slug="demo-skill")


def test_list_skills_empty(client: TestClient) -> None:
    """GET /skills returns an empty list when no skills exist."""
    with patch("app.services.skills.list_skills", return_value=[]):
        response = client.get("/skills")
    assert response.status_code == 200
    assert response.json() == []


def test_distill_skill_endpoint(client: TestClient) -> None:
    """POST /skills/distill returns the distilled skill metadata."""
    from app.main import app
    from skills.schemas import DistillSkillResponse as InternalResponse

    app.state.graph_auto = _mock_graph({"thread_id": "t1", "task": "demo"})

    fake = InternalResponse(
        thread_id="t1",
        slug="demo",
        path="/tmp/demo/SKILL.md",
        saved=True,
        created=True,
        refined=False,
        description="Demo skill",
        name="demo",
        body="# Demo",
        status="complete",
    )

    with patch(
        "app.services.skills.distill_skill_from_thread",
        AsyncMock(return_value=fake),
    ):
        response = client.post(
            "/skills/distill",
            json={"thread_id": "t1", "refine": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "demo"
    assert body["saved"] is True


def test_get_skill_not_found(client: TestClient) -> None:
    """GET /skills/{slug} returns 404 for missing skills."""
    with patch("app.services.skills.read_skill", side_effect=FileNotFoundError("missing")):
        response = client.get("/skills/missing-skill")
    assert response.status_code == 404


def test_get_skill_returns_detail(client: TestClient) -> None:
    """GET /skills/{slug} returns the skill playbook."""
    with (
        patch(
            "app.services.skills.read_skill",
            return_value=("demo", "Demo skill", "# Demo body"),
        ),
        patch("app.services.skills.read_meta") as read_meta,
        patch("app.services.skills.skill_path", return_value="/tmp/demo/SKILL.md"),
    ):
        read_meta.return_value = type(
            "Meta",
            (),
            {"thread_ids": ["t1"], "distilled_at": ["2026-01-01T00:00:00+00:00"]},
        )()
        response = client.get("/skills/demo-skill")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "demo-skill"
    assert body["body"] == "# Demo body"
