## [2026-07-08 19:35] | Task: Move DESIGN.md to docs/

### User Query

> Rename DESIGN.md and put it under docs folder

### Changes Overview

- Merged root `DESIGN.md` (tokens, typography, layout) with `docs/DESIGN.md`
  (console mapping, principles) into single `docs/DESIGN.md`
- Deleted root `DESIGN.md`
- Updated links in AGENTS.md, README.md, and docs/*

### Design Intent

Align with `doc.md` relocation: product stays at root (`PRODUCT.md`), visual
system lives in `docs/DESIGN.md`. Impeccable `context.mjs` resolves
`docs/DESIGN.md` via its `docs/` fallback path.

### Files Modified

- `docs/DESIGN.md` (canonical)
- `DESIGN.md` (deleted)
- `AGENTS.md`, `README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`,
  `docs/FRONTEND.md`, `docs/REPO_COLLAB_GUIDE.md`, `docs/QUALITY_SCORE.md`,
  `docs/PRODUCT_SENSE.md`, `docs/design-docs/index.md`, `docs/doc.md`
