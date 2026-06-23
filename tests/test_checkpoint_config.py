"""Tests for checkpoint backend selection."""

from __future__ import annotations

import pytest

from memory.checkpoint_config import resolve_checkpoint_backend, sqlite_checkpoint_path


def test_default_backend_is_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local dev defaults to SQLite when backend is not explicit."""
    monkeypatch.delenv("CHECKPOINT_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert resolve_checkpoint_backend() == "sqlite"


def test_explicit_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """CHECKPOINT_BACKEND=memory overrides defaults."""
    monkeypatch.setenv("CHECKPOINT_BACKEND", "memory")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/agents")
    assert resolve_checkpoint_backend() == "memory"


def test_docker_database_url_does_not_force_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose-style DATABASE_URL alone should not pick Postgres locally."""
    monkeypatch.delenv("CHECKPOINT_BACKEND", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/agents")
    assert resolve_checkpoint_backend() == "sqlite"


def test_explicit_postgres_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """CHECKPOINT_BACKEND=postgres is honored."""
    monkeypatch.setenv("CHECKPOINT_BACKEND", "postgres")
    assert resolve_checkpoint_backend() == "postgres"


def test_sqlite_checkpoint_path_default(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default SQLite path lives under data/checkpoints/."""
    monkeypatch.delenv("CHECKPOINT_SQLITE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    path = sqlite_checkpoint_path()
    assert path.endswith("data/checkpoints/langgraph.db")
    assert (tmp_path / "data" / "checkpoints").is_dir()


def test_compile_with_sqlite_checkpointer(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Graph compiles with an async SQLite checkpointer."""
    pytest.importorskip("langgraph")
    pytest.importorskip("langgraph.checkpoint.sqlite")

    import asyncio

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from graph.builder import compile_with_checkpointer

    db_path = tmp_path / "test.db"

    async def _compile() -> object:
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
            await saver.setup()
            return compile_with_checkpointer(saver)

    graph = asyncio.run(_compile())
    assert graph is not None
