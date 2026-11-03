"""Harness settings and runtime diagnostics route."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter

from agent.task_rewrite import is_task_rewrite_enabled
from app.schemas.settings import McpInfo, McpServerDetail, SystemSettingsResponse
from harness_mcp.config import load_mcp_server_configs
from harness_mcp.tools import get_cached_mcp_tools
from rag.config import load_rag_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SystemSettingsResponse)
async def get_system_settings() -> SystemSettingsResponse:
    """Return backend configuration for MCP, task rewriting, LLM, and RAG."""
    # MCP
    mcp_env_enabled = os.getenv("HARNESS_MCP_ENABLED", "").strip().lower() in ("1", "true", "yes")
    mcp_servers_raw = {}
    try:
        mcp_servers_raw = load_mcp_server_configs()
    except Exception:
        logger.debug("Failed to load MCP server configs", exc_info=True)

    servers_detail = {
        name: McpServerDetail(
            command=cfg.command,
            args=cfg.args,
            env=cfg.env,
        )
        for name, cfg in mcp_servers_raw.items()
    }

    cached_tools = []
    try:
        cached_tools = [getattr(t, "name", str(t)) for t in get_cached_mcp_tools()]
    except Exception:
        logger.debug("Failed to list cached MCP tools", exc_info=True)

    # RAG
    rag_settings = load_rag_settings()

    return SystemSettingsResponse(
        task_rewrite_enabled=is_task_rewrite_enabled(),
        human_in_the_loop_default=True,
        mcp=McpInfo(
            enabled=mcp_env_enabled or bool(servers_detail),
            servers=servers_detail,
            tools=cached_tools,
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        checkpoint_backend=os.getenv("CHECKPOINT_BACKEND", "sqlite"),
        rag_enabled=rag_settings.enabled,
        rag_rewrite_enabled=rag_settings.rewrite.enabled,
    )

