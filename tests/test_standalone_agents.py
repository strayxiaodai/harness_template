"""Tests for standalone PydanticAI extraction and rewriting agents."""

import pytest
from langchain_core.messages import HumanMessage

from rag.ingest.memory_extract import extract_memories
from rag.retrieve.rewrite import rewrite_for_memory
from rag.schemas import ExtractionResult, RewrittenQueries
from skills.distill import _draft_skill
from skills.schemas import SkillDraft


@pytest.mark.asyncio
async def test_rewrite_for_memory_with_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "test")
    res = await rewrite_for_memory("test query", [HumanMessage(content="hello")])
    assert isinstance(res, RewrittenQueries)


@pytest.mark.asyncio
async def test_extract_memories_with_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "test")
    res = await extract_memories([HumanMessage(content="user prefers pytest")])
    assert isinstance(res, ExtractionResult)


@pytest.mark.asyncio
async def test_draft_skill_with_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "test")
    res = await _draft_skill(context="thread details")
    assert isinstance(res, SkillDraft)
