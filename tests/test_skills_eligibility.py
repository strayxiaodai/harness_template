"""Tests for skill distillation eligibility."""

from __future__ import annotations

from skills.eligibility import thread_eligible_for_skill


def test_thread_not_eligible_before_first_loop() -> None:
    """Threads with zero rounds cannot be distilled."""
    eligible, reason = thread_eligible_for_skill(
        {
            "rounds": 0,
            "execution": {"summary": "done"},
            "review": {"verdict": "pass"},
        },
    )
    assert eligible is False
    assert "at least one harness loop" in reason.lower()


def test_thread_not_eligible_without_execution_or_review() -> None:
    """Threads need executor or reviewer output from a completed loop."""
    eligible, reason = thread_eligible_for_skill({"rounds": 1})
    assert eligible is False
    assert "executor and reviewer" in reason.lower()


def test_thread_eligible_after_one_loop() -> None:
    """Threads with one round and review output can be distilled."""
    eligible, reason = thread_eligible_for_skill(
        {
            "rounds": 1,
            "execution": {"summary": "implemented feature"},
            "review": {"verdict": "pass", "reason": "looks good"},
        },
    )
    assert eligible is True
    assert reason == ""
