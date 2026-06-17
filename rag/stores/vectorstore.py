"""FAISS dense vector store for static documents."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.schemas import RagManifest

logger = logging.getLogger(__name__)


def faiss_dir(index_dir: Path) -> Path:
    """Return the FAISS index directory."""
    return index_dir / "faiss"


def manifest_path(index_dir: Path) -> Path:
    """Return the manifest file path."""
    return index_dir / "manifest.json"


def build_vectorstore(
    documents: list[Document],
    embeddings: Embeddings,
) -> FAISS:
    """Build a FAISS index from documents.

    Args:
        documents: Chunked documents with metadata.
        embeddings: Embedding model.

    Returns:
        A FAISS vector store.
    """
    return FAISS.from_documents(documents, embeddings)


def save_vectorstore(
    store: FAISS,
    index_dir: Path,
    manifest: RagManifest,
) -> None:
    """Persist FAISS index and manifest atomically.

    Args:
        store: FAISS store to save.
        index_dir: Root RAG data directory.
        manifest: Index metadata.
    """
    target = faiss_dir(index_dir)
    tmp = index_dir / "faiss.tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    store.save_local(str(tmp))

    if target.exists():
        for child in target.iterdir():
            child.unlink()
    else:
        target.mkdir(parents=True, exist_ok=True)

    for child in tmp.iterdir():
        child.rename(target / child.name)
    tmp.rmdir()

    manifest_path(index_dir).write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("Saved FAISS index with %d documents", manifest.doc_count)


def load_vectorstore(index_dir: Path, embeddings: Embeddings) -> FAISS | None:
    """Load a FAISS index if present.

    Args:
        index_dir: Root RAG data directory.
        embeddings: Embedding model for queries.

    Returns:
        FAISS store or None if index is missing.
    """
    target = faiss_dir(index_dir)
    if not (target / "index.faiss").is_file():
        return None
    return FAISS.load_local(
        str(target),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def load_manifest(index_dir: Path) -> RagManifest | None:
    """Load index manifest if present."""
    path = manifest_path(index_dir)
    if not path.is_file():
        return None
    return RagManifest.model_validate_json(path.read_text(encoding="utf-8"))


def validate_manifest(
    index_dir: Path,
    *,
    embedding_provider: str,
    embedding_model: str,
) -> None:
    """Validate manifest matches runtime embedding configuration.

    Args:
        index_dir: Root RAG data directory.
        embedding_provider: Expected provider name.
        embedding_model: Expected model name.

    Raises:
        RuntimeError: If manifest is missing or mismatched.
    """
    manifest = load_manifest(index_dir)
    if manifest is None:
        raise RuntimeError(f"RAG manifest missing under {index_dir}")
    if manifest.embedding_provider != embedding_provider:
        raise RuntimeError(
            "RAG embedding provider mismatch: "
            f"index={manifest.embedding_provider}, "
            f"runtime={embedding_provider}"
        )
    if manifest.embedding_model != embedding_model:
        raise RuntimeError(
            "RAG embedding model mismatch: "
            f"index={manifest.embedding_model}, "
            f"runtime={embedding_model}"
        )
