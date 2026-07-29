"""Elasticsearch sparse retriever for static documents."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchStore

logger = logging.getLogger(__name__)

METADATA_FIELD_MAPPING: dict[str, dict[str, str]] = {
    "file_type": {"type": "keyword"},
    "module": {"type": "keyword"},
    "topics": {"type": "keyword"},
}


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


def build_metadata_filter(
    metadata_hints: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    """Build ES filter clauses from metadata hints.

    Args:
        metadata_hints: Dict of field -> value(s) to filter on.

    Returns:
        List of ES filter clauses or None.
    """
    if not metadata_hints:
        return None
    filters: list[dict[str, Any]] = []
    for field, value in metadata_hints.items():
        if field not in METADATA_FIELD_MAPPING:
            continue
        if isinstance(value, list):
            filters.append({"terms": {f"metadata.{field}": value}})
        else:
            filters.append({"term": {f"metadata.{field}": value}})
    return filters or None


async def search_es(
    store: ElasticsearchStore,
    query: str,
    k: int,
    *,
    metadata_filter: dict[str, Any] | None = None,
) -> list[Document]:
    """Run a BM25 text-match query with optional metadata filtering.

    Args:
        store: ElasticsearchStore instance.
        query: Search query string.
        k: Number of results to return.
        metadata_filter: Optional metadata field filters.

    Returns:
        Ranked document list.
    """
    search_kwargs: dict[str, Any] = {"k": k}

    filters = build_metadata_filter(metadata_filter)
    if filters:
        search_kwargs["filter"] = filters

    retriever = store.as_retriever(search_kwargs=search_kwargs)
    return await retriever.ainvoke(query)
