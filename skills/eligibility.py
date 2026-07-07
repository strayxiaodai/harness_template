"""Eligibility rules for distilling harness threads into skills."""

from __future__ import annotations

from typing import Any

MIN_ROUNDS_FOR_SKILL = 1
SKILL_PREVIEW_SCORE_THRESHOLD = 80


def thread_eligible_for_skill(values: dict[str, Any]) -> tuple[bool, str]:
    """Return whether a thread has completed at least one harness loop.

    A loop is planner → executor → reviewer → actioner → memorize. The
    actioner increments ``rounds``, so ``rounds >= 1`` means at least one
    full cycle finished (or was interrupted after actioner on round 1).

    Args:
        values: LangGraph checkpoint values for the thread.

    Returns:
        Tuple of (eligible, reason). ``reason`` is empty when eligible.
    """
    rounds = int(values.get("rounds", 0))
    if rounds < MIN_ROUNDS_FOR_SKILL:
        return (
            False,
            "Complete at least one harness loop before saving a skill "
            f"(planner → executor → reviewer → actioner → memorize). "
            f"Current rounds: {rounds}.",
        )

    has_execution = bool(values.get("execution"))
    has_review = bool(values.get("review"))
    if not has_execution and not has_review:
        return (
            False,
            "At least one loop must produce executor and reviewer output "
            "before saving a skill.",
        )

    if not values.get("skill_preview_ready"):
        loop_score = int(values.get("loop_score", 0))
        return (
            False,
            "Loop quality score must be at least "
            f"{SKILL_PREVIEW_SCORE_THRESHOLD} before previewing a skill "
            f"(current score: {loop_score}). Continue refining or resume "
            "after a stronger loop.",
        )

    return True, ""
