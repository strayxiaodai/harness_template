## [2026-07-07 00:20] | Task: Add README, AGENTS.md, LICENSE, CONTRIBUTING, and upstream docs scaffold

### User Query

> Implement README.md, AGENTS.md, LICENSE, CONTRIBUTING.md and port/adapt upstream
> docs/ from iFurySt/harness-template; check conflicts with current code first.

### Changes Overview

- Area: Repository scaffolding and documentation
- Key actions:
  - Added root entry files (README, AGENTS, LICENSE, CONTRIBUTING)
  - Ported upstream `docs/` structure with project-specific content
  - Resolved conflicts with existing `doc.md`, `PRODUCT.md`, `DESIGN.md`
  - Added `docs/README.md` index and history entry

### Design Intent

Upstream harness-template provides methodology scaffolding; this repo already
had a full LangGraph implementation and Impeccable product/design docs at the
root. Rather than overwrite or duplicate:

- `doc.md` remains the technical encyclopedia (README links to it)
- `PRODUCT.md` and `DESIGN.md` stay at repo root; `docs/PRODUCT_SENSE.md` and
  `docs/DESIGN.md` point to them
- `docs/ARCHITECTURE.md` documents the actual flat layout, not upstream's
  `apps/packages/infra` placeholder
- `docs/QUALITY_SCORE.md` reflects real scores, not template defaults

### Files Modified

- `README.md`, `AGENTS.md`, `LICENSE`, `CONTRIBUTING.md` (new)
- `doc.md` (onboarding pointer only)
- `docs/**` (new and adapted scaffold)
- `docs/histories/2026-07/20260707-0020-add-agents-docs-scaffold.md`
