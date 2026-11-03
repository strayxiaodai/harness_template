"""RAG tools for the executor."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rag.config import load_rag_settings
from rag.service import get_rag_service
from tools.base import harness_tool


class SearchKbInput(BaseModel):
    """Input schema for the knowledge base search tool."""

    query: str = Field(
        min_length=1,
        description="Natural-language search query for static documents.",
    )


@harness_tool("search_knowledge_base", args_schema=SearchKbInput)
async def search_knowledge_base(query: str) -> str:
    """Search indexed documents. Read-only."""
    settings = load_rag_settings()
    if not settings.enabled:
        return "RAG is disabled."
    service = get_rag_service()
    return await service.search_documents_text(query)
