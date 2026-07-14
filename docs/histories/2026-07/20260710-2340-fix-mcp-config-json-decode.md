## [2026-07-10 23:40] | Task: Fix MCP config JSONDecodeError on startup

### Execution Context

- Agent ID: `composer`
- Base Model: `Composer`
- Runtime: `Cursor`

### User Query

> Startup traceback: MCP tool registration failed with JSONDecodeError when loading server configs.

### Changes Overview

- Area: MCP config loading
- Key actions: Stop auto-loading the commented example file; harden invalid JSON handling; make example file valid JSON.

### Design Intent

`mcp_config/servers.example.json` was in the default search path but started with `#` comments, so it was invalid JSON and triggered MCP load even without `HARNESS_MCP_ENABLED`. Default paths should only include real config locations (`mcp/servers.json`, `.cursor/mcp.json`). Invalid JSON should warn and return empty rather than raise.

### Files Modified

- `harness_mcp/config.py`
- `mcp_config/servers.example.json`
- `tests/test_mcp.py`
