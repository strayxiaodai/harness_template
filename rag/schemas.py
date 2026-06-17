"""Pydantic schemas for RAG ingest, retrieve, and memory."""

from __future__ import annotations

from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, Field


class ExtractedMemory(BaseModel):
    """One atomic memory extracted from chat history."""

    content: str = Field(min_length=1)
    memory_type: Literal["fact", "preference", "entity", "summary"] = "fact"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    """Structured output from the memory extraction LLM."""

    memories: list[ExtractedMemory] = Field(default_factory=list)
    discard_reason: str | None = None


class RewrittenQueries(BaseModel):
    """Query rewrite output for memory retrieval."""

    primary: str = Field(min_length=1)
    alternates: list[str] = Field(default_factory=list, max_length=2)
    rationale: str | None = None


class RagManifest(BaseModel):
    """Metadata written alongside document indexes at ingest time."""

    embedding_provider: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    doc_count: int


class MemoryContext(BaseModel):
    """Assembled memory context for prompt injection."""

    memory_block: str
    rewritten: RewrittenQueries | None = None
    documents: list[Document] = Field(default_factory=list)
