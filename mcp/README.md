# MCP Integration for the Harness

Config and docs for calling external Model Context Protocol (MCP) servers from the harness executor via PydanticAI.

Python implementation: `harness_mcp/` (powered by `pydantic_ai.mcp` and `MCPToolset`).

## Enable

1. Copy `servers.example.json` to `mcp/servers.json` (or use `.cursor/mcp.json`)
2. Set `HARNESS_MCP_ENABLED=true`
3. Install dependencies: `pip install -e ".[mcp]"` or ensure `pydantic-ai` is installed.
4. Restart the API

MCP tools are discovered at startup via PydanticAI MCP toolsets and registered for the executor as `mcp__{server}__{tool}` (as well as native `MCPToolset` instances accessible via `get_cached_mcp_toolsets()`).

## Config

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

Environment:

| Variable | Purpose |
|----------|---------|
| `HARNESS_MCP_ENABLED` | `true` to force enable |
| `HARNESS_MCP_CONFIG` | Path to servers JSON |
| `HARNESS_MCP_SERVERS` | Inline JSON (overrides file) |
| `HARNESS_MCP_INCLUDE_ALL` | Auto-allow MCP tools in executor (default `true`) |
