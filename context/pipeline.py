"""Assemble memory context for prompt injection."""

from __future__ import annotations

import logging

from graph.state import AgentState
from rag.config import load_rag_settings
from rag.inject.formatter import format_memory_context
from rag.retrieve.rewrite import rewrite_for_memory
from rag.retrieve.search import search_memories
from rag.schemas import MemoryContext, RewrittenQueries
from rag.service import get_rag_service

logger = logging.getLogger(__name__)


async def assemble_context(state: AgentState) -> MemoryContext:
    """Rewrite query, retrieve memories, rerank, and format for injection.

    Args:
        state: Current agent state.

    Returns:
        Memory context for prompt injection.
    """
    settings = load_rag_settings()
    if not settings.enabled or not settings.inject.planner:
        return MemoryContext(memory_block="(no relevant memories)")

    if state.get("memory_context_round") == state["rounds"]:
        block = state.get("memory_context", "(no relevant memories)")
        return MemoryContext(memory_block=block)

    try:
        service = get_rag_service()
    except RuntimeError:
        logger.debug("RAG service not initialized; skipping memory recall")
        return MemoryContext(memory_block="(no relevant memories)")

    recent = state["messages"][-settings.rewrite.max_recent_messages :]

    rewritten: RewrittenQueries
    if settings.rewrite.enabled and (state["task"] or recent):
        rewritten = await rewrite_for_memory(state["task"], recent)
    else:
        rewritten = RewrittenQueries(primary=state["task"])

    documents = await search_memories(
        state["thread_id"],
        rewritten,
        memory_store=service.memory_store,
        embeddings=service.embeddings,
        settings=settings,
        reranker=service.reranker,
    )

    block = format_memory_context(documents)
    return MemoryContext(
        memory_block=block,
        rewritten=rewritten,
        documents=documents,
    )
