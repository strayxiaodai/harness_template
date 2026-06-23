"""Graph checkpointer and FastAPI lifespan."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from audit.logger import set_audit_pool
from graph.builder import compile_with_checkpointer
from memory.checkpoint_config import resolve_checkpoint_backend, sqlite_checkpoint_path
from rag.service import init_rag_service
from rag.stores.memory_pg import set_memory_pool

load_dotenv()
logger = logging.getLogger(__name__)


def _compile_graphs(app: FastAPI, saver: object) -> None:
    """Attach auto and HITL graphs to application state."""
    app.state.graph_auto = compile_with_checkpointer(
        saver,
        human_in_the_loop=False,
    )
    app.state.graph_step = compile_with_checkpointer(
        saver,
        human_in_the_loop=True,
    )


@asynccontextmanager
async def graph_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open checkpointer, pools, RAG service, and compile both graphs."""
    init_rag_service()
    backend = resolve_checkpoint_backend()

    if backend == "postgres":
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            msg = "CHECKPOINT_BACKEND=postgres requires DATABASE_URL"
            raise RuntimeError(msg)

        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        async with AsyncConnectionPool(database_url, open=False) as audit_pool:
            await audit_pool.open()
            set_audit_pool(audit_pool)
            set_memory_pool(audit_pool)

            async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
                await saver.setup()
                _compile_graphs(app, saver)
                logger.info("Compiled graphs with Postgres checkpointer")
                try:
                    yield
                finally:
                    set_audit_pool(None)
                    set_memory_pool(None)
    elif backend == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        conn_string = sqlite_checkpoint_path()
        async with AsyncSqliteSaver.from_conn_string(conn_string) as saver:
            await saver.setup()
            _compile_graphs(app, saver)
            logger.info("Compiled graphs with SQLite checkpointer at %s", conn_string)
            yield
    else:
        saver = MemorySaver()
        _compile_graphs(app, saver)
        logger.info("Compiled graphs with in-memory checkpointer")
        yield
