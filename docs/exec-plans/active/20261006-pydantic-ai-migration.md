# PydanticAI Migration: LLM, MCP, and Agent Refactor

## Goal

Refine the harness repository by migrating the LLM provider layer and the MCP integration layer to PydanticAI's APIs (`pydantic_ai.models`, `pydantic_ai.providers`, `pydantic_ai.mcp`, `pydantic_ai.Agent`), while preserving LangGraph state graph topology, node contracts, audit logging, and checkpointer persistence.

## Scope

- In scope:
  - Add `pydantic-ai` to `pyproject.toml` and `requirements.txt`.
  - Refactor `llm/providers.py` to construct PydanticAI models (`OpenAIChatModel`, `AnthropicModel`, `OllamaModel`, `VLLMProvider`).
  - Refactor `llm/retry.py` to support PydanticAI Agent execution and transient error retries.
  - Refactor `harness_mcp/` (`config.py`, `client.py`, `tools.py`) to use PydanticAI's `pydantic_ai.mcp` (`MCPToolset`, `load_mcp_toolsets`).
  - Refactor structured LLM generation in `agent/planner.py`, `agent/actioner.py`, `skills/distill.py`, `rag/retrieve/rewrite.py`, `rag/ingest/memory_extract.py`, `agent/executor.py`, and `agent/learner.py` to use PydanticAI `Agent` runs.
  - Update tests (`tests/test_mcp.py`, `tests/test_llm_providers.py`, `tests/test_planner.py`, `tests/test_executor.py`, etc.) and docs (`docs/IMPLEMENTATION.md`, `docs/ARCHITECTURE.md`, `mcp/README.md`).
  - Create a history file in `docs/histories/2026-10/`.
- Out of scope:
  - Replacing LangGraph checkpointers or StateGraph routing.
  - Modifying FastAPI routes or React frontend UI.

## Context

- Relevant docs:
  - `docs/ARCHITECTURE.md`
  - `docs/IMPLEMENTATION.md`
  - `mcp/README.md`
- Relevant code paths:
  - `llm/`
  - `harness_mcp/`
  - `agent/`
  - `rag/`
  - `skills/`
  - `tools/`
  - `tests/`
- Constraints:
  - LangGraph node outputs must adhere to `AgentState` schema (`messages`, `plan`, `execution`, `learning`, `role`, etc.).
  - All unit tests must pass without external credentials (`pytest tests/ -q -k "not live"`).

## Risks

- Risk: PydanticAI model instantiation requires credentials unless mocked or passed dummy keys in tests.
  - Mitigation: Provide mock-friendly factory defaults and test model support (`TestModel`), matching the existing `_llm_credentials_configured()` patterns.
- Risk: LangGraph `messages` expecting LangChain `BaseMessage` objects.
  - Mitigation: PydanticAI runs produce structured models and messages; ensure node returns continue wrapping final strings into `AIMessage` as required by `AgentState`.
- Risk: MCP toolsets lifecycle management during FastAPI lifespan.
  - Mitigation: Connect and shutdown `MCPToolset` clients cleanly during `_startup_mcp()` and `_shutdown_mcp()`.

## Milestones

1. Project dependencies and configuration update.
2. `llm/` module refactoring with PydanticAI models and runner.
3. `harness_mcp/` module refactoring with PydanticAI MCP API.
4. Refactoring agents and structured generators (`planner`, `actioner`, `skills`, `rag`, `executor`, `learner`).
5. Unit tests update and validation.
6. Documentation updates and history log.

## Validation

- Commands:
  - `.venv/bin/pytest tests/test_llm_providers.py -v`
  - `.venv/bin/pytest tests/test_mcp.py -v`
  - `.venv/bin/pytest tests/ -q -k "not live"`
- Manual checks:
  - Verify `get_model()` and `get_llm()` with openai, anthropic, ollama, vllm.
  - Verify MCP config loading with `servers.example.json`.

## Progress Log

- [x] Add `pydantic-ai` and `logfire` to `pyproject.toml` and `requirements.txt`.
- [x] Refactor `llm/providers.py` and `llm/retry.py`.
- [x] Refactor `harness_mcp/` to use `pydantic_ai.mcp`.
- [x] Unify tools with `HarnessTool`, `@harness_tool`, and `execute_tool` (#1 & #2).
- [x] Migrate standalone extraction and rewriting agents (`rewrite_for_memory`, `extract_memories`, `_draft_skill`) to PydanticAI `Agent` (#3).
- [x] Integrate OpenTelemetry / Logfire tracing for PydanticAI and audit logging via `audit/tracing.py` (#4).
- [x] Update and expand unit tests (`test_harness_tools.py`, `test_standalone_agents.py`, `test_tracing.py`).
- [x] Run full test suite (`pytest tests/ -q -k "not live"`: 195 passed).
- [x] Update documentation and write history record.


## Decision Log

- 2026-10-06: Selected Deep integration with LangGraph compatibility: PydanticAI models, MCPToolsets, and Agent-based structured execution while preserving LangGraph state and workflow topology.
