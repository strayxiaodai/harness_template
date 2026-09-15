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
PDF_GLOBS = ("**/*.pdf",)


def load_pdf_document(pdf_path: Path) -> Document | None:
    """Load a PDF document using Docling layout parsing with pypdf fallback.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Document containing extracted Markdown or text, or None on failure.
    """
    if not pdf_path.is_file():
        return None

    # Try Docling layout-aware Markdown extraction
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        markdown_text = result.document.export_to_markdown()
        logger.info("Successfully converted %s using Docling", pdf_path)
        return Document(
            page_content=markdown_text,
            metadata={"source": str(pdf_path), "file_type": "pdf", "loader": "docling"},
        )
    except Exception as exc:
        logger.debug("Docling conversion unavailable or failed for %s: %s", pdf_path, exc)

    # Fallback to PyPDF
    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_path))
        pages_text = [
            page.extract_text() for page in reader.pages if page.extract_text()
        ]
        full_text = "\n\n".join(pages_text)
        logger.info("Loaded %s using pypdf fallback (%d pages)", pdf_path, len(reader.pages))
        return Document(
            page_content=full_text,
            metadata={"source": str(pdf_path), "file_type": "pdf", "loader": "pypdf"},
        )
    except Exception as exc:
        logger.warning("Failed to load PDF %s with pypdf fallback: %s", pdf_path, exc)
        return None


def load_documents(source_path: Path) -> list[Document]:
    """Load text and PDF documents from a directory or single file.

    Args:
        source_path: Directory or single file path containing source files.

    Returns:
        Loaded documents.
    """
    documents: list[Document] = []

    if source_path.is_file():
        if source_path.suffix.lower() == ".pdf":
            doc = load_pdf_document(source_path)
            if doc:
                documents.append(doc)
        else:
            try:
                loader = TextLoader(str(source_path), encoding="utf-8")
                documents.extend(loader.load())
            except Exception as exc:
                logger.warning("Failed to load text file %s: %s", source_path, exc)
        return documents

    if source_path.is_dir():
        for glob_pattern in SOURCE_GLOBS:
            loader = DirectoryLoader(
                str(source_path),
                glob=glob_pattern,
                loader_cls=TextLoader,
                show_progress=False,
                silent_errors=True,
            )
            documents.extend(loader.load())

        for pdf_glob in PDF_GLOBS:
            for pdf_file in source_path.glob(pdf_glob):
                doc = load_pdf_document(pdf_file)
                if doc:
                    documents.append(doc)

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
    if file_type in ("md", "pdf"):
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
