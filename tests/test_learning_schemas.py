"""Tests for learner structured output schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from graph.schemas import LearningResult, LessonsBlock


def test_learning_result_accepts_pass_with_lessons() -> None:
    """LearningResult accepts pass verdict, lessons, and candidates."""
    result = LearningResult(
        verdict="pass",
        reason="Looks solid",
        suggested_step="finish",
        lessons=LessonsBlock(
            worked=["tools used"],
            failed=[],
            risks=[],
            next_time=["keep verification"],
        ),
        learning_candidates=[
            {
                "id": "m0",
                "content": "Prefer pytest",
                "memory_type": "preference",
                "importance": 0.8,
            },
        ],
    )
    assert result.verdict == "pass"
    assert result.suggested_step == "finish"
    assert result.learning_candidates[0].content == "Prefer pytest"


def test_learning_result_rejects_executor_suggested_step() -> None:
    """suggested_step must be planner or finish, not executor."""
    with pytest.raises(ValidationError):
        LearningResult(
            verdict="fail",
            reason="Incomplete",
            suggested_step="executor",  # type: ignore[arg-type]
            lessons=LessonsBlock(),
            learning_candidates=[],
        )
