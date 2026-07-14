## [2026-07-14 01:15] | Task: Executor thread scripts + Docker learner runs

### User Query
> During executor phase, enable creating scripts (Deterministic/LLM/Hybrid). Persist under `app/threads/<task-slug>/scripts/`, run in learner via Docker S2 for review; distill to skills later.

### Changes Overview
- Area: executor/learner tools, Docker sandbox, prompts, docs
- Key actions: `write_thread_file` / `read_thread_file`; `run_thread_script` with manifest gate and Docker S2; learner tool loop; architect prompt guidance

### Design Intent
Prefer writing deterministic Python into the thread scripts tree over LLM-only verification; isolate execution in Docker with no host fallback. Phase D (promote into `app/skills`) deferred.

### Files Modified
- `tools/thread_files.py`, `tools/manifest.py`, `tools/sandbox_docker.py`, `tools/script_tools.py`, `tools/registry.py`
- `agent/executor.py`, `agent/learner.py`, `graph/state.py`
- `app/services/thread_artifacts.py`
- `config/prompts.yaml`
- `docs/IMPLEMENTATION.md`, `docs/SECURITY.md`
- `docs/superpowers/specs/2026-07-13-executor-thread-scripts-design.md`
- `docs/superpowers/plans/2026-07-13-executor-thread-scripts.md`
- tests under `tests/test_thread_files.py`, `test_manifest.py`, `test_sandbox_docker.py`, `test_script_tools.py`, `test_learner_tools.py`, etc.
