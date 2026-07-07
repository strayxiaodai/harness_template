# MCP integration for the harness

Config and docs for calling external MCP servers from the executor.

Python implementation: `harness_mcp/` (named to avoid clashing with the official `mcp` PyPI package).

## Enable

1. Copy `servers.example.json` to `mcp/servers.json` (or use `.cursor/mcp.json`)
2. Set `HARNESS_MCP_ENABLED=true`
3. Install optional dependency: `pip install mcp` or `pip install -e ".[mcp]"`
4. Restart the API

MCP tools are registered at startup and exposed to the executor as `mcp__{server}__{tool}`.

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
