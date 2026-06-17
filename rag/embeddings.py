"""Embedding provider factory for RAG."""

from __future__ import annotations

import os
from typing import Any

from rag.config import RagSettings, load_rag_settings


def get_embeddings(settings: RagSettings | None = None) -> Any:
    """Return an embeddings model based on RAG settings.

    Args:
        settings: Optional settings override. Defaults to loaded config.

    Returns:
        A LangChain ``Embeddings`` instance.

    Raises:
        ValueError: If the embedding provider is unsupported.
    """
    cfg = settings or load_rag_settings()
    provider = cfg.embedding_provider.lower()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=cfg.embedding_model)

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=cfg.embedding_model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")
