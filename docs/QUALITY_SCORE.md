# Quality Score

Track quality by product area and architectural layer so agents can prioritize
the weakest parts of the system.

## Scale

- `A`: strong coverage, stable behavior, clear docs, low operational risk.
- `B`: acceptable but still has known gaps.
- `C`: works but needs targeted hardening.
- `D`: fragile or underspecified.

## Current Scores

| Area | Score | Why | Next Step |
| --- | --- | --- | --- |
| Product surface | B | [`PRODUCT.md`](../PRODUCT.md) and [`DESIGN.md`](../DESIGN.md) define the console; React UI exists under `app/frontend/`. | Add thread list/history API and wire UI to audit rows. |
| Architecture docs | B | [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`doc.md`](../doc.md) describe the real layout. | Finish `app/` refactor commit; remove conftest import aliases when layout stabilizes. |
| Agent loop | B | planner → executor → reviewer → actioner → memorize is implemented and tested. | Add write/edit executor tools for code-changing workflows. |
| Testing | B | 17 pytest modules; API, graph, RAG, MCP, skills covered. | Add Docker Compose integration tests; frontend test suite. |
| API / serving | B | `/run`, `/resume`, `/stream`, `/health`, `/skills` implemented. | Add auth, rate limiting, run cancellation. |
| RAG / memory | B | Hybrid retrieve, ingest, FAISS default, pgvector optional. | RAG audit events; prompt-injection guardrails on recall. |
| Observability | C | Python logging + optional Postgres audit. No metrics/traces. | Document log conventions; add structured logging config. |
| Security | D | API routes are open; no rate limits. | Auth middleware; document threat model in [`SECURITY.md`](SECURITY.md). |
| Infrastructure | D | No Docker Compose, no CI workflows. | `docker-compose.yml` + GitHub Actions pytest gate. |
| Harness scaffolding | B | `AGENTS.md`, `docs/`, `CONTRIBUTING.md` now in place. | Add `Makefile`/`scripts/` from upstream template. |

Update this table when an area materially improves or regresses.
