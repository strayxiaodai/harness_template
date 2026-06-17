"""Tests for the actioner agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


def _state(**overrides: object) -> dict[str, Any]:
    """Build a minimal AgentState dict for actioner tests."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": ["step one"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "actioner",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_actioner_increments_rounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner must bump the round counter by one."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())

    result = await actioner_module.actioner_agent(_state(rounds=1))

    assert result["role"] == "actioner"
    assert result["rounds"] == 2


@pytest.mark.asyncio
async def test_actioner_sets_refine_from_from_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner copies the reviewer's suggested_step into refine_from."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())

    result = await actioner_module.actioner_agent(
        _state(
            review={
                "verdict": "fail",
                "reason": "needs more tests",
                "suggested_step": "executor",
            },
        ),
    )

    assert result["refine_from"] == "executor"


@pytest.mark.asyncio
async def test_actioner_defaults_to_finish_when_no_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing review should default refine_from to finish."""
    from app.agents import actioner as actioner_module

    monkeypatch.setattr(actioner_module, "write_audit_event", AsyncMock())

    result = await actioner_module.actioner_agent(_state())

    assert result["refine_from"] == "finish"


@pytest.mark.asyncio
async def test_actioner_writes_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actioner must audit the routing decision."""
    from app.agents import actioner as actioner_module

    audit = AsyncMock()
    monkeypatch.setattr(actioner_module, "write_audit_event", audit)

    await actioner_module.actioner_agent(
        _state(
            rounds=2,
            approved=True,
            review={
                "verdict": "pass",
                "reason": "looks good",
                "suggested_step": "finish",
            },
        ),
    )

    audit.assert_awaited_once()
    kwargs = audit.await_args.kwargs
    assert kwargs["thread_id"] == "test-thread"
    assert kwargs["round_number"] == 3
    assert kwargs["node"] == "actioner"
    assert kwargs["event_type"] == "route_decision"
    assert kwargs["payload"] == {
        "suggested_step": "finish",
        "approved": True,
    }
