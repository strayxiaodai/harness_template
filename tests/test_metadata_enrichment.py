"""Tests for metadata enrichment and query-time filtering."""

from __future__ import annotations

from langchain_core.documents import Document

from rag.config import MetadataSettings
from rag.ingest.documents import enrich_metadata
from rag.retrieve.metadata_filter import extract_metadata_hints
from rag.stores.sparse import build_metadata_filter


class TestEnrichMetadata:
    """Tests for enrich_metadata()."""

    def test_extracts_file_type_and_module(self) -> None:
        chunks = [
            Document(
                page_content="hello world",
                metadata={"source": "rag/ingest/documents.py"},
            )
        ]
        settings = MetadataSettings(enabled=True, extract_topics=False)
        enrich_metadata(chunks, settings)

        assert chunks[0].metadata["file_type"] == "py"
        assert chunks[0].metadata["module"] == "rag"

    def test_extracts_topics_from_markdown(self) -> None:
        content = "# Getting Started\n\nSome text\n\n## Installation\n"
        chunks = [
            Document(page_content=content, metadata={"source": "docs/guide.md"})
        ]
        settings = MetadataSettings(enabled=True, extract_topics=True)
        enrich_metadata(chunks, settings)

        assert "getting started" in chunks[0].metadata["topics"]
        assert "installation" in chunks[0].metadata["topics"]

    def test_extracts_topics_from_python_docstrings(self) -> None:
        content = '"""Load configuration from disk."""\n\ndef load():\n    pass\n'
        chunks = [
            Document(page_content=content, metadata={"source": "rag/config.py"})
        ]
        settings = MetadataSettings(enabled=True, extract_topics=True)
        enrich_metadata(chunks, settings)

        assert "load configuration from disk." in chunks[0].metadata["topics"]

    def test_disabled_skips_enrichment(self) -> None:
        chunks = [
            Document(page_content="x", metadata={"source": "foo/bar.md"})
        ]
        settings = MetadataSettings(enabled=False)
        enrich_metadata(chunks, settings)

        assert "file_type" not in chunks[0].metadata


class TestExtractMetadataHints:
    """Tests for extract_metadata_hints()."""

    def test_detects_module_keyword(self) -> None:
        hints = extract_metadata_hints("how does the agent work?")
        assert hints is not None
        assert hints["module"] == "agent"

    def test_detects_file_type(self) -> None:
        hints = extract_metadata_hints("show me the yaml config")
        assert hints is not None
        assert hints["file_type"] == "yaml"

    def test_returns_none_for_generic_query(self) -> None:
        hints = extract_metadata_hints("what is the meaning of life")
        assert hints is None


class TestBuildMetadataFilter:
    """Tests for build_metadata_filter()."""

    def test_single_term_filter(self) -> None:
        filters = build_metadata_filter({"module": "rag"})
        assert filters == [{"term": {"metadata.module": "rag"}}]

    def test_list_terms_filter(self) -> None:
        filters = build_metadata_filter({"topics": ["config", "setup"]})
        assert filters == [{"terms": {"metadata.topics": ["config", "setup"]}}]

    def test_none_for_empty(self) -> None:
        assert build_metadata_filter(None) is None
        assert build_metadata_filter({}) is None

    def test_ignores_unknown_fields(self) -> None:
        assert build_metadata_filter({"unknown_field": "val"}) is None
