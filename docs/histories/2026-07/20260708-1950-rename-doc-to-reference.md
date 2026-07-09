## [2026-07-08 19:50] | Task: Rename doc.md to REFERENCE.md

### User Query

> Rename doc.md, since it is so general

### Changes Overview

- Renamed `docs/doc.md` → `docs/REFERENCE.md`
- Updated links across AGENTS.md, README.md, CONTRIBUTING.md, docs/*, config,
  and tests
- Updated `docs/README.md` naming conventions table

### Design Intent

`REFERENCE.md` matches the document title ("Technical Reference") and the
`UPPER_SNAKE.md` convention used by other top-level docs. History archives keep
the old `doc.md` name as historical record.

### Files Modified

- `docs/REFERENCE.md` (renamed from `doc.md`)
- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `config/settings.yaml`
- `tests/test_rag_tools.py`
- `docs/README.md`, `docs/ARCHITECTURE.md`, and other cross-linked docs
