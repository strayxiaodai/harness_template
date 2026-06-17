"""Tests for RAG prompt formatters."""

from __future__ import annotations

from langchain_core.documents import Document

from rag.inject.formatter import format_document_context, format_memory_context


def test_format_memory_context_empty() -> None:
    """Empty memory list renders the empty label."""
    block = format_memory_context([])
    assert "(no relevant memories)" in block


def test_format_document_context_includes_source() -> None:
    """Document formatter includes source metadata."""
    docs = [
        Document(
            page_content="hello",
            metadata={"source": "docs/readme.md"},
        ),
    ]
    text = format_document_context(docs)
    assert "docs/readme.md" in text
    assert "hello" in text
