"""Stage-2 cross-encoder reranker."""

from __future__ import annotations

import asyncio
import logging

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Rerank documents with a cross-encoder model."""

    def __init__(
        self,
        model_name: str,
        top_n: int,
        batch_size: int = 16,
    ) -> None:
        self._model_name = model_name
        self._top_n = top_n
        self._batch_size = batch_size
        self._model: object | None = None

    def _get_model(self) -> object:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    def _predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        model = self._get_model()
        scores = model.predict(  # type: ignore[union-attr]
            pairs,
            batch_size=self._batch_size,
        )
        return [float(score) for score in scores]

    async def arerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Rerank documents with cross-encoder scores.

        Args:
            query: Search query.
            docs: Candidate documents.

        Returns:
            Top documents by cross-encoder score.
        """
        if not docs:
            return []

        pairs = [(query, doc.page_content) for doc in docs]
        scores = await asyncio.to_thread(self._predict, pairs)
        ranked = sorted(
            zip(docs, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [doc for doc, _ in ranked[: self._top_n]]
