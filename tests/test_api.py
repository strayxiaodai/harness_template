"""Tests for the FastAPI service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.schemas import ResumeRequest, RunRequest, RunResponse


def _snapshot(
    values: dict[str, Any],
    *,
    next_nodes: tuple[str, ...] = (),
) -> MagicMock:
    """Build a fake LangGraph state snapshot."""
    snap = MagicMock()
    snap.values = values
    snap.next = next_nodes
    return snap


def _mock_graph(
  values: dict[str, Any],
  *,
  next_nodes: tuple[str, ...] = (),
) -> MagicMock:
    """Build a mock compiled graph."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=None)
    graph.aget_state = AsyncMock(
        return_value=_snapshot(values, next_nodes=next_nodes),
    )

    async def _astream(*_args: object, **_kwargs: object):
        yield {"planner": {"role": "planner"}}

    graph.astream = _astream
    return graph


@pytest.fixture
def client() -> TestClient:
    """Test client with mocked graphs on app state."""
    from api.server import api

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

    api.state.graph_auto = _mock_graph(complete_values)
    api.state.graph_step = _mock_graph(
        hitl_values,
        next_nodes=("executor",),
    )

    return TestClient(api, raise_server_exceptions=True)


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


def test_resume_requires_hitl_thread(client: TestClient) -> None:
    """POST /resume returns 409 for non-HITL threads."""
    from api.server import api

    api.state.graph_step = _mock_graph(
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
    from api.server import api

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
    api.state.graph_step = graph

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
    with patch("api.server.list_skills", return_value=[]):
        response = client.get("/skills")
    assert response.status_code == 200
    assert response.json() == []


def test_distill_skill_endpoint(client: TestClient) -> None:
    """POST /skills/distill returns the distilled skill metadata."""
    from api.server import api
    from skills.schemas import DistillSkillResponse as InternalResponse

    api.state.graph_auto = _mock_graph({"thread_id": "t1", "task": "demo"})

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
        "api.server.distill_skill_from_thread",
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
    with patch("api.server.read_skill", side_effect=FileNotFoundError("missing")):
        response = client.get("/skills/missing-skill")
    assert response.status_code == 404


def test_get_skill_returns_detail(client: TestClient) -> None:
    """GET /skills/{slug} returns the skill playbook."""
    with (
        patch(
            "api.server.read_skill",
            return_value=("demo", "Demo skill", "# Demo body"),
        ),
        patch("api.server.read_meta") as read_meta,
        patch("api.server.skill_path", return_value="/tmp/demo/SKILL.md"),
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
