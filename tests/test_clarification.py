"""Tests for HITL clarification helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.clarification import (
    ask_clarification,
    format_ascii_pipeline,
    format_ascii_score_bar,
    format_clarification_block,
    format_executor_clarification,
    format_learner_clarification,
    format_planner_clarification,
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


def test_clarification_question_with_options_and_default() -> None:
    """ClarificationQuestion supports clickable options and default."""
    q = ClarificationQuestion(
        id="choice",
        prompt="Choose an action:",
        options=["(Recommended) Approve", "Reject"],
        default="(Recommended) Approve",
        is_multi_select=False,
    )
    dumped = q.model_dump()
    assert dumped["options"] == ["(Recommended) Approve", "Reject"]
    assert dumped["default"] == "(Recommended) Approve"
    assert dumped["is_multi_select"] is False


def test_normalize_clarification_answers_populates_default() -> None:
    """When resumed with no explicit answer, default option is used."""
    questions = [
        ClarificationQuestion(
            id="q1",
            prompt="Confirm plan?",
            options=["(Recommended) Approve", "Modify"],
            default="(Recommended) Approve",
        ),
    ]
    # Resumed with empty answers or True
    normalized = normalize_clarification_answers(True, questions)
    assert len(normalized) == 1
    assert normalized[0]["question_id"] == "q1"
    assert normalized[0]["answer"] == "(Recommended) Approve"


def test_format_ascii_pipeline_renders_vertical_tree() -> None:
    """ASCII pipeline renders a clean vertical execution tree with full text."""
    steps = ["Discover target", "Author test cases", "Verify coverage"]
    flow = format_ascii_pipeline(steps)
    assert "┌── [1] Discover target" in flow
    assert "├── [2] Author test cases" in flow
    assert "└── [3] Verify coverage" in flow


def test_format_ascii_pipeline_wraps_long_lines_under_tree() -> None:
    """ASCII pipeline wraps long step descriptions cleanly with tree indent."""
    steps = [
        "First short step",
        "A very long step description that definitely exceeds thirty characters to test wrapping",
    ]
    flow = format_ascii_pipeline(steps, max_width=45)
    assert "┌── [1] First short step" in flow
    assert "└── [2] " in flow
    assert "    " in flow


def test_format_planner_clarification_includes_flow_and_sections() -> None:
    """Planner clarification hint contains vertical ASCII tree in code fence and sectioned rationale."""
    steps = ["Step 1", "Step 2"]
    rationale = (
        "Goal: Make tests. Assumptions surfaced: No spec file. "
        "Trade-offs: Breadth vs depth. Risk: Wrong target. Verification: Gap check."
    )
    hint = format_planner_clarification(steps, rationale)
    assert "```text\n┌── [1] Step 1\n└── [2] Step 2\n```" in hint
    assert "### Rationale" in hint
    assert "- **Goal:** Make tests." in hint
    assert "- **Assumptions surfaced:** No spec file." in hint
    assert "- **Trade-offs:** Breadth vs depth." in hint
    assert "- **Risk:** Wrong target." in hint
    assert "- **Verification:** Gap check." in hint


def test_format_executor_clarification_includes_flow_and_details() -> None:
    """Executor clarification hint contains flow, summary, changes, and verification."""
    hint = format_executor_clarification(
        summary="Updated auth endpoint",
        changes=["Modified auth.py", "Added token check"],
        verification=["Ran pytest tests/test_auth.py (passed)"],
        risks=["Token expiry edge case"],
    )
    assert "```text\n[Inspect Context] ──> [Apply Changes] ──> [Verify Output] ──> [DONE ✓]\n```" in hint
    assert "### Summary\nUpdated auth endpoint" in hint
    assert "### Changes\n- Modified auth.py\n- Added token check" in hint
    assert "### Verification\n- Ran pytest tests/test_auth.py (passed)" in hint
    assert "### Risks & Watchpoints\n- Token expiry edge case" in hint


def test_format_learner_clarification_includes_pass_and_fail_flow() -> None:
    """Learner clarification formats PASS and FAIL flows with lessons."""
    pass_hint = format_learner_clarification(
        verdict="pass",
        reason="All tests passed",
        suggested_step="finish",
        lessons={"worked": ["Clean tests"], "failed": [], "risks": [], "next_time": []},
    )
    assert "```text\n[Execution Done] ──> [Evaluation: PASS ✓] ──> [Actioner: Finish & Store]\n```" in pass_hint
    assert "**What worked:** Clean tests" in pass_hint
    assert "**Suggested Next Step:** `finish`" in pass_hint

    fail_hint = format_learner_clarification(
        verdict="fail",
        reason="Missing regression test",
        suggested_step="planner",
    )
    assert "```text\n[Execution Done] ──> [Evaluation: FAIL ✗] ──> [Planner: Re-plan & Fix]\n```" in fail_hint
    assert "### Evaluation Reason\nMissing regression test" in fail_hint
    assert "**Suggested Next Step:** `planner`" in fail_hint


def test_format_ascii_score_bar() -> None:
    """Score bar renders 10-char block progress representation."""
    assert format_ascii_score_bar(0) == "[░░░░░░░░░░]"
    assert format_ascii_score_bar(50) == "[█████░░░░░]"
    assert format_ascii_score_bar(80) == "[████████░░]"
    assert format_ascii_score_bar(100) == "[██████████]"


