"""Load MCP server definitions from env or config files."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from harness_mcp.schemas import McpServersDocument, McpStdioServerConfig

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PATHS = (
    _REPO_ROOT / "mcp" / "servers.json",
    _REPO_ROOT / "mcp_config" / "servers.example.json",
    _REPO_ROOT / ".cursor" / "mcp.json",
)


def _parse_servers_payload(payload: object) -> dict[str, McpStdioServerConfig]:
    """Normalize JSON into server configs."""
    if not isinstance(payload, dict):
        msg = "MCP config must be a JSON object"
        raise ValueError(msg)

    if "mcpServers" in payload:
        doc = McpServersDocument.model_validate(payload)
        return doc.mcpServers

    servers: dict[str, McpStdioServerConfig] = {}
    for name, raw in payload.items():
        if not isinstance(raw, dict):
            continue
        servers[name] = McpStdioServerConfig.model_validate(raw)
    return servers


def load_mcp_server_configs() -> dict[str, McpStdioServerConfig]:
    """Load MCP server configs when MCP is enabled."""
    enabled = os.getenv("HARNESS_MCP_ENABLED", "").strip().lower()
    if enabled in {"0", "false", "no"}:
        return {}

    inline = os.getenv("HARNESS_MCP_SERVERS", "").strip()
    config_path = os.getenv("HARNESS_MCP_CONFIG", "").strip()
    default_path = next((candidate for candidate in _DEFAULT_PATHS if candidate.is_file()), None)

    if not inline and not config_path and default_path is None and enabled not in {
        "1",
        "true",
        "yes",
    }:
        return {}

    if inline:
        return _parse_servers_payload(json.loads(inline))

    path = Path(config_path).expanduser() if config_path else default_path
    if path is None or not path.is_file():
        logger.warning("MCP enabled but no servers config file found")
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    servers = _parse_servers_payload(payload)
    logger.info("Loaded %d MCP server(s) from %s", len(servers), path)
    return servers
