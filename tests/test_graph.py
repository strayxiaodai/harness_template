"""Tests for graph routing and builder shape."""

from __future__ import annotations

import pytest

from graph.routing import DEFAULT_MAX_ROUNDS, route_after_action


def _state(**overrides: object) -> dict[str, object]:
    """Build a minimal AgentState dict for routing tests."""
    base: dict[str, object] = {
        "thread_id": "test-thread",
        "task": "Implement feature",
        "messages": [],
        "plan": [],
        "rounds": 0,
        "max_rounds": 3,
        "role": "memorize",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


def test_route_finishes_when_approved() -> None:
    """Approved checks should finish."""
    assert route_after_action(_state(approved=True)) == "finish"


def test_route_defaults_to_executor_refinement() -> None:
    """Failed checks should resume execution by default."""
    assert route_after_action(_state()) == "executor"


def test_route_can_resume_at_planner() -> None:
    """Planning suggestions should restart refinement from planning."""
    assert route_after_action(_state(refine_from="planner")) == "planner"


def test_route_respects_round_budget() -> None:
    """The loop must finish once the round budget is exhausted."""
    assert (
        route_after_action(
            _state(rounds=3, max_rounds=3, refine_from="executor"),
        )
        == "finish"
    )


def test_default_round_budget_is_three() -> None:
    """The default budget must terminate after three rounds."""
    assert DEFAULT_MAX_ROUNDS == 3
    state = _state(rounds=3)
    state.pop("max_rounds")
    assert route_after_action(state) == "finish"


def test_route_honors_finish_suggestion() -> None:
    """Explicit finish suggestion should end the loop."""
    assert route_after_action(_state(refine_from="finish")) == "finish"


def test_create_workflow_has_expected_nodes() -> None:
    """Workflow includes planner through memorize."""
    pytest.importorskip("langgraph")
    from graph.builder import HITL_PAUSE_NODES, create_workflow

    workflow = create_workflow()
    assert set(workflow.nodes) == {
        "planner",
        "executor",
        "reviewer",
        "actioner",
        "memorize",
    }
    assert HITL_PAUSE_NODES == [
        "planner",
        "executor",
        "reviewer",
        "memorize",
    ]


def test_compile_with_memory_checkpointer() -> None:
    """Graph compiles with an in-memory checkpointer."""
    pytest.importorskip("langgraph")
    from langgraph.checkpoint.memory import MemorySaver

    from graph.builder import compile_with_checkpointer

    graph = compile_with_checkpointer(MemorySaver())
    assert graph is not None
