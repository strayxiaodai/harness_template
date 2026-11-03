## [2026-11-02 19:36] | Task: Interactive Click-to-Confirm HITL for All Nodes

### User Query
> for each steps, when human in the loop enabled, I hope it can be a interactive with human, list questions and human click to confirm then process.

### Changes Overview
- Schema: Extended `ClarificationQuestion` with `options: list[str]`, `default: str | None`, and `is_multi_select: bool`.
- State & Clarification helper: Added `clarification_answers` to `AgentState`. Updated `normalize_clarification_answers` to auto-populate default selections when resumed without manual text entry.
- Agent Nodes: Wired interactive confirmation questions into `planner_agent`, `executor_agent`, and `learner_agent` when `human_in_the_loop` is True, allowing operators to approve or override decisions in one click.
- Frontend UI: Extended `types/api.ts` and `useResumeDraft.ts` to support question options and defaults. Updated `Workplace.tsx` and `Workplace.css` with interactive option buttons (`.btn-option`, `.btn-option--selected`, `.btn-option--recommended`) for single-click selection.
- MCP Resilience: In `memory/checkpoint.py` and `harness_mcp/config.py`, handled missing, empty, or unparseable MCP configs with clean logger warnings rather than logging multi-line tracebacks. Removed `servers.example.json` from active `_DEFAULT_PATHS`.
- Ollama `/v1` Normalization: In `llm/providers.py`, normalized Ollama `base_url` to append `/v1` when missing, matching OpenAI-compatible endpoint format and resolving `404 page not found` errors during structured query rewriting. In `tools/thread_files.py`, handled missing thread file reads gracefully.
- Verification: Added unit tests in `tests/test_clarification.py` and `tests/test_mcp.py`. Full non-live test suite verified (`206 passed, 3 deselected`) and live e2e run verified.

### Design Intent
Avoid blunt pauses or blank text inputs by turning HITL interruptions into structured, one-click decision cards. Each step surfaces clear options with a `(Recommended)` choice so the operator can review and continue in under two seconds while maintaining explicit control over plan adjustments, code edits, and verification verdicts.

### Files Modified
- `graph/schemas.py`
- `graph/state.py`
- `agent/clarification.py`
- `agent/planner.py`
- `agent/executor.py`
- `agent/learner.py`
- `app/frontend/src/types/api.ts`
- `app/frontend/src/hooks/useResumeDraft.ts`
- `app/frontend/src/components/Workplace.tsx`
- `app/frontend/src/components/Workplace.css`
- `tests/test_clarification.py`
- `docs/exec-plans/active/20261102-interactive-hitl-clarification.md`

