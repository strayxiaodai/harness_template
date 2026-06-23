"""Tests for skill prompt injection."""

from __future__ import annotations

from skills.inject import skill_prompt_prefix


def test_skill_prompt_prefix_empty_without_context() -> None:
    """skill_prompt_prefix returns empty when no skill is loaded."""
    assert skill_prompt_prefix({}) == ""


def test_skill_prompt_prefix_includes_slug_and_body() -> None:
    """skill_prompt_prefix formats the harness skill block."""
    text = skill_prompt_prefix(
        {
            "skill_slug": "demo-skill",
            "skill_context": "# Steps\n\nDo the thing.",
        },
    )
    assert "demo-skill" in text
    assert "Do the thing." in text
