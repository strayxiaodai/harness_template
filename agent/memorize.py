"""Memorize agent node: ingest chat memories after each round."""

from __future__ import annotations

import logging

from graph.state import AgentState
from rag.config import load_rag_settings
from rag.ingest.memory_extract import run_memory_ingest
from rag.service import get_rag_service

logger = logging.getLogger(__name__)


async def memorize_agent(state: AgentState) -> dict[str, object]:
    """Extract and store new memories from chat history.

    Args:
        state: Current agent state.

    Returns:
        State updates including memory_cursor.
    """
    settings = load_rag_settings()
    if not settings.enabled:
        return {"role": "memorize"}

    try:
        service = get_rag_service()
    except RuntimeError:
        logger.debug("RAG service not initialized; skipping memory ingest")
        return {"role": "memorize"}

    updates = await run_memory_ingest(
        state,
        memory_store=service.memory_store,
        settings=settings,
    )
    service.save_memory_store()
    return {"role": "memorize", **updates}
