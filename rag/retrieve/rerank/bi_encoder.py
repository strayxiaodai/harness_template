"""Stage-1 bi-encoder reranker using embedding cosine similarity."""

from __future__ import annotations

import logging
import math

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class BiEncoderReranker:
    """Rerank documents with bi-encoder cosine similarity."""

    def __init__(self, embeddings: Embeddings, top_n: int) -> None:
        self._embeddings = embeddings
        self._top_n = top_n

    async def arerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Rerank documents by embedding similarity to the query.

        Args:
            query: Search query.
            docs: Candidate documents.

        Returns:
            Top documents by cosine similarity.
        """
        if not docs:
            return []

        query_vec = await self._embeddings.aembed_query(query)
        doc_vecs = await self._embeddings.aembed_documents(
            [doc.page_content for doc in docs]
        )
        scored = sorted(
            zip(docs, doc_vecs, strict=True),
            key=lambda pair: _cosine(query_vec, pair[1]),
            reverse=True,
        )
        return [doc for doc, _ in scored[: self._top_n]]
