## [2026-07-08 19:40] | Task: Move PRODUCT.md to docs/

### User Query

> Can we put PRODUCT.md into docs?

### Changes Overview

- Moved root `PRODUCT.md` to `docs/PRODUCT.md` with links to `PRODUCT_SENSE.md`
  and `DESIGN.md`
- Deleted root `PRODUCT.md`
- Updated harness doc links (AGENTS.md, README.md, docs/*)

### Design Intent

Complete the docs/ consolidation started with `doc.md` and `DESIGN.md`. Both
product and design context now live under `docs/`, which Impeccable `context.mjs`
resolves via its `docs/` fallback directory.

### Files Modified

- `docs/PRODUCT.md` (canonical)
- `PRODUCT.md` (deleted)
- `AGENTS.md`, `README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`,
  `docs/FRONTEND.md`, `docs/DESIGN.md`, `docs/PRODUCT_SENSE.md`,
  `docs/REPO_COLLAB_GUIDE.md`, `docs/QUALITY_SCORE.md`, `docs/doc.md`,
  `docs/design-docs/index.md`
