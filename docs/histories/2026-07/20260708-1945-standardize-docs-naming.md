## [2026-07-08 19:45] | Task: Standardize docs/ file naming

### User Query

> Recheck the naming under folder of docs, refine them if needed

### Changes Overview

- Renamed `docs/asyncio.md` → `docs/ASYNCIO.md`
- Renamed `docs/langgraph.md` → `docs/LANGGRAPH.md`
- Added **File Naming** section to `docs/README.md` documenting conventions
- Updated cross-links in ARCHITECTURE, RELIABILITY, references, doc.md, etc.

### Design Intent

Top-level topical docs use `UPPER_SNAKE.md` (`ARCHITECTURE.md`, `FRONTEND.md`,
…). `asyncio.md` and `langgraph.md` were lowercase outliers. `doc.md` stays
lowercase as the established technical encyclopedia anchor (high reference
count, RAG fixtures). Process meta-docs keep the `*_GUIDE.md` suffix.

### Files Modified

- `docs/ASYNCIO.md`, `docs/LANGGRAPH.md` (renamed)
- `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/RELIABILITY.md`
- `docs/references/README.md`, `docs/design-docs/core-beliefs.md`, `docs/doc.md`
