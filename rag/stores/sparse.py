"""BM25 sparse retriever for static documents."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def bm25_path(index_dir: Path) -> Path:
    """Return the BM25 pickle path."""
    return index_dir / "bm25" / "retriever.pkl"


def build_bm25(documents: list[Document]) -> BM25Retriever:
    """Build a BM25 retriever from documents.

    Args:
        documents: Chunked documents.

    Returns:
        Configured BM25 retriever.
    """
    retriever = BM25Retriever.from_documents(documents)
    retriever.k = 1
    return retriever


def save_bm25(retriever: BM25Retriever, index_dir: Path) -> None:
    """Persist BM25 retriever to disk.

    Args:
        retriever: BM25 retriever to save.
        index_dir: Root RAG data directory.
    """
    target = index_dir / "bm25"
    target.mkdir(parents=True, exist_ok=True)
    path = bm25_path(index_dir)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as handle:
        pickle.dump(retriever, handle)
    tmp.rename(path)
    logger.info("Saved BM25 retriever")


def load_bm25(index_dir: Path) -> BM25Retriever | None:
    """Load BM25 retriever if present.

    Args:
        index_dir: Root RAG data directory.

    Returns:
        BM25 retriever or None if missing.
    """
    path = bm25_path(index_dir)
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        retriever: BM25Retriever = pickle.load(handle)
    return retriever
