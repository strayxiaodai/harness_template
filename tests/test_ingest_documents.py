"""Tests for document loading and ingestion in rag/ingest/documents.py."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from rag.ingest.documents import (
    chunk_documents,
    load_documents,
    load_pdf_document,
)


def test_load_documents_text_directory(tmp_path: Path) -> None:
    """load_documents loads markdown files from directory."""
    doc_file = tmp_path / "guide.md"
    doc_file.write_text("# Title\n\nSome doc content.", encoding="utf-8")

    docs = load_documents(tmp_path)
    assert len(docs) == 1
    assert "Title" in docs[0].page_content


def test_load_documents_single_text_file(tmp_path: Path) -> None:
    """load_documents loads a single text file."""
    doc_file = tmp_path / "notes.txt"
    doc_file.write_text("Meeting notes content.", encoding="utf-8")

    docs = load_documents(doc_file)
    assert len(docs) == 1
    assert docs[0].page_content == "Meeting notes content."


def test_load_pdf_document_pypdf_fallback(tmp_path: Path) -> None:
    """load_pdf_document falls back to pypdf when docling fails or is unavailable."""
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake pdf")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page 1 extracted content"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    # Ensure docling import raises ImportError
    with patch.dict(sys.modules, {"docling": None, "docling.document_converter": None}):
        with patch("pypdf.PdfReader", return_value=mock_reader):
            doc = load_pdf_document(pdf_file)
            assert doc is not None
            assert doc.metadata["loader"] == "pypdf"
            assert "Page 1 extracted content" in doc.page_content


def test_load_pdf_document_docling_success(tmp_path: Path) -> None:
    """load_pdf_document converts PDF to markdown using Docling."""
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake pdf")

    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = "# Header\n\nDocling markdown table"

    mock_converter_cls = MagicMock()
    mock_converter_cls.return_value.convert.return_value = mock_result

    fake_docling = ModuleType("docling")
    fake_converter_mod = ModuleType("docling.document_converter")
    fake_converter_mod.DocumentConverter = mock_converter_cls

    with patch.dict(sys.modules, {
        "docling": fake_docling,
        "docling.document_converter": fake_converter_mod,
    }):
        doc = load_pdf_document(pdf_file)
        assert doc is not None
        assert doc.metadata["loader"] == "docling"
        assert "# Header" in doc.page_content
        assert "Docling markdown table" in doc.page_content


def test_chunk_documents_metadata() -> None:
    """chunk_documents generates chunk_id in metadata."""
    from langchain_core.documents import Document

    docs = [Document(page_content="Header\n" * 100, metadata={"source": "test.md"})]
    chunks = chunk_documents(docs, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert "chunk_id" in chunks[0].metadata
    assert chunks[0].metadata["chunk_id"].startswith("test.md::")
