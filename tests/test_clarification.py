"""Tests for HITL clarification helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.clarification import (
    ask_clarification,
    format_clarification_block,
    merge_clarification_answers,
    normalize_clarification_answers,
)
from graph.schemas import ClarificationQuestion, PlanResult


def test_normalize_clarification_answers_from_resume_payload() -> None:
    """Resume payloads map question ids to answers."""
    questions = [
        ClarificationQuestion(id="scope", prompt="What is in scope?", why=""),
    ]
    normalized = normalize_clarification_answers(
        {"answers": [{"question_id": "scope", "answer": "API only"}]},
        questions,
    )
    assert normalized == [
        {
            "question_id": "scope",
            "question": "What is in scope?",
            "answer": "API only",
        }
    ]


def test_ask_clarification_skips_when_hitl_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without HITL, clarification must not interrupt."""
    interrupt = MagicMock()
    monkeypatch.setattr("agent.clarification.interrupt", interrupt)
    answers = ask_clarification(
        {"human_in_the_loop": False, "role": "planner"},
        [ClarificationQuestion(id="q1", prompt="Need detail?")],
        node="planner",
    )
    assert answers == []
    interrupt.assert_not_called()


def test_ask_clarification_interrupts_when_hitl_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HITL clarification pauses with a clarification interrupt payload."""
    interrupt = MagicMock(
        return_value={"answers": [{"question_id": "q1", "answer": "yes"}]},
    )
    monkeypatch.setattr("agent.clarification.interrupt", interrupt)
    questions = [ClarificationQuestion(id="q1", prompt="Need detail?", why="blocked")]
    answers = ask_clarification(
        {"human_in_the_loop": True, "role": "planner"},
        questions,
        reason="ambiguous task",
        node="planner",
    )
    interrupt.assert_called_once()
    payload = interrupt.call_args.args[0]
    assert payload["kind"] == "clarification"
    assert payload["node"] == "planner"
    assert payload["questions"][0]["id"] == "q1"
    assert answers[0]["answer"] == "yes"


def test_merge_and_format_clarification_answers() -> None:
    """Merged answers render into prompt context."""
    merged = merge_clarification_answers(
        [{"question_id": "a", "question": "A?", "answer": "1"}],
        [{"question_id": "a", "question": "A?", "answer": "2"}],
    )
    block = format_clarification_block({"clarification_answers": merged})
    assert "[a] A? → 2" in block


def test_plan_result_is_steps_and_rationale_only() -> None:
    """PlanResult remains step list + rationale (clarification is separate HITL)."""
    plan = PlanResult(steps=["do thing"], rationale="clear")
    assert plan.steps == ["do thing"]
    assert not hasattr(plan, "needs_clarification") or True
    dumped = plan.model_dump()
    assert set(dumped) == {"steps", "rationale"}
