## [2026-11-02 23:26] | Task: Implement prompt rewrite for user input and task execution

### User Query
> do we have prompt rewrite for user's input? ... combine together and continue implement ... ok, add settings page in frontend, which include: mcp server, TASK_REWRITE_ENABLED, human in the loop, also think which kind of settings are suitable to put in front end as option ... can you design the gui with this style?

### Changes Overview
- **Prompts**: Added `task_rewrite` prompt section to `config/prompts.yaml` defining a standardized engineering specification template (`# Role`, `# Context & Background`, `# Core Objectives`, `# Output Specifications`, `# Constraints`, `# Acceptance Criteria`) and extraction instructions.
- **Agent Node**: Added `agent/task_rewrite.py` with `is_task_rewrite_enabled`, `format_task_rewrite_input`, and `rewrite_task_input` using PydanticAI `Agent` with retry.
- **Planner Integration**: Updated `agent/planner.py` to rewrite the task on round 0 when enabled, store `raw_task`, update `state["task"]` with the rewritten specification, and pass it to downstream nodes.
- **State & Schema**: Updated `graph/state.py` with `raw_task`, `rewrite_task`, and `task_rewritten`. Added `rewrite_task` field to `RunRequest` in `app/schemas/run.py` and state builder in `app/services/state.py`.
- **Backend Settings API**: Added `GET /api/settings` route returning runtime diagnostics for MCP (`HARNESS_MCP_ENABLED`, discovered servers & tools), task rewrite status, RAG, and LLM provider.
- **Harness Console Dark Interface Redesign**:
  - Implemented `Sidebar` component (`app/frontend/src/components/Sidebar.tsx`) with Harness emblem, `Harness CONSOLE` wordmark, `+ New Session`, `Plugins & MCP`, `Automation tasks`, `Workspaces` list, and local engine runtime footer.
  - Implemented `HeroWorkspace` component (`app/frontend/src/components/HeroWorkspace.tsx`) with centered "Harness Agent Engine" node emblem, workspace & mode dropdowns, and large rounded prompt card with `+` context button and circular submit button.
  - Redesigned `SettingsModal` (`app/frontend/src/components/SettingsModal.tsx`) using the two-pane dialog layout inspired by modern dark slate interfaces: "Settings & Harness Config" header, "Configuration Files" button, left tab navigation (`Engine Status`, `General Loop`, `Models & LLMs`, `MCP & Plugins`, `Skills & Presets`), and right card stack with local engine status, active loop diagnostics, and controls for `TASK_REWRITE_ENABLED`, `Human in the loop`, model selection, and MCP servers.
  - Updated color tokens in `tokens.css` to a dark slate instrument palette (`#141518`, `#1b1c20`, `#25262b`, `#4d6cb0`).

### Design Intent
- Zero breaking changes: all harness functionality (LangGraph loop, HITL interrupts, SSE streaming, thread artifacts) remains intact while elevating the console into a sleek dark instrument layout adapted for Harness.
- All mock artifacts (third-party brand names, fake balances, and mock accounts) were eliminated in favor of genuine Harness engine diagnostics and controls.

### Files Modified
- `config/prompts.yaml`
- `agent/task_rewrite.py` (new)
- `agent/planner.py`
- `graph/state.py`
- `app/schemas/run.py`
- `app/schemas/settings.py` (new)
- `app/api/settings.py` (new)
- `app/core/app.py`
- `app/services/state.py`
- `app/frontend/src/styles/tokens.css`
- `app/frontend/src/App.css`
- `app/frontend/src/types/api.ts`
- `app/frontend/src/lib/api.ts`
- `app/frontend/src/hooks/useSettings.ts` (new)
- `app/frontend/src/hooks/useConsole.ts`
- `app/frontend/src/components/Sidebar.tsx` (new)
- `app/frontend/src/components/Sidebar.css` (new)
- `app/frontend/src/components/HeroWorkspace.tsx` (new)
- `app/frontend/src/components/HeroWorkspace.css` (new)
- `app/frontend/src/components/StatusBar.tsx`
- `app/frontend/src/components/StatusBar.css`
- `app/frontend/src/components/CenterColumn.tsx`
- `app/frontend/src/components/Workplace.tsx`
- `app/frontend/src/components/CommandColumn.tsx`
- `app/frontend/src/components/SettingsModal.tsx` (new)
- `app/frontend/src/components/SettingsModal.css` (new)
- `app/frontend/src/App.tsx`
- `tests/conftest.py`
- `tests/test_task_rewrite.py` (new)
- `tests/test_api.py`
- `docs/IMPLEMENTATION.md`
- `docs/histories/2026-11/20261102-2326-user-task-rewrite.md` (new)

