"""Memorize agent node: commit approved memories after each round."""

from __future__ import annotations

import logging

from graph.state import AgentState
from rag.config import load_rag_settings
from rag.ingest.memory_extract import commit_approved_memories
from rag.service import get_rag_service

logger = logging.getLogger(__name__)


def _clear_memory_lists() -> dict[str, list[dict[str, object]]]:
    """Return empty pending and approved memory lists."""
    return {"pending_memories": [], "approved_memories": []}


def _skip_memorize_updates(state: AgentState) -> dict[str, object]:
    """Return memorize updates when commit cannot run."""
    return {
        "role": "memorize",
        "memory_cursor": len(state.get("messages", [])),
        **_clear_memory_lists(),
    }


async def memorize_agent(state: AgentState) -> dict[str, object]:
    """Commit approved memories from state to the memory store.

    Args:
        state: Current agent state.

    Returns:
        State updates including memory_cursor and cleared memory lists.
    """
    settings = load_rag_settings()
    if not settings.enabled:
        return _skip_memorize_updates(state)

    try:
        service = get_rag_service()
    except RuntimeError:
        logger.debug("RAG service not initialized; skipping memory commit")
        return _skip_memorize_updates(state)

    try:
        updates = await commit_approved_memories(
            state,
            memory_store=service.memory_store,
            settings=settings,
        )
        service.save_memory_store()
        return {"role": "memorize", **updates}
    except Exception as exc:
        logger.warning(
            "Memory commit failed for thread %s; continuing graph without "
            "storing memories: %s",
            state.get("thread_id", ""),
            exc,
            exc_info=True,
        )
        return _skip_memorize_updates(state)
