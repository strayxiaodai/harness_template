"""Extract memories from chat history and store them."""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from config.prompts import PROMPTS
from graph.state import AgentState
from llm.providers import get_llm
from llm.retry import call_llm
from rag.config import RagSettings, load_rag_settings
from rag.embeddings import get_embeddings
from rag.schemas import ExtractionResult
from rag.stores.memory import MemoryStore

logger = logging.getLogger(__name__)


def collect_new_messages(
    messages: list[BaseMessage],
    *,
    since_index: int,
    roles: set[str] | None = None,
) -> list[BaseMessage]:
    """Return messages added since the last memory write.

    Args:
        messages: Full message history.
        since_index: Index of first new message.
        roles: Message types to include.

    Returns:
        New messages for extraction.
    """
    allowed = roles or {"human", "ai"}
    return [message for message in messages[since_index:] if message.type in allowed]


def format_messages_for_extraction(messages: list[BaseMessage]) -> str:
    """Format messages for the extraction LLM.

    Args:
        messages: Messages to extract from.

    Returns:
        Formatted prompt text.
    """
    lines = []
    for message in messages:
        lines.append(f"{message.type}: {message.content}")
    return "\n".join(lines)


async def extract_memories(messages: list[BaseMessage]) -> ExtractionResult:
    """Extract durable memories from a message slice.

    Args:
        messages: Messages to extract from.

    Returns:
        Structured extraction result.
    """
    llm = get_llm().with_structured_output(ExtractionResult)
    return await call_llm(
        llm,
        [
            SystemMessage(content=PROMPTS["rag"]["extract"].strip()),
            HumanMessage(content=format_messages_for_extraction(messages)),
        ],
    )


async def run_memory_ingest(
    state: AgentState,
    *,
    memory_store: MemoryStore,
    settings: RagSettings | None = None,
) -> dict[str, object]:
    """Run memory ingest: history → extract → embed → store.

    Args:
        state: Current agent state.
        memory_store: Memory store.
        settings: Optional settings override.

    Returns:
        State updates including memory_cursor.
    """
    cfg = settings or load_rag_settings()
    cursor = state.get("memory_cursor", 0)
    new_messages = collect_new_messages(state["messages"], since_index=cursor)
    if not new_messages:
        return {}

    extracted = await extract_memories(new_messages)
    filtered = [
        memory
        for memory in extracted.memories
        if memory.importance >= cfg.extract.min_importance
    ]
    if not filtered:
        return {"memory_cursor": len(state["messages"])}

    embeddings = get_embeddings(cfg)
    await memory_store.upsert_memories(
        state["thread_id"],
        filtered,
        embeddings,
    )
    memory_store.save(cfg.index_dir)

    logger.info(
        "Stored %d memories for thread %s",
        len(filtered),
        state["thread_id"],
    )
    return {"memory_cursor": len(state["messages"])}


async def extract_memory_candidates(
    state: AgentState,
    *,
    settings: RagSettings | None = None,
) -> list[dict[str, object]]:
    """Extract filtered memory candidates without writing to the store.

    Args:
        state: Current agent state.
        settings: Optional settings override.

    Returns:
        Pending memory candidates with stable ids (m0, m1, ...).
    """
    cfg = settings or load_rag_settings()
    if not cfg.enabled:
        return []
    cursor = state.get("memory_cursor", 0)
    new_messages = collect_new_messages(state["messages"], since_index=cursor)
    if not new_messages:
        return []
    extracted = await extract_memories(new_messages)
    filtered = [
        memory
        for memory in extracted.memories
        if memory.importance >= cfg.extract.min_importance
    ]
    return [
        {
            "id": f"m{index}",
            "content": memory.content,
            "memory_type": memory.memory_type,
            "importance": memory.importance,
        }
        for index, memory in enumerate(filtered)
    ]


async def commit_approved_memories(
    state: AgentState,
    *,
    memory_store: MemoryStore,
    settings: RagSettings | None = None,
) -> dict[str, object]:
    """Upsert approved_memories and advance memory_cursor.

    Args:
        state: Current agent state with approved_memories.
        memory_store: Memory store.
        settings: Optional settings override.

    Returns:
        State updates including memory_cursor and cleared pending/approved.
    """
    from rag.schemas import ExtractedMemory

    cfg = settings or load_rag_settings()
    cursor_update = {"memory_cursor": len(state.get("messages", []))}
    raw = state.get("approved_memories") or []
    if not isinstance(raw, list) or not raw:
        return {
            **cursor_update,
            "pending_memories": [],
            "approved_memories": [],
        }

    memories: list[ExtractedMemory] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        memories.append(
            ExtractedMemory(
                content=content,
                memory_type=item.get("memory_type", "fact"),  # type: ignore[arg-type]
                importance=float(item.get("importance", 0.5)),
            ),
        )
    if not memories:
        return {
            **cursor_update,
            "pending_memories": [],
            "approved_memories": [],
        }

    embeddings = get_embeddings(cfg)
    await memory_store.upsert_memories(
        state["thread_id"],
        memories,
        embeddings,
    )
    memory_store.save(cfg.index_dir)
    return {
        **cursor_update,
        "pending_memories": [],
        "approved_memories": [],
    }
