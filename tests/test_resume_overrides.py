"""Tests for normalizing HITL resume overrides before aupdate_state."""

from __future__ import annotations

from app.services.resume_overrides import apply_resume_overrides


def test_learning_override_syncs_approved_and_keeps_lessons() -> None:
    """Flipping verdict must update approved without wiping lessons."""
    current = {
        "approved": False,
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
    }
    patch = apply_resume_overrides(
        current,
        {
            "learning": {
                "verdict": "pass",
                "reason": "Operator override: accept",
                "suggested_step": "finish",
            },
        },
    )

    assert patch["approved"] is True
    assert patch["learning"]["verdict"] == "pass"
    assert patch["learning"]["reason"] == "Operator override: accept"
    assert patch["learning"]["suggested_step"] == "finish"
    assert patch["learning"]["lessons"]["failed"] == ["missing tests"]


def test_learning_fail_override_clears_approved() -> None:
    """pass → fail overrides must clear the approved bit."""
    current = {
        "approved": True,
        "learning": {
            "verdict": "pass",
            "reason": "ok",
            "suggested_step": "finish",
            "lessons": {"worked": ["done"], "failed": [], "risks": [], "next_time": []},
        },
    }
    patch = apply_resume_overrides(
        current,
        {
            "learning": {
                "verdict": "fail",
                "reason": "Operator override: replan",
                "suggested_step": "planner",
            },
        },
    )

    assert patch["approved"] is False
    assert patch["learning"]["lessons"]["worked"] == ["done"]


def test_refine_from_override_syncs_learning_suggested_step() -> None:
    """refine_from override must survive actioner via learning.suggested_step."""
    current = {
        "approved": False,
        "learning": {
            "verdict": "fail",
            "reason": "incomplete",
            "suggested_step": "planner",
            "lessons": {"worked": [], "failed": [], "risks": [], "next_time": []},
        },
    }
    patch = apply_resume_overrides(current, {"refine_from": "finish"})

    assert patch["refine_from"] == "finish"
    assert patch["learning"]["suggested_step"] == "finish"
    assert patch["learning"]["verdict"] == "fail"
    assert patch["approved"] is False
