"""RAG subsystem: ingest, retrieve, rerank, and inject."""

from rag.service import RagService, get_rag_service, init_rag_service

__all__ = ["RagService", "get_rag_service", "init_rag_service"]
