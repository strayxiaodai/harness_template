"""Reciprocal rank fusion for hybrid retrieval."""

from __future__ import annotations

from langchain_core.documents import Document


def reciprocal_rank_fusion(
    ranked_lists: list[list[Document]],
    *,
    rrf_k: int = 60,
    id_key: str = "chunk_id",
) -> list[Document]:
    """Fuse multiple ranked document lists with reciprocal rank fusion.

    Args:
        ranked_lists: One ranked list per retriever.
        rrf_k: RRF constant (typically 60).
        id_key: Metadata key used to deduplicate documents.

    Returns:
        Documents sorted by fused RRF score (descending).
    """
    scores: dict[str, float] = {}
    by_id: dict[str, Document] = {}

    for results in ranked_lists:
        for rank, doc in enumerate(results):
            doc_id = str(doc.metadata.get(id_key, doc.page_content))
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank + 1)
            by_id[doc_id] = doc

    ordered_ids = sorted(scores, key=scores.get, reverse=True)
    return [by_id[doc_id] for doc_id in ordered_ids]
