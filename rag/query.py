"""CLI query tool for testing dense, sparse, fusion, and rerank search modes, plus optional LLM answer generation."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Literal

from langchain_core.documents import Document

from rag.config import load_rag_settings
from rag.embeddings import get_embeddings
from rag.inject.formatter import format_document_context
from rag.retrieve.fusion import reciprocal_rank_fusion
from rag.retrieve.metadata_filter import extract_metadata_hints
from rag.retrieve.rerank.pipeline import build_reranker
from rag.stores.sparse import get_es_store, search_es
from rag.stores.vectorstore import load_vectorstore

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# 1. DENSE SEARCH (FAISS / Vector Embeddings)
async def run_dense_search(query: str, top_k: int = 5) -> list[Document]:
    """Execute dense vector similarity search using FAISS."""
    cfg = load_rag_settings()
    embeddings = get_embeddings(cfg)
    if not cfg.index_dir.exists():
        raise RuntimeError(f"FAISS index directory {cfg.index_dir} does not exist.")
    vectorstore = load_vectorstore(cfg.index_dir, embeddings)
    return await vectorstore.asimilarity_search(query, k=top_k)


# 2. SPARSE SEARCH (Elasticsearch / BM25 Keywords)
async def run_sparse_search(query: str, top_k: int = 5) -> list[Document]:
    """Execute sparse BM25 keyword search using Elasticsearch."""
    cfg = load_rag_settings()
    if not cfg.hybrid.enabled:
        raise RuntimeError("Hybrid/Elasticsearch search is disabled in settings.")
    es_store = get_es_store(
        cfg.hybrid.elasticsearch_url, cfg.hybrid.elasticsearch_index
    )
    metadata_filter = (
        extract_metadata_hints(query) if cfg.metadata.enabled else None
    )
    return await search_es(
        es_store, query, top_k, metadata_filter=metadata_filter
    )


# 3. FUSION SEARCH (Reciprocal Rank Fusion - RRF)
async def run_fusion_search(query: str, top_k: int = 5) -> list[Document]:
    """Execute hybrid search combining Dense and Sparse results via RRF."""
    cfg = load_rag_settings()
    dense_docs = await run_dense_search(query, cfg.hybrid.retrieve_k)
    sparse_docs = await run_sparse_search(query, cfg.hybrid.retrieve_k)
    fused = reciprocal_rank_fusion(
        [sparse_docs, dense_docs], rrf_k=cfg.hybrid.rrf_k
    )
    return fused[:top_k]


# 4. FUSION & RERANK SEARCH (Hybrid RRF + Cross-Encoder Reranker)
async def run_rerank_search(query: str, top_k: int = 5) -> list[Document]:
    """Execute full RAG pipeline: Hybrid RRF Fusion + Cross-Encoder Rerank."""
    cfg = load_rag_settings()
    embeddings = get_embeddings(cfg)
    fused_docs = await run_fusion_search(query, cfg.hybrid.fusion_top_n)
    reranker = build_reranker(embeddings, cfg.rerank)
    if reranker is not None:
        reranked = await reranker.arerank(query, fused_docs)
        return reranked[:top_k]
    return fused_docs[:top_k]


async def generate_llm_answer(query: str, docs: list[Document]) -> str:
    """Inject retrieved document context into LLM to generate the final answer."""
    from llm.providers import get_llm

    formatted_context = format_document_context(docs)
    prompt = f"""You are a technical documentation assistant. Answer the user's question based strictly on the retrieved document context below.

{formatted_context}

Question: {query}
Answer:"""

    llm = get_llm()
    response = await asyncio.to_thread(llm.invoke, prompt)
    return getattr(response, "content", str(response))


def print_results(mode_name: str, docs: list[Document]) -> None:
    """Pretty-print document search results."""
    print(f"\n==========================================")
    print(f" MODE: {mode_name.upper()} (Found {len(docs)} results)")
    print(f"==========================================")
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        print(f"\n[{i}] Source: {source}")
        snippet = doc.page_content.replace("\n", " ").strip()
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        print(f"    Content: {snippet}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query RAG system with selectable search modes and optional LLM answer generation."
    )
    parser.add_argument(
        "-q", "--query",
        type=str,
        default="FortiOS administration",
        help="Search query text",
    )
    parser.add_argument(
        "-m", "--mode",
        type=str,
        choices=["dense", "sparse", "fusion", "rerank", "all"],
        default="all",
        help="Search mode: dense | sparse | fusion | rerank | all",
    )
    parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=3,
        help="Number of top results per mode",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Feed the retrieved context into the configured LLM to generate an answer",
    )

    args = parser.parse_args()
    print(f"🔍 Query: '{args.query}' (top_k={args.top_k})\n")

    selected_docs: list[Document] = []

    if args.mode in ("dense", "all"):
        docs = await run_dense_search(args.query, args.top_k)
        print_results("Dense Search (FAISS / Vector)", docs)
        selected_docs = docs

    if args.mode in ("sparse", "all"):
        docs = await run_sparse_search(args.query, args.top_k)
        print_results("Sparse Search (Elasticsearch / BM25)", docs)
        selected_docs = docs

    if args.mode in ("fusion", "all"):
        docs = await run_fusion_search(args.query, args.top_k)
        print_results("Fusion Search (RRF Hybrid)", docs)
        selected_docs = docs

    if args.mode in ("rerank", "all"):
        docs = await run_rerank_search(args.query, args.top_k)
        print_results("Fusion + Rerank Search (Cross-Encoder)", docs)
        selected_docs = docs

    if args.generate:
        print("\n==========================================")
        print("🤖 LLM GENERATED ANSWER")
        print("==========================================")
        try:
            answer = await generate_llm_answer(args.query, selected_docs)
            print(f"\n{answer}\n")
        except Exception as exc:
            print(f"\n❌ Error generating LLM answer: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
