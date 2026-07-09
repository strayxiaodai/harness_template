## [2026-07-09 00:25] | Task: Rename REFERENCE.md to IMPLEMENTATION.md

### User Query

> It is fine, we can call docs/REFERENCE.md as implementation.md with capital

### Changes Overview

- Renamed `docs/REFERENCE.md` → `docs/IMPLEMENTATION.md`
- Updated title and intro to "as-built implementation guide"
- Updated links across AGENTS.md, README.md, docs/*, config, tests

### Design Intent

`IMPLEMENTATION.md` signals documented **as-built behavior**, distinct from
`docs/references/` (external link index) and future spec work. Product/design
docs (`PRODUCT.md`, `DESIGN.md`) remain separate.

### Files Modified

- `docs/IMPLEMENTATION.md` (renamed)
- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `config/settings.yaml`
- `tests/test_rag_tools.py`, `docs/README.md`, and cross-linked docs
