# Replace BM25 with Elasticsearch for Sparse Retrieval

**Date:** 2026-07-29
**Scope:** Swap the in-process BM25 sparse retrieval leg with Elasticsearch,
using `langchain-elasticsearch`. FAISS dense retrieval, RRF fusion, reranking,
and memory stores are unchanged.

## Decision Summary

| Aspect | Before | After |
|--------|--------|-------|
| Sparse retriever | `rank-bm25` via `BM25Retriever` (pickle on disk) | Elasticsearch via `langchain-elasticsearch` |
| Dense retriever | FAISS | FAISS (unchanged) |
| Fusion | RRF | RRF (unchanged) |
| Infrastructure | None | Elasticsearch single-node (docker-compose) or external |

## Configuration

New settings on `HybridSettings` (in `rag/config.py`):

| Field | Env var | Default |
|-------|---------|---------|
| `elasticsearch_url` | `ELASTICSEARCH_URL` | `http://localhost:9200` |
| `elasticsearch_index` | `ELASTICSEARCH_INDEX` | `rag_documents` |

Reuse existing `hybrid.retrieve_k` for the number of sparse results.

## File Changes

### `rag/stores/sparse.py` — rewrite

Remove all BM25/pickle code. New module exposes:

```python
def get_es_store(url: str, index_name: str) -> ElasticsearchStore:
    """Create or return an ElasticsearchStore for sparse BM25 retrieval."""

def index_documents(store: ElasticsearchStore, documents: list[Document]) -> None:
    """Bulk-index chunked documents into Elasticsearch."""

async def search_es(store: ElasticsearchStore, query: str, k: int) -> list[Document]:
    """Run a BM25 text-match query and return ranked documents."""
```

### `rag/config.py`

Add `elasticsearch_url` and `elasticsearch_index` fields to `HybridSettings`.
Add corresponding env-var loading in `load_rag_settings()`.

### `rag/retrieve/search.py`

- Replace `bm25: BM25Retriever | None` parameter with
  `es_store: ElasticsearchStore | None` in `search_documents()`.
- Sparse leg calls `search_es(es_store, query, hybrid.retrieve_k)` instead of
  `bm25.ainvoke(query)`.
- RRF fusion logic unchanged.

### `rag/service.py`

- `RagService.__init__` replaces `bm25: BM25Retriever | None` with
  `es_store: ElasticsearchStore | None`.
- `from_settings()` calls `get_es_store()` instead of `load_bm25()`.
- Remove `BM25Retriever` import, add `ElasticsearchStore` import.

### `rag/ingest/documents.py`

- `ingest_documents()` calls `get_es_store()` + `index_documents()` instead of
  `build_bm25()` / `save_bm25()`.
- Remove `rank-bm25` / sparse pickle imports.

### `tests/test_rag_service.py`

- `_build_indexes()` indexes into ES instead of building BM25.
- Tests use a mock or testcontainer ES instance.
- Assertion logic unchanged (still checks document results from hybrid search).

### `docker-compose.yml`

Add `elasticsearch` service:

```yaml
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.15.0
  environment:
    - discovery.type=single-node
    - xpack.security.enabled=false
    - ES_JAVA_OPTS=-Xms512m -Xmx512m
  ports:
    - "9200:9200"
```

### `.env.example`

Add:

```
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=rag_documents
```

### `pyproject.toml`

- Remove `rank-bm25` from dependencies.
- Add `langchain-elasticsearch`.

### Documentation

- `docs/IMPLEMENTATION.md` — update RAG table row from "FAISS + BM25" to
  "FAISS + Elasticsearch", update config table with new env vars.
- `docs/ARCHITECTURE.md` — update index description.

## Out of Scope

- Replacing FAISS with ES for dense retrieval.
- Memory stores (FAISS / pgvector) — unchanged.
- Reranking pipeline — unchanged.
- Query rewrite — unchanged.

## Risks

- **ES availability:** If ES is down, sparse leg returns empty; dense-only
  fallback still works (existing behavior when BM25 was missing).
- **Test isolation:** Tests need either a mock ES or testcontainers; CI must
  have access to an ES image.
