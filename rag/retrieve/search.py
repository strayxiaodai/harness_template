"""Hybrid document and memory search."""

from __future__ import annotations

import logging

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.config import HybridSettings, MemoryRetrieveSettings, RagSettings
from rag.retrieve.fusion import reciprocal_rank_fusion
from rag.retrieve.rerank.pipeline import TwoStageReranker
from rag.schemas import RewrittenQueries
from rag.stores.memory import MemoryStore

logger = logging.getLogger(__name__)


async def search_documents(
    query: str,
    *,
    vectorstore: FAISS | None,
    bm25: BM25Retriever | None,
    embeddings: Embeddings,
    settings: RagSettings,
    reranker: TwoStageReranker | None,
) -> list[Document]:
    """Run hybrid document retrieval with optional reranking.

    Args:
        query: Search query.
        vectorstore: FAISS store.
        bm25: BM25 retriever.
        embeddings: Embedding model.
        settings: RAG settings.
        reranker: Optional two-stage reranker.

    Returns:
        Ranked document chunks.
    """
    hybrid = settings.hybrid
    ranked_lists: list[list[Document]] = []

    if hybrid.enabled and bm25 is not None:
        bm25.k = hybrid.retrieve_k
        sparse = await bm25.ainvoke(query)
        ranked_lists.append(list(sparse))

    if vectorstore is not None:
        dense = await vectorstore.asimilarity_search(query, k=hybrid.retrieve_k)
        ranked_lists.append(dense)

    if not ranked_lists:
        return []

    if len(ranked_lists) == 1:
        fused = ranked_lists[0][: hybrid.fusion_top_n]
    else:
        fused = reciprocal_rank_fusion(
            ranked_lists,
            rrf_k=hybrid.rrf_k,
        )[: hybrid.fusion_top_n]

    if reranker is not None:
        fused = await reranker.arerank(query, fused)

    return fused[: settings.top_k]


async def search_memories(
    thread_id: str,
    queries: RewrittenQueries,
    *,
    memory_store: MemoryStore,
    embeddings: Embeddings,
    settings: RagSettings,
    reranker: TwoStageReranker | None,
) -> list[Document]:
    """Search and rerank memories for a thread.

    Args:
        thread_id: Conversation thread id.
        queries: Rewritten search queries.
        memory_store: Memory store.
        embeddings: Embedding model.
        settings: RAG settings.
        reranker: Optional two-stage reranker.

    Returns:
        Ranked memory documents.
    """
    mem_settings = settings.memory
    seen: set[str] = set()
    candidates: list[Document] = []

    for query in [queries.primary, *queries.alternates]:
        vector = await embeddings.aembed_query(query)
        hits = await memory_store.search(
            thread_id,
            vector,
            top_k=mem_settings.retrieve_k,
        )
        for hit in hits:
            chunk_id = str(hit.metadata.get("chunk_id", hit.page_content))
            if chunk_id not in seen:
                seen.add(chunk_id)
                candidates.append(hit)

    candidates = candidates[: mem_settings.fusion_top_n]
    if reranker is not None and candidates:
        candidates = await reranker.arerank(queries.primary, candidates)

    return candidates[: settings.top_k]
