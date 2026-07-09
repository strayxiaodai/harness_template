# Quality Score

Track quality by area so agents and contributors prioritize the weakest layers.

## Scale

| Grade | Meaning |
| --- | --- |
| **A** | Strong coverage, stable behavior, clear docs, low operational risk |
| **B** | Acceptable with known, documented gaps |
| **C** | Works but needs targeted hardening |
| **D** | Fragile or underspecified |

## Current Scores

| Area | Score | Why | Next step |
| --- | --- | --- | --- |
| Product surface | B | [`PRODUCT.md`](PRODUCT.md), [`DESIGN.md`](DESIGN.md), React console with graph spine + inspector | Thread list API; audit panel in UI |
| Architecture docs | **B+** | [`ARCHITECTURE.md`](ARCHITECTURE.md), [`IMPLEMENTATION.md`](IMPLEMENTATION.md) with examples; console↔API map | Keep in sync when API changes |
| Agent loop | B | Full loop + loop scoring + skill-preview HITL | Sandboxed write/edit executor tools |
| Testing | B | pytest across agents, graph, RAG, API, MCP, skills | Docker integration tests; frontend e2e |
| API / serving | B | `/run`, `/resume`, `/stream`, `/health`, `/skills` | Auth, rate limits, cancellation |
| RAG / memory | B | Hybrid retrieve, FAISS default, pgvector optional | Recall guardrails; RAG audit events |
| Documentation | **B+** | `docs/` scaffold, indexed in [`README.md`](README.md), examples in `IMPLEMENTATION.md` | Add `Makefile`/`scripts/`; CI doc when workflows land |
| Observability | C | Logging + optional Postgres audit | Structured logging; `thread_id` correlation |
| Security | D | Open API; read-only tools | Auth middleware; threat model in [`SECURITY.md`](SECURITY.md) |
| Infrastructure | D | No Compose, no CI workflows | `docker-compose.yml` + GitHub Actions pytest gate |
| Harness scaffolding | B | `AGENTS.md`, `CONTRIBUTING.md`, histories/exec-plans | Upstream `scripts/` from iFurySt template |

Update this table when an area materially improves or regresses.

## Example — when to bump a score

| Event | Action |
| --- | --- |
| GitHub Actions pytest gate merged | Infrastructure → C; Documentation note CI in `CICD.md` |
| Auth middleware shipped | Security → C; update `SECURITY.md` examples |
| Playwright e2e for console | Testing → B+; document in `FRONTEND.md` |

## Related

- Gaps tracked in [`exec-plans/tech-debt-tracker.md`](exec-plans/tech-debt-tracker.md)
- Roadmap in [`IMPLEMENTATION.md`](IMPLEMENTATION.md#roadmap)
