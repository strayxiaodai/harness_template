"""FAISS-backed memory store for extracted chat memories."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.schemas import ExtractedMemory

logger = logging.getLogger(__name__)


def memory_dir(index_dir: Path) -> Path:
    """Return the memory FAISS directory."""
    return index_dir / "memory"


class MemoryStore:
    """Thread-scoped memory store backed by FAISS."""

    def __init__(self, store: FAISS | None = None) -> None:
        self._store = store

    @classmethod
    def load(cls, index_dir: Path, embeddings: Embeddings) -> MemoryStore:
        """Load memory store from disk or return an empty store.

        Args:
            index_dir: Root RAG data directory.
            embeddings: Embedding model.

        Returns:
            MemoryStore instance.
        """
        target = memory_dir(index_dir)
        if not (target / "index.faiss").is_file():
            return cls(None)
        store = FAISS.load_local(
            str(target),
            embeddings,
            allow_dangerous_deserialization=True,
        )
        return cls(store)

    def save(self, index_dir: Path) -> None:
        """Persist memory store to disk.

        Args:
            index_dir: Root RAG data directory.
        """
        if self._store is None:
            return
        target = memory_dir(index_dir)
        target.mkdir(parents=True, exist_ok=True)
        self._store.save_local(str(target))
        logger.info("Saved memory store")

    async def search(
        self,
        thread_id: str,
        query_embedding: list[float],
        *,
        top_k: int = 20,
    ) -> list[Document]:
        """Search memories for a thread.

        Args:
            thread_id: Conversation thread id.
            query_embedding: Query vector.
            top_k: Maximum results.

        Returns:
            Matching memory documents.
        """
        if self._store is None:
            return []

        docs = await self._store.asimilarity_search_by_vector(
            query_embedding,
            k=top_k * 3,
        )
        filtered = [
            doc
            for doc in docs
            if doc.metadata.get("thread_id") == thread_id
        ]
        return filtered[:top_k]

    async def upsert_memories(
        self,
        thread_id: str,
        items: list[ExtractedMemory],
        embeddings: Embeddings,
    ) -> list[str]:
        """Add extracted memories to the store.

        Args:
            thread_id: Conversation thread id.
            items: Extracted memories.
            embeddings: Embedding model.
        Returns:
            List of stored memory ids.
        """
        if not items:
            return []

        stored_ids: list[str] = []
        new_docs: list[Document] = []
        for item in items:
            memory_id = f"{thread_id}:{len(stored_ids)}:{hash(item.content)}"
            new_docs.append(
                Document(
                    page_content=item.content,
                    metadata={
                        "chunk_id": memory_id,
                        "thread_id": thread_id,
                        "memory_type": item.memory_type,
                        "importance": item.importance,
                    },
                )
            )
            stored_ids.append(memory_id)

        if not new_docs:
            return []

        if self._store is None:
            self._store = FAISS.from_documents(new_docs, embeddings)
        else:
            self._store.add_documents(new_docs)

        return stored_ids
