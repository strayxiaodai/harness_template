## [2026-10-06 03:35] | Task: Replace Logfire With Langfuse For Tracing & Observability

### User Query
> for log tracing, could we use langfuse? replace with langfuse

### Changes Overview
- **Dependencies (`pyproject.toml`, `requirements.txt`)**: Replaced `logfire` with `langfuse` and `langchain`.
- **Observability (`audit/tracing.py`)**: Replaced Logfire instrumentation with Langfuse integration:
  - Added `init_tracing()` with automatic environment detection.
  - Added `get_langfuse_handler()` providing Langfuse's native `CallbackHandler` for LangGraph run/stream/resume sessions.
  - Added `trace_event()` emitting structured events to Langfuse.
  - Added `flush_tracing()` to ensure all pending spans flush upon execution completion.
- **Harness Service (`app/services/harness.py`)**: Updated `_graph_config()`, `run_harness()`, `resume_harness()`, and `stream_harness()` to attach the Langfuse callback handler and thread/task metadata to all LangGraph invocations.
- **Tests (`tests/test_tracing.py`)**: Updated unit tests covering local initialization, enablement flags, callback handler creation, and event emissions.
- **Documentation (`docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION.md`)**: Updated observability topology, configuration guide, and environment variable references.

### Design Intent
- Langfuse provides native LangGraph DAG execution tracing (mapping `planner`, `executor`, `learner`, `actioner` node transitions, tokens, and latencies automatically).
- Thread-level isolation maps directly to Langfuse's session tracking using `thread_id`.
- Graceful degradation: in test and local environments without API credentials, tracing disables silently without crashing the harness.

### Files Modified
- `pyproject.toml`
- `requirements.txt`
- `audit/tracing.py`
- `app/services/harness.py`
- `tests/test_tracing.py`
- `docs/ARCHITECTURE.md`
- `docs/IMPLEMENTATION.md`
- `docs/histories/2026-10/20261006-0335-langfuse-tracing-integration.md`
