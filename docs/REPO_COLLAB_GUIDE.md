# Repository Collaboration Guide

Default collaboration model for this agent-first LangGraph harness.

## Development Principles

- Prefer boring, legible, well-instrumented technology over opaque complexity.
- Optimize for agent legibility: knowledge in versioned files beats chat context.
- Keep code, docs, tests, config, and release notes synchronized.
- Fix scaffolding when agents repeatedly fail — not just the prompt.
- When fixing a bug, expand tests and docs so the same class stays caught.

## Documentation Discipline

| Layer | File | Role |
| --- | --- | --- |
| Agent router | [`AGENTS.md`](../AGENTS.md) | What to read per task |
| Technical implementation | [`IMPLEMENTATION.md`](IMPLEMENTATION.md) | Runtime behavior, API, RAG |
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layout and boundaries |
| Process / ops | `docs/*.md` | Collaboration, security, CI |
| Product | [`PRODUCT.md`](PRODUCT.md) | Console purpose and UX rules |
| Visual system | [`DESIGN.md`](DESIGN.md) | Tokens and layout |

If behavior changes, update the corresponding docs in the same change. Prefer a
new focused doc over appending to a catch-all file.

**Example — API field added to `RunResponse`:**

1. `app/schemas/run.py`
2. `docs/IMPLEMENTATION.md` (JSON example)
3. `app/frontend/src/types/api.ts`
4. `tests/test_api.py`

## Git And Review

- Keep commits scoped and descriptive.
- Before PR: docs, examples, and histories match final behavior.
- Large work: execution plan in `docs/exec-plans/active/`.
- Cite repository files in review comments, not private context.

## Testing And Validation

| Area | Command | When |
| --- | --- | --- |
| Python unit tests | `pytest tests/ -q -k "not live"` | Any Python change |
| API smoke | `pytest tests/test_api.py -v` | `app/` changes |
| Graph / agents | `pytest tests/test_graph.py tests/test_actioner.py -v` | `agent/`, `graph/` |
| RAG | `pytest tests/test_rag_service.py tests/test_memory_pipeline.py -v` | `rag/` |
| Frontend lint | `cd app/frontend && npm run lint` | `app/frontend/` |
| Frontend build | `cd app/frontend && npm run build` | `app/frontend/` |

Integration tests (`@pytest.mark.integration`) require external services and are
not part of the default gate yet.

**Example — minimal pre-PR check:**

```bash
pytest tests/ -q -k "not live" && cd app/frontend && npm run build
```

## CI/CD And Release

No GitHub Actions yet. See [`CICD.md`](CICD.md). When adding pipelines, update
`CICD.md` and [`CONTRIBUTING.md`](../CONTRIBUTING.md) together.

User-visible changes: [`releases/feature-release-notes.md`](releases/feature-release-notes.md).

## Configuration Hygiene

- Document env vars in [`IMPLEMENTATION.md`](IMPLEMENTATION.md).
- Keep `.env` out of version control.
- Avoid hidden setup — encode steps in markdown or scripts.

**Example — new optional env var:**

```bash
# docs/IMPLEMENTATION.md configuration table
MY_FEATURE_FLAG=true   # enables experimental X
```

## History Records

Finished code-change tasks: one file in `docs/histories/YYYY-MM/` per
[`HISTORY_GUIDE.md`](HISTORY_GUIDE.md). Pure Q&A without repo changes does not
need a history entry.
