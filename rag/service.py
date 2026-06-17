"""RAG service singleton."""

from __future__ import annotations

import logging

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.config import RagSettings, load_rag_settings
from rag.embeddings import get_embeddings
from rag.inject.formatter import format_document_context
from rag.retrieve.rerank.pipeline import TwoStageReranker, build_reranker
from rag.retrieve.search import search_documents
from rag.stores.memory import MemoryStore
from rag.stores.sparse import load_bm25
from rag.stores.vectorstore import load_vectorstore, validate_manifest

logger = logging.getLogger(__name__)

_rag_service: RagService | None = None


class RagService:
    """Singleton RAG service for document retrieval and memory storage."""

    def __init__(
        self,
        settings: RagSettings,
        embeddings: Embeddings,
        vectorstore: FAISS | None,
        bm25: BM25Retriever | None,
        memory_store: MemoryStore,
        reranker: TwoStageReranker | None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._vectorstore = vectorstore
        self._bm25 = bm25
        self._memory_store = memory_store
        self._reranker = reranker

    @property
    def settings(self) -> RagSettings:
        """Return service settings."""
        return self._settings

    @property
    def memory_store(self) -> MemoryStore:
        """Return the memory store."""
        return self._memory_store

    @property
    def embeddings(self) -> Embeddings:
        """Return the embedding model."""
        return self._embeddings

    @property
    def reranker(self) -> TwoStageReranker | None:
        """Return the two-stage reranker."""
        return self._reranker

    @classmethod
    def from_settings(cls, settings: RagSettings | None = None) -> RagService:
        """Build a service from settings.

        Args:
            settings: Optional settings override.

        Returns:
            Configured RagService.
        """
        cfg = settings or load_rag_settings()
        embeddings = get_embeddings(cfg)

        vectorstore: FAISS | None = None
        bm25: BM25Retriever | None = None
        if cfg.index_dir.exists():
            try:
                validate_manifest(
                    cfg.index_dir,
                    embedding_provider=cfg.embedding_provider,
                    embedding_model=cfg.embedding_model,
                )
                vectorstore = load_vectorstore(cfg.index_dir, embeddings)
                bm25 = load_bm25(cfg.index_dir)
            except RuntimeError as exc:
                logger.warning("RAG document index not ready: %s", exc)

        memory_store = MemoryStore.load(cfg.index_dir, embeddings)
        reranker = build_reranker(embeddings, cfg.rerank)

        return cls(cfg, embeddings, vectorstore, bm25, memory_store, reranker)

    async def search_documents(self, query: str) -> list[Document]:
        """Search static documents.

        Args:
            query: Search query.

        Returns:
            Ranked document chunks.
        """
        return await search_documents(
            query,
            vectorstore=self._vectorstore,
            bm25=self._bm25,
            embeddings=self._embeddings,
            settings=self._settings,
            reranker=self._reranker,
        )

    async def search_documents_text(self, query: str) -> str:
        """Search documents and return formatted text.

        Args:
            query: Search query.

        Returns:
            Formatted retrieval result for tools.
        """
        docs = await self.search_documents(query)
        return format_document_context(docs)

    def save_memory_store(self) -> None:
        """Persist memory store to disk."""
        self._memory_store.save(self._settings.index_dir)


def init_rag_service(settings: RagSettings | None = None) -> RagService | None:
    """Initialize the global RAG service.

    Args:
        settings: Optional settings override.

    Returns:
        RagService or None when RAG is disabled.
    """
    global _rag_service
    cfg = settings or load_rag_settings()
    if not cfg.enabled:
        _rag_service = None
        return None
    _rag_service = RagService.from_settings(cfg)
    return _rag_service


def get_rag_service() -> RagService:
    """Return the initialized RAG service.

    Returns:
        RagService instance.

    Raises:
        RuntimeError: If RAG has not been initialized.
    """
    if _rag_service is None:
        raise RuntimeError("RAG service not initialized; call init_rag_service()")
    return _rag_service
