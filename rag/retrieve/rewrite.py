"""LLM query rewrite for memory retrieval."""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from config.prompts import PROMPTS
from llm.providers import get_llm
from llm.retry import call_llm
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
    llm = get_llm().with_structured_output(RewrittenQueries)
    return await call_llm(
        llm,
        [
            SystemMessage(content=PROMPTS["rag"]["rewrite"].strip()),
            HumanMessage(content=format_rewrite_input(task, recent_messages)),
        ],
    )
