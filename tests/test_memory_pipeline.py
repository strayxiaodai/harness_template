"""Tests for memory extract, recall, inject, and memorize agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_community.embeddings import FakeEmbeddings
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.schemas import PlanResult
from rag.config import InjectSettings, RagSettings, RewriteSettings
from rag.ingest import memory_extract as memory_extract_module
from rag.schemas import (
    ExtractedMemory,
    ExtractionResult,
    MemoryContext,
    RewrittenQueries,
)
from rag.stores.memory import MemoryStore


def _state(**overrides: object) -> dict[str, Any]:
    """Build a minimal AgentState dict."""
    base: dict[str, Any] = {
        "thread_id": "test-thread",
        "task": "Write unit tests",
        "messages": [],
        "plan": [],
        "rounds": 0,
        "max_rounds": 3,
        "role": "planner",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_run_memory_ingest_skips_when_no_new_messages(
    tmp_path: Path,
) -> None:
    """Ingest returns nothing when the cursor already caught up."""
    settings = RagSettings(
        enabled=True,
        index_dir=tmp_path / "rag",  # type: ignore[operator]
    )
    state = _state(
        messages=[HumanMessage(content="hello")],
        memory_cursor=1,
    )

    updates = await memory_extract_module.run_memory_ingest(
        state,
        memory_store=MemoryStore(),
        settings=settings,
    )

    assert updates == {}


@pytest.mark.asyncio
async def test_run_memory_ingest_extracts_and_stores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Extract step stores memories and advances memory_cursor."""
    settings = RagSettings(
        enabled=True,
        index_dir=tmp_path / "rag",  # type: ignore[operator]
        embedding_provider="openai",
        embedding_model="fake",
    )
    state = _state(
        messages=[
            HumanMessage(content="I prefer pytest for testing"),
            AIMessage(content="Noted."),
        ],
        memory_cursor=0,
    )
    extracted = ExtractionResult(
        memories=[
            ExtractedMemory(
                content="User prefers pytest for testing",
                memory_type="preference",
                importance=0.9,
            ),
        ],
    )
    monkeypatch.setattr(
        memory_extract_module,
        "extract_memories",
        AsyncMock(return_value=extracted),
    )
    monkeypatch.setattr(
        memory_extract_module,
        "get_embeddings",
        lambda _cfg=None: FakeEmbeddings(size=32),
    )

    store = MemoryStore()
    updates = await memory_extract_module.run_memory_ingest(
        state,
        memory_store=store,
        settings=settings,
    )

    assert updates["memory_cursor"] == 2
    vector = await FakeEmbeddings(size=32).aembed_query("pytest")
    hits = await store.search("test-thread", vector, top_k=5)
    assert len(hits) == 1
    assert "pytest" in hits[0].page_content


@pytest.mark.asyncio
async def test_assemble_context_runs_rewrite_recall_inject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recall pipeline rewrites the query and formats memories."""
    import context.pipeline as context_module

    mock_service = MagicMock()
    mock_service.memory_store = MemoryStore()
    mock_service.embeddings = FakeEmbeddings(size=32)
    mock_service.reranker = None

    monkeypatch.setattr(
        context_module,
        "load_rag_settings",
        lambda: RagSettings(
            enabled=True,
            inject=InjectSettings(planner=True),
            rewrite=RewriteSettings(enabled=True),
        ),
    )
    monkeypatch.setattr(context_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(
        context_module,
        "rewrite_for_memory",
        AsyncMock(
            return_value=RewrittenQueries(
                primary="testing framework preference",
                alternates=["pytest preference"],
            ),
        ),
    )
    monkeypatch.setattr(
        context_module,
        "search_memories",
        AsyncMock(
            return_value=[
                Document(
                    page_content="User prefers pytest",
                    metadata={"memory_type": "preference"},
                ),
            ],
        ),
    )

    ctx = await context_module.assemble_context(_state())

    assert "pytest" in ctx.memory_block
    assert ctx.rewritten is not None
    assert ctx.rewritten.primary == "testing framework preference"
    context_module.rewrite_for_memory.assert_awaited_once()
    context_module.search_memories.assert_awaited_once()


@pytest.mark.asyncio
async def test_assemble_context_reuses_cached_block_same_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same round reuses memory_context without calling rewrite."""
    import context.pipeline as context_module

    monkeypatch.setattr(
        context_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True, inject=InjectSettings(planner=True)),
    )
    rewrite = AsyncMock()
    monkeypatch.setattr(context_module, "rewrite_for_memory", rewrite)

    state = _state(
        rounds=1,
        memory_context_round=1,
        memory_context="Relevant memories from prior conversations:\n- cached",
    )

    ctx = await context_module.assemble_context(state)

    assert "cached" in ctx.memory_block
    rewrite.assert_not_awaited()


@pytest.mark.asyncio
async def test_planner_injects_memory_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planner prepends assembled memory context to the human prompt."""
    from app.agents import planner as planner_module

    memory_block = (
        "Relevant memories from prior conversations:\n"
        "- [preference] User prefers pytest"
    )
    monkeypatch.setattr(
        planner_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True, inject=InjectSettings(planner=True)),
    )
    monkeypatch.setattr(
        planner_module,
        "assemble_context",
        AsyncMock(
            return_value=MemoryContext(memory_block=memory_block),
        ),
    )

    fake_llm = MagicMock()
    structured = MagicMock()
    fake_llm.with_structured_output.return_value = structured
    monkeypatch.setattr(planner_module, "get_llm", lambda: fake_llm)

    captured: list[Any] = []
    plan = PlanResult(steps=["write tests"], rationale="coverage matters")

    async def fake_call_llm(_runnable: Any, messages: list[Any]) -> PlanResult:
        captured.extend(messages)
        return plan

    monkeypatch.setattr(planner_module, "call_llm", fake_call_llm)

    result = await planner_module.planner_agent(_state())

    human_messages = [m for m in captured if isinstance(m, HumanMessage)]
    assert len(human_messages) == 1
    assert "User prefers pytest" in human_messages[0].content
    assert result["memory_context"] == memory_block
    assert result["memory_context_round"] == 0


@pytest.mark.asyncio
async def test_executor_injects_memory_context_from_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executor prepends cached memory_context to its prompt."""
    from app.agents import executor as executor_module
    from app.graph.schemas import ExecutorResult

    monkeypatch.setattr(
        executor_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True, inject=InjectSettings(executor=True)),
    )
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = MagicMock()
    fake_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(executor_module, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(executor_module, "get_executor_tools", lambda: [])
    monkeypatch.setattr(executor_module, "write_audit_event", AsyncMock())

    captured: list[Any] = []
    execution = ExecutorResult(summary="done")

    async def fake_call_llm(_runnable: Any, messages: list[Any]) -> Any:
        if not captured:
            captured.extend(messages)
            return AIMessage(content="no tools")
        return execution

    monkeypatch.setattr(executor_module, "call_llm", fake_call_llm)

    await executor_module.executor_agent(
        _state(
            role="executor",
            plan=["step one"],
            memory_context="Relevant memories:\n- [fact] Use pytest",
        ),
    )

    human_messages = [m for m in captured if isinstance(m, HumanMessage)]
    assert len(human_messages) == 1
    assert "Use pytest" in human_messages[0].content


@pytest.mark.asyncio
async def test_memorize_commits_approved_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent import memorize as memorize_module

    mock_service = MagicMock()
    mock_service.memory_store = MemoryStore()
    mock_service.save_memory_store = MagicMock()
    commit = AsyncMock(
        return_value={
            "memory_cursor": 2,
            "pending_memories": [],
            "approved_memories": [],
        },
    )
    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(memorize_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(memorize_module, "commit_approved_memories", commit)

    state = _state(
        messages=[HumanMessage(content="hi"), AIMessage(content="ok")],
        approved_memories=[
            {
                "content": "User said hi",
                "memory_type": "fact",
                "importance": 0.7,
            },
        ],
        pending_memories=[{"id": "m0", "content": "x"}],
    )
    result = await memorize_module.memorize_agent(state)
    assert result["role"] == "memorize"
    assert result["memory_cursor"] == 2
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_memorize_skips_store_when_approved_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent import memorize as memorize_module

    mock_service = MagicMock()
    mock_service.save_memory_store = MagicMock()
    commit = AsyncMock(
        return_value={
            "memory_cursor": 1,
            "pending_memories": [],
            "approved_memories": [],
        },
    )
    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(memorize_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(memorize_module, "commit_approved_memories", commit)

    result = await memorize_module.memorize_agent(
        _state(messages=[HumanMessage(content="x")], approved_memories=[]),
    )
    assert result["memory_cursor"] == 1
    mock_service.save_memory_store.assert_called_once()


@pytest.mark.asyncio
async def test_memorize_agent_runs_memory_ingest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Memorize node delegates to commit_approved_memories and saves the store."""
    from agent import memorize as memorize_module

    mock_service = MagicMock()
    mock_service.memory_store = MemoryStore()
    mock_service.save_memory_store = MagicMock()

    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(memorize_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(
        memorize_module,
        "commit_approved_memories",
        AsyncMock(return_value={"memory_cursor": 3}),
    )

    result = await memorize_module.memorize_agent(_state(messages=[]))

    assert result["role"] == "memorize"
    assert result["memory_cursor"] == 3
    memorize_module.commit_approved_memories.assert_awaited_once()
    mock_service.save_memory_store.assert_called_once()


@pytest.mark.asyncio
async def test_memorize_agent_continues_when_ingest_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Memorize node must not block the graph when embedding/storage fails."""
    from agent import memorize as memorize_module
    from langchain_core.messages import AIMessage

    mock_service = MagicMock()
    mock_service.memory_store = MemoryStore()
    mock_service.save_memory_store = MagicMock()

    monkeypatch.setattr(
        memorize_module,
        "load_rag_settings",
        lambda: RagSettings(enabled=True),
    )
    monkeypatch.setattr(memorize_module, "get_rag_service", lambda: mock_service)
    monkeypatch.setattr(
        memorize_module,
        "commit_approved_memories",
        AsyncMock(side_effect=RuntimeError("embedding failed: NaN")),
    )

    messages = [AIMessage(content="done")]
    result = await memorize_module.memorize_agent(_state(messages=messages))

    assert result["role"] == "memorize"
    assert result["memory_cursor"] == len(messages)
    assert result["pending_memories"] == []
    assert result["approved_memories"] == []
    mock_service.save_memory_store.assert_not_called()


@pytest.mark.asyncio
async def test_extract_memory_candidates_does_not_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Extract candidates assigns ids but does not write to the store."""
    settings = RagSettings(
        enabled=True,
        index_dir=tmp_path / "rag",  # type: ignore[operator]
    )
    state = _state(
        messages=[HumanMessage(content="I prefer pytest")],
        memory_cursor=0,
    )
    monkeypatch.setattr(
        memory_extract_module,
        "extract_memories",
        AsyncMock(
            return_value=ExtractionResult(
                memories=[
                    ExtractedMemory(
                        content="User prefers pytest",
                        memory_type="preference",
                        importance=0.9,
                    ),
                ],
            ),
        ),
    )
    store = MemoryStore()
    candidates = await memory_extract_module.extract_memory_candidates(
        state,
        settings=settings,
    )
    assert candidates == [
        {
            "id": "m0",
            "content": "User prefers pytest",
            "memory_type": "preference",
            "importance": 0.9,
        },
    ]
    vector = await FakeEmbeddings(size=32).aembed_query("pytest")
    hits = await store.search("test-thread", vector, top_k=5)
    assert len(hits) == 0


@pytest.mark.asyncio
async def test_commit_approved_memories_stores_and_clears(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Commit upserts approved rows, advances cursor, and clears pending."""
    settings = RagSettings(
        enabled=True,
        index_dir=tmp_path / "rag",  # type: ignore[operator]
        embedding_provider="openai",
        embedding_model="fake",
    )
    state = _state(
        messages=[
            HumanMessage(content="I prefer pytest"),
            AIMessage(content="Noted."),
        ],
        memory_cursor=0,
        pending_memories=[
            {
                "id": "m0",
                "content": "User prefers pytest",
                "memory_type": "preference",
                "importance": 0.9,
            },
        ],
        approved_memories=[
            {
                "content": "User prefers pytest",
                "memory_type": "preference",
                "importance": 0.9,
            },
        ],
    )
    monkeypatch.setattr(
        memory_extract_module,
        "get_embeddings",
        lambda _cfg=None: FakeEmbeddings(size=32),
    )

    store = MemoryStore()
    updates = await memory_extract_module.commit_approved_memories(
        state,
        memory_store=store,
        settings=settings,
    )

    assert updates["memory_cursor"] == 2
    assert updates["pending_memories"] == []
    assert updates["approved_memories"] == []
    vector = await FakeEmbeddings(size=32).aembed_query("pytest")
    hits = await store.search("test-thread", vector, top_k=5)
    assert len(hits) == 1
    assert "pytest" in hits[0].page_content
