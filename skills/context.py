"""Serialize harness thread state for skill distillation."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import BaseMessage


def _format_messages(messages: list[BaseMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        content = message.content
        if not isinstance(content, str):
            content = json.dumps(content, default=str)
        lines.append(f"{message.type}: {content}")
    return "\n".join(lines) if lines else "(no messages)"


def format_thread_context(values: dict[str, Any]) -> str:
    """Build a readable snapshot of a completed harness thread.

    Args:
        values: LangGraph checkpoint values for the thread.

    Returns:
        Plain-text context for the distillation LLM.
    """
    sections: list[str] = []

    task = values.get("task")
    if task:
        sections.append(f"## Task\n{task}")

    plan = values.get("plan") or []
    if plan:
        plan_lines = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(plan))
        sections.append(f"## Plan\n{plan_lines}")

    execution = values.get("execution")
    if execution:
        sections.append(
            "## Execution summary\n"
            f"{json.dumps(execution, indent=2, default=str)}",
        )

    tool_calls = values.get("tool_calls") or []
    if tool_calls:
        sections.append(
            "## Tool calls\n"
            f"{json.dumps(tool_calls, indent=2, default=str)}",
        )

    learning = values.get("learning")
    if learning:
        sections.append(
            "## Learning\n"
            f"{json.dumps(learning, indent=2, default=str)}",
        )

    result = values.get("result")
    if result:
        sections.append(f"## Final result\n{result}")

    messages = values.get("messages") or []
    if messages:
        sections.append(f"## Message trace\n{_format_messages(messages)}")

    rounds = values.get("rounds", 0)
    max_rounds = values.get("max_rounds", 0)
    approved = values.get("approved", False)
    sections.append(
        "## Run metadata\n"
        f"rounds: {rounds}/{max_rounds}\n"
        f"approved: {approved}\n"
        f"thread_id: {values.get('thread_id', '')}",
    )

    return "\n\n".join(sections)
