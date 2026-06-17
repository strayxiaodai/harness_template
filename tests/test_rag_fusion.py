"""Tests for reciprocal rank fusion."""

from __future__ import annotations

from langchain_core.documents import Document

from rag.retrieve.fusion import reciprocal_rank_fusion


def test_rrf_promotes_documents_in_both_lists() -> None:
    """Documents ranked in both lists should score higher."""
    doc_a = Document(page_content="a", metadata={"chunk_id": "a"})
    doc_b = Document(page_content="b", metadata={"chunk_id": "b"})
    doc_c = Document(page_content="c", metadata={"chunk_id": "c"})

    fused = reciprocal_rank_fusion(
        [
            [doc_a, doc_b],
            [doc_b, doc_c],
        ],
        rrf_k=60,
    )

    assert [doc.metadata["chunk_id"] for doc in fused] == ["b", "a", "c"]
