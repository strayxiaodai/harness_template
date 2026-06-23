"""Postgres + pgvector memory store for extracted chat memories."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.schemas import ExtractedMemory

logger = logging.getLogger(__name__)

_memory_pool: Any | None = None


def set_memory_pool(pool: object | None) -> None:
    """Install a pooled Postgres connection for memory reads and writes."""
    global _memory_pool
    _memory_pool = pool


def _vector_literal(values: list[float]) -> str:
    """Format a float list as a pgvector literal."""
    return "[" + ",".join(str(value) for value in values) + "]"


class PostgresMemoryStore:
    """Thread-scoped memory store backed by pgvector."""

    def __init__(self, *, embedding_dim: int = 1536) -> None:
        self._embedding_dim = embedding_dim

    def save(self, index_dir: Path) -> None:
        """No-op — Postgres is the source of truth."""
        del index_dir

    async def search(
        self,
        thread_id: str,
        query_embedding: list[float],
        *,
        top_k: int = 20,
    ) -> list[Document]:
        """Search memories for a thread using cosine distance.

        Args:
            thread_id: Conversation thread id.
            query_embedding: Query vector.
            top_k: Maximum results.

        Returns:
            Matching memory documents, or empty when pool is unset.
        """
        if _memory_pool is None:
            logger.debug("memory pool not configured; skipping search")
            return []

        sql = """
            SELECT content, memory_type, importance, id::text
            FROM memory_entries
            WHERE thread_id = %s
              AND superseded_by IS NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        async with _memory_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (thread_id, _vector_literal(query_embedding), top_k),
                )
                rows = await cur.fetchall()

        return [
            Document(
                page_content=row[0],
                metadata={
                    "chunk_id": row[3],
                    "thread_id": thread_id,
                    "memory_type": row[1],
                    "importance": float(row[2]),
                },
            )
            for row in rows
        ]

    async def upsert_memories(
        self,
        thread_id: str,
        items: list[ExtractedMemory],
        embeddings: Embeddings,
    ) -> list[str]:
        """Insert extracted memories into Postgres.

        Args:
            thread_id: Conversation thread id.
            items: Extracted memories.
            embeddings: Embedding model.

        Returns:
            List of stored memory ids.
        """
        if not items:
            return []

        if _memory_pool is None:
            logger.debug("memory pool not configured; skipping memory write")
            return []

        texts = [item.content for item in items]
        vectors = await embeddings.aembed_documents(texts)
        stored_ids: list[str] = []

        insert_sql = """
            INSERT INTO memory_entries (
                id, thread_id, content, memory_type, importance, embedding
            )
            VALUES (%s::uuid, %s, %s, %s, %s, %s::vector)
        """

        async with _memory_pool.connection() as conn:
            async with conn.cursor() as cur:
                for item, vector in zip(items, vectors, strict=True):
                    memory_id = str(uuid4())
                    await cur.execute(
                        insert_sql,
                        (
                            memory_id,
                            thread_id,
                            item.content,
                            item.memory_type,
                            item.importance,
                            _vector_literal(vector),
                        ),
                    )
                    stored_ids.append(memory_id)

        return stored_ids
