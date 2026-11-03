"""LLM prompt rewrite for general user tasks and inputs."""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic_ai import Agent

from config.prompts import PROMPTS
from llm.providers import get_model
from llm.retry import run_agent

logger = logging.getLogger(__name__)


def is_task_rewrite_enabled(state: dict[str, Any] | None = None) -> bool:
    """Check if task rewriting is enabled via state or environment."""
    if state and "rewrite_task" in state and state["rewrite_task"] is not None:
        return bool(state["rewrite_task"])
    return os.getenv("TASK_REWRITE_ENABLED", "false").lower() in ("true", "1", "yes")


def format_task_rewrite_input(
    task: str,
    recent_messages: list[BaseMessage] | None = None,
) -> str:
    """Format the raw user task and recent conversation history for rewriting.

    Args:
        task: Raw user prompt or task statement.
        recent_messages: Recent conversation messages for context resolution.

    Returns:
        Formatted prompt input string.
    """
    lines = [f"Raw User Task:\n{task.strip()}"]
    if recent_messages:
        lines.append("\nRecent Conversation Messages:")
        for msg in recent_messages[-6:]:
            msg_type = getattr(msg, "type", "message")
            content = getattr(msg, "content", str(msg))
            lines.append(f"[{msg_type}]: {content}")
    return "\n".join(lines)


async def rewrite_task_input(
    task: str,
    recent_messages: list[BaseMessage] | None = None,
) -> str:
    """Rewrite raw user task input into a structured engineering specification.

    Args:
        task: Raw user prompt.
        recent_messages: Recent conversation messages.

    Returns:
        Structured specification adhering to the prompt template.
    """
    if not task or not task.strip():
        return task

    system_prompt = PROMPTS.get("task_rewrite", {}).get("system", "").strip()
    if not system_prompt:
        logger.warning("task_rewrite system prompt not found; using original task")
        return task

    agent = Agent(
        get_model(),
        system_prompt=system_prompt,
    )
    prompt = format_task_rewrite_input(task, recent_messages)
    try:
        result = await run_agent(agent, prompt)
        if isinstance(result, str) and result.strip():
            return result.strip()
        if hasattr(result, "content") and getattr(result, "content"):
            return str(result.content).strip()
        if hasattr(result, "output") and getattr(result, "output"):
            return str(result.output).strip()
        return str(result).strip() if result else task
    except Exception:
        logger.exception("Failed to rewrite user task; falling back to original task")
        return task

