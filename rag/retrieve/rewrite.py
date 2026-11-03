"""LLM query rewrite for memory retrieval."""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage
from pydantic_ai import Agent

from config.prompts import PROMPTS
from llm.providers import get_model
from llm.retry import run_agent
from rag.schemas import RewrittenQueries

logger = logging.getLogger(__name__)


def format_rewrite_input(
    task: str,
    recent_messages: list[BaseMessage],
) -> str:
    """Format task and recent messages for query rewrite.

    Args:
        task: Current user task.
        recent_messages: Recent conversation messages.

    Returns:
        Formatted prompt text.
    """
    lines = [f"Task: {task}", "", "Recent messages:"]
    for message in recent_messages:
        lines.append(f"{message.type}: {message.content}")
    return "\n".join(lines)


async def rewrite_for_memory(
    task: str,
    recent_messages: list[BaseMessage],
) -> RewrittenQueries:
    """Rewrite a task into memory search queries.

    Args:
        task: Current user task.
        recent_messages: Recent conversation messages.

    Returns:
        Primary and alternate search queries.
    """
    agent = Agent(
        get_model(),
        output_type=RewrittenQueries,
        system_prompt=PROMPTS["rag"]["rewrite"].strip(),
    )
    prompt = format_rewrite_input(task, recent_messages)
    return await run_agent(agent, prompt)
