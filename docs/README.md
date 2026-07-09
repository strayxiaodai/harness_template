# Documentation Index

Knowledge base for this LangGraph harness. [`AGENTS.md`](../AGENTS.md) routes
agents to the right file for each task.

[`IMPLEMENTATION.md`](IMPLEMENTATION.md) is the **as-built implementation guide** (API, RAG, state, config,
curl examples). Other files in `docs/` cover process, ops, product heuristics,
and focused references.

## Recommended Reading Order

### New to the repo

1. [`../README.md`](../README.md) — install and quick start
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — layout and runtime topology
3. [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — API and configuration depth
4. [`PRODUCT.md`](PRODUCT.md) + [`DESIGN.md`](DESIGN.md) — console intent

### Before a code change

1. [`REPO_COLLAB_GUIDE.md`](REPO_COLLAB_GUIDE.md) — testing and doc sync rules
2. Relevant section of [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
3. [`QUALITY_SCORE.md`](QUALITY_SCORE.md) — weakest areas to harden

### Before a frontend change

1. [`FRONTEND.md`](FRONTEND.md) — components, proxy, API mapping
2. [`DESIGN.md`](DESIGN.md) — tokens and layout
3. [`IMPLEMENTATION.md`](IMPLEMENTATION.md#http-api) — request/response shapes

## Doc Map

### Technical

| Doc | When to read |
| --- | --- |
| [`IMPLEMENTATION.md`](IMPLEMENTATION.md) | API, RAG, agents, env vars, examples |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Repo layout, boundaries, console mapping |
| [`LANGGRAPH.md`](LANGGRAPH.md) | Checkpoint backends |
| [`ASYNCIO.md`](ASYNCIO.md) | Async patterns in FastAPI + LangGraph |
| [`FRONTEND.md`](FRONTEND.md) | React console dev guide |

### Process and quality

| Doc | Purpose |
| --- | --- |
| [`REPO_COLLAB_GUIDE.md`](REPO_COLLAB_GUIDE.md) | Collaboration and validation |
| [`QUALITY_SCORE.md`](QUALITY_SCORE.md) | Quality by area |
| [`HISTORY_GUIDE.md`](HISTORY_GUIDE.md) | Change history format |
| [`PLANS_GUIDE.md`](PLANS_GUIDE.md) | Execution plans |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | PR checklist |

### Product and design

| Doc | Purpose |
| --- | --- |
| [`PRODUCT.md`](PRODUCT.md) | Product spec (users, purpose, principles) |
| [`PRODUCT_SENSE.md`](PRODUCT_SENSE.md) | Tradeoff heuristics |
| [`DESIGN.md`](DESIGN.md) | Console design system (tokens, layout, UI map) |

### Operations

| Doc | Purpose |
| --- | --- |
| [`RELIABILITY.md`](RELIABILITY.md) | Health, timeouts, failure modes |
| [`SECURITY.md`](SECURITY.md) | Threat model, secrets, tools |
| [`SUPPLY_CHAIN_SECURITY.md`](SUPPLY_CHAIN_SECURITY.md) | Dependencies |
| [`CICD.md`](CICD.md) | CI/CD roadmap |

## Directories

| Path | Purpose |
| --- | --- |
| [`design-docs/`](design-docs/) | Core beliefs and design index |
| [`exec-plans/`](exec-plans/) | Active and completed plans |
| [`histories/`](histories/) | Finished change records |
| [`releases/`](releases/) | User-facing release notes |
| [`references/`](references/) | Curated external references |

## Maintenance Rules

When you change behavior, update docs in the **same PR**:

| Change type | Update |
| --- | --- |
| API schema / route | `IMPLEMENTATION.md`, `app/frontend/src/types/api.ts`, maybe `FRONTEND.md` |
| Graph node or state | `IMPLEMENTATION.md`, `ARCHITECTURE.md` |
| Env var | `IMPLEMENTATION.md`, `SECURITY.md` if secret |
| UI component | `FRONTEND.md`, `DESIGN.md` if tokens change |
| CI pipeline | `CICD.md`, `CONTRIBUTING.md` |
| User-visible feature | `releases/feature-release-notes.md` |
| Finished task | `histories/YYYY-MM/` per `HISTORY_GUIDE.md` |

Record material quality shifts in [`QUALITY_SCORE.md`](QUALITY_SCORE.md).

## File Naming

Top-level docs in `docs/` follow a small, consistent scheme:

| Pattern | Examples | Use for |
| --- | --- | --- |
| `UPPER_SNAKE.md` | `ARCHITECTURE.md`, `FRONTEND.md`, `ASYNCIO.md` | Topic guides and references |
| `*_GUIDE.md` | `HISTORY_GUIDE.md`, `PLANS_GUIDE.md`, `REPO_COLLAB_GUIDE.md` | Process and workflow meta-docs |
| `IMPLEMENTATION.md` | — | As-built implementation guide (API, RAG, agents, config) |
| `README.md` | `docs/README.md`, `releases/README.md` | Index for a folder |

**Subdirectories** use kebab-case (`design-docs/`, `exec-plans/`) with kebab-case
filenames inside (`core-beliefs.md`, `tech-debt-tracker.md`). History entries
use `YYYYMMDD-HHMM-short-slug.md` under `histories/YYYY-MM/`.

**Root entry files** (`README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `LICENSE`)
stay at the repository root — not under `docs/`.
