"""Tests for the RAG service and hybrid retrieval."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_community.embeddings import FakeEmbeddings
from langchain_core.documents import Document

from rag.config import RagSettings, RerankSettings
from rag.retrieve.rerank.pipeline import build_reranker
from rag.retrieve.search import search_documents
from rag.schemas import ExtractedMemory, RagManifest
from rag.service import RagService, init_rag_service
from rag.stores.memory import MemoryStore
from rag.stores.vectorstore import build_vectorstore, save_vectorstore


@pytest.fixture
def rag_settings(tmp_path: Path) -> RagSettings:
    """Build test RAG settings with rerank disabled."""
    return RagSettings(
        enabled=True,
        index_dir=tmp_path / "rag",
        embedding_provider="openai",
        embedding_model="fake",
        rerank=RerankSettings(enabled=False),
    )


@pytest.fixture
def sample_docs() -> list[Document]:
    """Return sample documents for retrieval tests."""
    return [
        Document(
            page_content="Python asyncio patterns for web servers",
            metadata={"chunk_id": "a::0", "source": "a.md"},
        ),
        Document(
            page_content="LangGraph checkpointing with Postgres",
            metadata={"chunk_id": "b::0", "source": "b.md"},
        ),
    ]


def _build_indexes(
    settings: RagSettings,
    docs: list[Document],
    embeddings: FakeEmbeddings,
) -> tuple[object, MagicMock]:
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore = build_vectorstore(docs, embeddings)
    manifest = RagManifest(
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        chunk_size=512,
        chunk_overlap=64,
        doc_count=len(docs),
    )
    save_vectorstore(vectorstore, settings.index_dir, manifest)

    mock_es = MagicMock()
    mock_retriever = AsyncMock()
    mock_retriever.ainvoke = AsyncMock(return_value=docs)
    mock_es.as_retriever.return_value = mock_retriever
    return vectorstore, mock_es


@pytest.mark.asyncio
async def test_hybrid_search_returns_documents(
    rag_settings: RagSettings,
    sample_docs: list[Document],
) -> None:
    """Hybrid search returns ranked documents from built indexes."""
    embeddings = FakeEmbeddings(size=32)
    vectorstore, mock_es = _build_indexes(rag_settings, sample_docs, embeddings)
    service = RagService(
        rag_settings,
        embeddings,
        vectorstore,
        mock_es,
        MemoryStore(),
        build_reranker(embeddings, rag_settings.rerank),
    )

    docs = await service.search_documents("LangGraph Postgres")
    assert docs
    assert any("LangGraph" in doc.page_content for doc in docs)


@pytest.mark.asyncio
async def test_memory_store_filters_by_thread(
    rag_settings: RagSettings,
) -> None:
    """Memory store only returns entries for the requested thread."""
    embeddings = FakeEmbeddings(size=32)
    store = MemoryStore()
    await store.upsert_memories(
        "thread-a",
        [ExtractedMemory(content="User prefers pytest", memory_type="preference")],
        embeddings,
    )
    await store.upsert_memories(
        "thread-b",
        [ExtractedMemory(content="User prefers unittest", memory_type="preference")],
        embeddings,
    )

    vector = await embeddings.aembed_query("testing preference")
    hits = await store.search("thread-a", vector, top_k=5)
    assert len(hits) == 1
    assert "pytest" in hits[0].page_content


def test_init_rag_service_disabled() -> None:
    """Disabled RAG returns None from init."""
    service = init_rag_service(RagSettings(enabled=False))
    assert service is None


@pytest.mark.asyncio
async def test_search_documents_direct(
    rag_settings: RagSettings,
    sample_docs: list[Document],
) -> None:
    """search_documents helper fuses ES and dense results."""
    embeddings = FakeEmbeddings(size=32)
    vectorstore = build_vectorstore(sample_docs, embeddings)

    mock_es = MagicMock()
    mock_retriever = AsyncMock()
    mock_retriever.ainvoke = AsyncMock(return_value=sample_docs)
    mock_es.as_retriever.return_value = mock_retriever

    docs = await search_documents(
        "asyncio",
        vectorstore=vectorstore,
        es_store=mock_es,
        embeddings=embeddings,
        settings=rag_settings,
        reranker=None,
    )
    assert docs
