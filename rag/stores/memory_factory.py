"""Memory store protocol and factory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.config import RagSettings
from rag.schemas import ExtractedMemory
from rag.stores.memory import MemoryStore as FaissMemoryStore

logger = logging.getLogger(__name__)


class MemoryStoreBackend(Protocol):
    """Protocol for thread-scoped conversational memory."""

    async def search(
        self,
        thread_id: str,
        query_embedding: list[float],
        *,
        top_k: int = 20,
    ) -> list[Document]:
        """Search memories for a thread."""

    async def upsert_memories(
        self,
        thread_id: str,
        items: list[ExtractedMemory],
        embeddings: Embeddings,
    ) -> list[str]:
        """Store extracted memories."""

    def save(self, index_dir: Path) -> None:
        """Persist store state (no-op for Postgres)."""


def load_memory_store(
    settings: RagSettings,
    embeddings: Embeddings,
) -> MemoryStoreBackend:
    """Load the configured memory store backend.

    Args:
        settings: RAG settings.
        embeddings: Embedding model.

    Returns:
        FAISS or Postgres memory store.
    """
    if settings.memory_store.backend == "postgres":
        from rag.stores.memory_pg import PostgresMemoryStore

        if not settings.memory_store.database_url:
            logger.warning(
                "RAG_MEMORY_BACKEND=postgres but DATABASE_URL unset; "
                "falling back to FAISS"
            )
            return FaissMemoryStore.load(settings.index_dir, embeddings)

        return PostgresMemoryStore(
            embedding_dim=settings.memory_store.embedding_dim,
        )

    return FaissMemoryStore.load(settings.index_dir, embeddings)
