# harness-template

This repository is an agent-first LangGraph harness implementation.

`AGENTS.md` stays short on purpose. Treat it as a map, not the encyclopedia.
Repository-local markdown under `docs/` is the system of record for process and
ops. [`doc.md`](doc.md) is the system of record for runtime behavior, APIs, and
configuration.

If a code or workflow change makes a doc stale, update the doc in the same task.

## Read At The Start Of Each Task

- [`docs/REPO_COLLAB_GUIDE.md`](docs/REPO_COLLAB_GUIDE.md): collaboration,
  commit, documentation, and testing expectations.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): top-level architecture map and
  package boundaries.
- [`docs/design-docs/core-beliefs.md`](docs/design-docs/core-beliefs.md):
  agent-first operating principles.
- [`doc.md`](doc.md): agent loop, RAG, API routes, env vars, and schemas.

## Read Before Finishing A Code Change

- [`docs/HISTORY_GUIDE.md`](docs/HISTORY_GUIDE.md): when to record code
  changes, naming rules, and redaction rules.
- [`docs/QUALITY_SCORE.md`](docs/QUALITY_SCORE.md): current quality targets and
  gaps by area.

## Read When The Task Needs It

- [`docs/PLANS_GUIDE.md`](docs/PLANS_GUIDE.md): when to create an execution
  plan and how to maintain it.
- [`PRODUCT.md`](PRODUCT.md): product purpose, users, and UX constraints.
- [`docs/PRODUCT_SENSE.md`](docs/PRODUCT_SENSE.md): product tradeoff heuristics.
- [`DESIGN.md`](DESIGN.md): harness console visual system and layout rules.
- [`docs/FRONTEND.md`](docs/FRONTEND.md): frontend dev, build, and verification.
- [`docs/RELIABILITY.md`](docs/RELIABILITY.md): logging, health, timeouts, and
  operational readiness.
- [`docs/SECURITY.md`](docs/SECURITY.md): auth, secrets, and external
  integration defaults.
- [`docs/SUPPLY_CHAIN_SECURITY.md`](docs/SUPPLY_CHAIN_SECURITY.md): dependency
  and provenance guidance.
- [`docs/CICD.md`](docs/CICD.md): CI/CD status and where to add automation.
- [`mcp/README.md`](mcp/README.md): MCP server configuration for the executor.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): pull request expectations.
- [`docs/releases/README.md`](docs/releases/README.md): user-facing release notes.
- [`docs/references/README.md`](docs/references/README.md): curated external
  references.

## Working Rules

- Prefer small, explicit, repository-legible abstractions.
- Keep prompts, policies, and architectural rules versioned in-repo.
- For complex work, create an execution plan under `docs/exec-plans/active/`
  instead of relying on long chat context.
- Record finished code changes in `docs/histories/`.
- Core graph logic lives at the repository root (`agent/`, `graph/`, `rag/`).
  HTTP serving lives under `app/`. Do not move modules without updating
  `docs/ARCHITECTURE.md` and `tests/conftest.py` import aliases.
