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
