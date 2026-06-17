"""Two-stage rerank pipeline."""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.config import RerankSettings
from rag.retrieve.rerank.bi_encoder import BiEncoderReranker
from rag.retrieve.rerank.cross_encoder import CrossEncoderReranker

logger = logging.getLogger(__name__)


class TwoStageReranker:
    """Chain bi-encoder then cross-encoder reranking."""

    def __init__(
        self,
        stage1: BiEncoderReranker,
        stage2: CrossEncoderReranker | None,
    ) -> None:
        self._stage1 = stage1
        self._stage2 = stage2

    async def arerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Run two-stage reranking.

        Args:
            query: Search query.
            docs: Candidate documents.

        Returns:
            Reranked documents.
        """
        narrowed = await self._stage1.arerank(query, docs)
        if self._stage2 is None:
            return narrowed
        try:
            return await self._stage2.arerank(query, narrowed)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; skipping cross-encoder"
            )
            return narrowed
        except Exception as exc:
            logger.error("Cross-encoder rerank failed: %s", exc)
            return narrowed


def build_reranker(
    embeddings: Embeddings,
    settings: RerankSettings,
) -> TwoStageReranker | None:
    """Build reranker from settings.

    Args:
        embeddings: Embedding model for stage 1.
        settings: Rerank configuration.

    Returns:
        TwoStageReranker or None when reranking is disabled.
    """
    if not settings.enabled:
        return None

    stage1 = BiEncoderReranker(embeddings, settings.stage1_top_n)
    stage2 = CrossEncoderReranker(
        settings.cross_encoder_model,
        settings.stage2_top_n,
        batch_size=settings.batch_size,
    )
    return TwoStageReranker(stage1, stage2)
