"""Static document ingest pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import RagSettings, load_rag_settings
from rag.embeddings import get_embeddings
from rag.schemas import RagManifest
from rag.stores.sparse import build_bm25, save_bm25
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


def ingest_documents(
    source_dir: Path,
    settings: RagSettings | None = None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RagManifest:
    """Ingest static documents into FAISS and BM25 indexes.

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
    embeddings = get_embeddings(cfg)

    vectorstore = build_vectorstore(chunks, embeddings)
    bm25 = build_bm25(chunks)

    manifest = RagManifest(
        embedding_provider=cfg.embedding_provider,
        embedding_model=cfg.embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        doc_count=len(chunks),
    )

    cfg.index_dir.mkdir(parents=True, exist_ok=True)
    save_vectorstore(vectorstore, cfg.index_dir, manifest)
    save_bm25(bm25, cfg.index_dir)
    logger.info("Ingested %d chunks from %s", len(chunks), source_dir)
    return manifest
