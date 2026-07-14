"""Smoke tests for executor/learner script-related prompts."""

from __future__ import annotations

from config.prompts import PROMPTS


def test_executor_prompt_mentions_scripts() -> None:
    """Executor system prompt steers toward thread scripts/manifest."""
    text = PROMPTS["executor"]["system"]
    assert "manifest" in text.lower() or "scripts/" in text


def test_learner_prompt_mentions_run_thread_script() -> None:
    """Learner system prompt mentions sandboxed script verification."""
    text = PROMPTS["learner"]["system"]
    assert "run_thread_script" in text or "Docker" in text or "manifest" in text.lower()
