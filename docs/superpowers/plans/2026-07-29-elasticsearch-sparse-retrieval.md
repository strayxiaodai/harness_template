# Elasticsearch Sparse Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the in-process BM25 sparse retrieval leg with Elasticsearch, using `langchain-elasticsearch`.

**Architecture:** `rag/stores/sparse.py` is rewritten to wrap `ElasticsearchStore`. Config gains ES URL/index fields. `search_documents()` swaps the BM25 call for an ES query. FAISS dense, RRF fusion, reranking, and memory stores are untouched.

**Tech Stack:** `langchain-elasticsearch`, Elasticsearch 8.x, `pytest` with `unittest.mock`

## Global Constraints

- Python ≥ 3.12
- Follow existing code style (type hints, Google docstrings, f-strings)
- All new public functions need type hints and docstrings
- `rag/stores/sparse.py` is the only store file that changes
- Do not modify memory stores, reranking, or query rewrite

---

### Task 1: Add `langchain-elasticsearch` dependency and remove `rank-bm25`

**Files:**
- Modify: `pyproject.toml:5-20`

**Interfaces:**
- Consumes: nothing
- Produces: `langchain-elasticsearch` available for import

- [ ] **Step 1: Update pyproject.toml**

```toml
[project]
name = "harness-template"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langchain-core",
    "langchain-community",
    "langchain-text-splitters",
    "langchain-openai",
    "langchain-ollama",
    "langchain-elasticsearch",
    "faiss-cpu",
    "tenacity",
    "pyyaml",
    "python-dotenv",
    "pydantic",
    "langgraph",
    "fastapi",
    "uvicorn[standard]",
]
```

Remove `"rank-bm25"`, add `"langchain-elasticsearch"`.

- [ ] **Step 2: Install updated dependencies**

Run: `pip install -e ".[dev]"`
Expected: installs successfully, `langchain_elasticsearch` importable

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: replace rank-bm25 with langchain-elasticsearch"
```

---

### Task 2: Add Elasticsearch config fields

**Files:**
- Modify: `rag/config.py:39-46` (HybridSettings)
- Modify: `rag/config.py:162-175` (load_rag_settings hybrid block)
- Modify: `.env.example`

**Interfaces:**
- Consumes: nothing
- Produces: `HybridSettings.elasticsearch_url: str`, `HybridSettings.elasticsearch_index: str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rag_config_es.py`:

```python
"""Tests for Elasticsearch config fields."""

from __future__ import annotations

from rag.config import HybridSettings, load_rag_settings


def test_hybrid_settings_has_es_defaults() -> None:
    """HybridSettings exposes ES URL and index with defaults."""
    h = HybridSettings()
    assert h.elasticsearch_url == "http://localhost:9200"
    assert h.elasticsearch_index == "rag_documents"


def test_load_rag_settings_picks_up_es_env(monkeypatch: object) -> None:
    """load_rag_settings reads ELASTICSEARCH_URL and ELASTICSEARCH_INDEX."""
    import pytest

    monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "my_index")
    settings = load_rag_settings()
    assert settings.hybrid.elasticsearch_url == "http://es:9200"
    assert settings.hybrid.elasticsearch_index == "my_index"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rag_config_es.py -v`
Expected: FAIL — `HybridSettings` has no `elasticsearch_url` attribute

- [ ] **Step 3: Add fields to HybridSettings**

In `rag/config.py`, update the `HybridSettings` dataclass:

```python
@dataclass(frozen=True)
class HybridSettings:
    """Hybrid Elasticsearch + dense retrieval settings."""

    enabled: bool = True
    retrieve_k: int = 30
    rrf_k: int = 60
    fusion_top_n: int = 50
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "rag_documents"
```

- [ ] **Step 4: Wire env vars in load_rag_settings()**

In the `hybrid=HybridSettings(...)` block inside `load_rag_settings()`, add:

```python
        hybrid=HybridSettings(
            enabled=_env_bool(
                "RAG_HYBRID_ENABLED",
                bool(hybrid_raw.get("enabled", True)),
            ),
            retrieve_k=_env_int(
                "RAG_RETRIEVE_K",
                int(hybrid_raw.get("retrieve_k", 30)),
            ),
            rrf_k=_env_int("RAG_RRF_K", int(hybrid_raw.get("rrf_k", 60))),
            fusion_top_n=_env_int(
                "RAG_FUSION_TOP_N",
                int(hybrid_raw.get("fusion_top_n", 50)),
            ),
            elasticsearch_url=os.getenv(
                "ELASTICSEARCH_URL",
                str(hybrid_raw.get("elasticsearch_url", "http://localhost:9200")),
            ),
            elasticsearch_index=os.getenv(
                "ELASTICSEARCH_INDEX",
                str(hybrid_raw.get("elasticsearch_index", "rag_documents")),
            ),
        ),
```

- [ ] **Step 5: Update .env.example**

Append to `.env.example`:

```
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=rag_documents
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_rag_config_es.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add rag/config.py .env.example tests/test_rag_config_es.py
git commit -m "feat(rag): add Elasticsearch URL and index config fields"
```

---

### Task 3: Rewrite `rag/stores/sparse.py` for Elasticsearch

**Files:**
- Modify: `rag/stores/sparse.py` (full rewrite)
- Create: `tests/test_es_sparse.py`

**Interfaces:**
- Consumes: `HybridSettings.elasticsearch_url`, `HybridSettings.elasticsearch_index`
- Produces: `get_es_store(url, index_name) -> ElasticsearchStore`, `index_documents(store, documents) -> None`, `search_es(store, query, k) -> list[Document]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_es_sparse.py`:

```python
"""Tests for Elasticsearch sparse retrieval store."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from rag.stores.sparse import get_es_store, index_documents, search_es


def test_get_es_store_returns_store() -> None:
    """get_es_store creates an ElasticsearchStore."""
    with patch("rag.stores.sparse.ElasticsearchStore") as mock_cls:
        mock_cls.return_value = MagicMock()
        store = get_es_store("http://localhost:9200", "test_index")
        mock_cls.assert_called_once_with(
            es_url="http://localhost:9200",
            index_name="test_index",
            strategy=mock_cls.BM25RetrievalStrategy.return_value
                if hasattr(mock_cls, "BM25RetrievalStrategy")
                else mock_cls.call_args.kwargs.get("strategy"),
        )
        assert store is not None


def test_index_documents_calls_add_documents() -> None:
    """index_documents bulk-indexes into the store."""
    store = MagicMock()
    docs = [Document(page_content="hello", metadata={"chunk_id": "a::0"})]
    index_documents(store, docs)
    store.add_documents.assert_called_once_with(docs)


@pytest.mark.asyncio
async def test_search_es_returns_documents() -> None:
    """search_es returns documents from ES BM25 query."""
    store = MagicMock()
    expected = [Document(page_content="result", metadata={})]
    store.as_retriever.return_value = AsyncMock()
    store.as_retriever.return_value.ainvoke = AsyncMock(return_value=expected)
    results = await search_es(store, "test query", k=5)
    assert results == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_es_sparse.py -v`
Expected: FAIL — `get_es_store`, `index_documents`, `search_es` not found

- [ ] **Step 3: Rewrite rag/stores/sparse.py**

```python
"""Elasticsearch sparse retriever for static documents."""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchStore

logger = logging.getLogger(__name__)


def get_es_store(url: str, index_name: str) -> ElasticsearchStore:
    """Create an ElasticsearchStore for sparse BM25 retrieval.

    Args:
        url: Elasticsearch connection URL.
        index_name: Target index name.

    Returns:
        Configured ElasticsearchStore.
    """
    return ElasticsearchStore(
        es_url=url,
        index_name=index_name,
        strategy=ElasticsearchStore.BM25RetrievalStrategy(),
    )


def index_documents(store: ElasticsearchStore, documents: list[Document]) -> None:
    """Bulk-index chunked documents into Elasticsearch.

    Args:
        store: ElasticsearchStore instance.
        documents: Chunked documents to index.
    """
    store.add_documents(documents)
    logger.info("Indexed %d documents into Elasticsearch", len(documents))


async def search_es(
    store: ElasticsearchStore, query: str, k: int
) -> list[Document]:
    """Run a BM25 text-match query and return ranked documents.

    Args:
        store: ElasticsearchStore instance.
        query: Search query string.
        k: Number of results to return.

    Returns:
        Ranked document list.
    """
    retriever = store.as_retriever(search_kwargs={"k": k})
    return await retriever.ainvoke(query)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_es_sparse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rag/stores/sparse.py tests/test_es_sparse.py
git commit -m "feat(rag): rewrite sparse.py to use Elasticsearch"
```

---

### Task 4: Update `search_documents()` to use ES store

**Files:**
- Modify: `rag/retrieve/search.py:1-70`
- Modify: `tests/test_rag_service.py` (update `test_search_documents_direct`)

**Interfaces:**
- Consumes: `get_es_store()`, `search_es()` from `rag.stores.sparse`
- Produces: `search_documents(query, *, vectorstore, es_store, embeddings, settings, reranker) -> list[Document]`

- [ ] **Step 1: Update search_documents() signature and body**

In `rag/retrieve/search.py`:

```python
"""Hybrid document and memory search."""

from __future__ import annotations

import logging

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_elasticsearch import ElasticsearchStore

from rag.config import HybridSettings, MemoryRetrieveSettings, RagSettings
from rag.retrieve.fusion import reciprocal_rank_fusion
from rag.retrieve.rerank.pipeline import TwoStageReranker
from rag.schemas import RewrittenQueries
from rag.stores.memory import MemoryStore
from rag.stores.sparse import search_es

logger = logging.getLogger(__name__)


async def search_documents(
    query: str,
    *,
    vectorstore: FAISS | None,
    es_store: ElasticsearchStore | None,
    embeddings: Embeddings,
    settings: RagSettings,
    reranker: TwoStageReranker | None,
) -> list[Document]:
    """Run hybrid document retrieval with optional reranking.

    Args:
        query: Search query.
        vectorstore: FAISS store.
        es_store: Elasticsearch store for sparse retrieval.
        embeddings: Embedding model.
        settings: RAG settings.
        reranker: Optional two-stage reranker.

    Returns:
        Ranked document chunks.
    """
    hybrid = settings.hybrid
    ranked_lists: list[list[Document]] = []

    if hybrid.enabled and es_store is not None:
        sparse = await search_es(es_store, query, hybrid.retrieve_k)
        ranked_lists.append(sparse)

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
```

Leave `search_memories()` unchanged.

- [ ] **Step 2: Update test_search_documents_direct**

In `tests/test_rag_service.py`, update the `test_search_documents_direct` test:

```python
@pytest.mark.asyncio
async def test_search_documents_direct(
    rag_settings: RagSettings,
    sample_docs: list[Document],
) -> None:
    """search_documents helper fuses ES and dense results."""
    from unittest.mock import AsyncMock, MagicMock

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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_rag_service.py::test_search_documents_direct -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add rag/retrieve/search.py tests/test_rag_service.py
git commit -m "feat(rag): update search_documents to use Elasticsearch store"
```

---

### Task 5: Update `RagService` and ingest pipeline

**Files:**
- Modify: `rag/service.py`
- Modify: `rag/ingest/documents.py`
- Modify: `tests/test_rag_service.py` (update `_build_indexes`, `test_hybrid_search_returns_documents`)

**Interfaces:**
- Consumes: `get_es_store()`, `index_documents()`, `search_es()` from `rag.stores.sparse`; `HybridSettings.elasticsearch_url`, `HybridSettings.elasticsearch_index`
- Produces: `RagService.__init__(..., es_store: ElasticsearchStore | None, ...)`

- [ ] **Step 1: Update rag/service.py**

Replace BM25 references with ES store:

```python
"""RAG service singleton."""

from __future__ import annotations

import logging

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_elasticsearch import ElasticsearchStore

from rag.config import RagSettings, load_rag_settings
from rag.embeddings import get_embeddings
from rag.inject.formatter import format_document_context
from rag.retrieve.rerank.pipeline import TwoStageReranker, build_reranker
from rag.retrieve.search import search_documents
from rag.stores.memory_factory import MemoryStoreBackend, load_memory_store
from rag.stores.sparse import get_es_store
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
        es_store: ElasticsearchStore | None,
        memory_store: MemoryStoreBackend,
        reranker: TwoStageReranker | None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._vectorstore = vectorstore
        self._es_store = es_store
        self._memory_store = memory_store
        self._reranker = reranker

    @property
    def settings(self) -> RagSettings:
        """Return service settings."""
        return self._settings

    @property
    def memory_store(self) -> MemoryStoreBackend:
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
        es_store: ElasticsearchStore | None = None
        if cfg.index_dir.exists():
            try:
                validate_manifest(
                    cfg.index_dir,
                    embedding_provider=cfg.embedding_provider,
                    embedding_model=cfg.embedding_model,
                )
                vectorstore = load_vectorstore(cfg.index_dir, embeddings)
            except RuntimeError as exc:
                logger.warning("RAG document index not ready: %s", exc)

        if cfg.hybrid.enabled:
            try:
                es_store = get_es_store(
                    cfg.hybrid.elasticsearch_url,
                    cfg.hybrid.elasticsearch_index,
                )
            except Exception as exc:
                logger.warning("Elasticsearch not available: %s", exc)

        memory_store = load_memory_store(cfg, embeddings)
        reranker = build_reranker(embeddings, cfg.rerank)

        return cls(cfg, embeddings, vectorstore, es_store, memory_store, reranker)

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
            es_store=self._es_store,
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
```

- [ ] **Step 2: Update rag/ingest/documents.py**

Replace BM25 ingest with ES indexing:

```python
"""Static document ingest pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import RagSettings, load_rag_settings
from rag.embeddings import get_embeddings
from rag.schemas import RagManifest
from rag.stores.sparse import get_es_store, index_documents
from rag.stores.vectorstore import build_vectorstore, save_vectorstore

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
SOURCE_GLOBS = ("**/*.md", "**/*.txt", "**/*.py", "**/*.yaml", "**/*.yml")


def load_documents(source_dir: Path) -> list[Document]:
    """Load text documents from a directory.

    Args:
        source_dir: Directory containing source files.

    Returns:
        Loaded documents.
    """
    documents: list[Document] = []
    for glob_pattern in SOURCE_GLOBS:
        loader = DirectoryLoader(
            str(source_dir),
            glob=glob_pattern,
            loader_cls=TextLoader,
            show_progress=False,
            silent_errors=True,
        )
        documents.extend(loader.load())
    return documents


def chunk_documents(
    documents: list[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split documents into chunks with stable ids.

    Args:
        documents: Source documents.
        chunk_size: Chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        Chunked documents with metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(documents)
    for index, chunk in enumerate(chunks):
        source = chunk.metadata.get("source", "unknown")
        chunk.metadata["chunk_id"] = f"{source}::{index}"
    return chunks


def ingest_documents(
    source_dir: Path,
    settings: RagSettings | None = None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RagManifest:
    """Ingest static documents into FAISS and Elasticsearch indexes.

    Args:
        source_dir: Directory containing documents.
        settings: Optional settings override.
        chunk_size: Chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        Manifest describing the built index.
    """
    cfg = settings or load_rag_settings()
    raw_docs = load_documents(source_dir)
    if not raw_docs:
        raise ValueError(f"No documents found under {source_dir}")

    chunks = chunk_documents(
        raw_docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    embeddings = get_embeddings(cfg)

    vectorstore = build_vectorstore(chunks, embeddings)

    es_store = get_es_store(
        cfg.hybrid.elasticsearch_url,
        cfg.hybrid.elasticsearch_index,
    )
    index_documents(es_store, chunks)

    manifest = RagManifest(
        embedding_provider=cfg.embedding_provider,
        embedding_model=cfg.embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        doc_count=len(chunks),
    )

    cfg.index_dir.mkdir(parents=True, exist_ok=True)
    save_vectorstore(vectorstore, cfg.index_dir, manifest)
    logger.info("Ingested %d chunks from %s", len(chunks), source_dir)
    return manifest
```

- [ ] **Step 3: Update tests/test_rag_service.py**

Remove BM25 imports, update `_build_indexes` and `test_hybrid_search_returns_documents`:

```python
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
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_rag_service.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add rag/service.py rag/ingest/documents.py tests/test_rag_service.py
git commit -m "feat(rag): wire Elasticsearch into RagService and ingest pipeline"
```

---

### Task 6: Update documentation and docker-compose

**Files:**
- Modify: `docs/IMPLEMENTATION.md` (RAG table, config table)
- Modify: `docs/ARCHITECTURE.md` (index description)
- Modify: `rag/stores/__init__.py` (docstring)

**Interfaces:**
- Consumes: nothing
- Produces: updated docs

- [ ] **Step 1: Update docs/IMPLEMENTATION.md**

Change the RAG table row:

```
| Documents | FAISS + Elasticsearch | unchanged |
```

Add to the RAG configuration table:

```
| `ELASTICSEARCH_URL` | Elasticsearch connection | `http://localhost:9200` |
| `ELASTICSEARCH_INDEX` | ES index name | `rag_documents` |
```

- [ ] **Step 2: Update docs/ARCHITECTURE.md**

Change:

```
| Document RAG index | FAISS + Elasticsearch | — |
```

- [ ] **Step 3: Update rag/stores/__init__.py**

```python
"""Vector, Elasticsearch, and memory stores for RAG."""
```

- [ ] **Step 4: Commit**

```bash
git add docs/IMPLEMENTATION.md docs/ARCHITECTURE.md rag/stores/__init__.py
git commit -m "docs: update RAG references from BM25 to Elasticsearch"
```

---

### Task 7: Clean up old BM25 artifacts

**Files:**
- Delete: `data/rag/bm25/` directory (if present on disk)

**Interfaces:**
- Consumes: nothing
- Produces: nothing

- [ ] **Step 1: Remove stale BM25 pickle directory**

```bash
rm -rf data/rag/bm25/
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS, no remaining BM25 references in imports

- [ ] **Step 3: Final commit**

```bash
git commit --allow-empty -m "chore: remove stale BM25 pickle data"
```
