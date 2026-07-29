"""Static document ingest pipeline."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import MetadataSettings, RagSettings, load_rag_settings
from rag.embeddings import get_embeddings
from rag.schemas import RagManifest
from rag.stores.sparse import get_es_store, index_documents
from rag.stores.vectorstore import build_vectorstore, save_vectorstore

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
SOURCE_GLOBS = ("**/*.md", "**/*.txt", "**/*.py", "**/*.yaml", "**/*.yml")


def load_documents(source_dir: Path) -> list[Document]:
    """Load text documents from a directory.

    Args:
        source_dir: Directory containing source files.

    Returns:
        Loaded documents.
    """
    documents: list[Document] = []
    for glob_pattern in SOURCE_GLOBS:
        loader = DirectoryLoader(
            str(source_dir),
            glob=glob_pattern,
            loader_cls=TextLoader,
            show_progress=False,
            silent_errors=True,
        )
        documents.extend(loader.load())
    return documents


def chunk_documents(
    documents: list[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split documents into chunks with stable ids.

    Args:
        documents: Source documents.
        chunk_size: Chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        Chunked documents with metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(documents)
    for index, chunk in enumerate(chunks):
        source = chunk.metadata.get("source", "unknown")
        chunk.metadata["chunk_id"] = f"{source}::{index}"
    return chunks


_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
_DOCSTRING_RE = re.compile(r'"""(.+?)"""', re.DOTALL)


def _extract_topics_from_content(content: str, file_type: str) -> list[str]:
    """Extract topic keywords from chunk content using heuristics."""
    topics: list[str] = []
    if file_type == "md":
        headings = _HEADING_RE.findall(content)
        topics.extend(h.strip().lower() for h in headings[:5])
    elif file_type == "py":
        docstrings = _DOCSTRING_RE.findall(content)
        for ds in docstrings[:3]:
            first_line = ds.strip().split("\n")[0].strip().lower()
            if first_line:
                topics.append(first_line)
    return topics


def enrich_metadata(
    chunks: list[Document],
    settings: MetadataSettings,
) -> list[Document]:
    """Enrich document chunks with structured metadata fields.

    Adds file_type, module, and optionally topics to each chunk's metadata.

    Args:
        chunks: Chunked documents with source metadata.
        settings: Metadata extraction settings.

    Returns:
        The same chunks with enriched metadata (mutated in place).
    """
    if not settings.enabled:
        return chunks

    for chunk in chunks:
        source = chunk.metadata.get("source", "")
        source_path = Path(source)

        # file_type from extension
        ext = source_path.suffix.lstrip(".")
        chunk.metadata["file_type"] = ext or "unknown"

        # module from first meaningful directory component
        parts = source_path.parts
        chunk.metadata["module"] = parts[0] if parts else "root"

        # topics from content heuristics
        if settings.extract_topics:
            topics = _extract_topics_from_content(
                chunk.page_content, chunk.metadata["file_type"]
            )
            chunk.metadata["topics"] = topics

    return chunks


def ingest_documents(
    source_dir: Path,
    settings: RagSettings | None = None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RagManifest:
    """Ingest static documents into FAISS and Elasticsearch indexes.

    Args:
        source_dir: Directory containing documents.
        settings: Optional settings override.
        chunk_size: Chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        Manifest describing the built index.
    """
    cfg = settings or load_rag_settings()
    raw_docs = load_documents(source_dir)
    if not raw_docs:
        raise ValueError(f"No documents found under {source_dir}")

    chunks = chunk_documents(
        raw_docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    enrich_metadata(chunks, cfg.metadata)
    embeddings = get_embeddings(cfg)

    vectorstore = build_vectorstore(chunks, embeddings)

    es_store = get_es_store(
        cfg.hybrid.elasticsearch_url,
        cfg.hybrid.elasticsearch_index,
    )
    index_documents(es_store, chunks)

    manifest = RagManifest(
        embedding_provider=cfg.embedding_provider,
        embedding_model=cfg.embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        doc_count=len(chunks),
    )

    cfg.index_dir.mkdir(parents=True, exist_ok=True)
    save_vectorstore(vectorstore, cfg.index_dir, manifest)
    logger.info("Ingested %d chunks from %s", len(chunks), source_dir)
    return manifest
