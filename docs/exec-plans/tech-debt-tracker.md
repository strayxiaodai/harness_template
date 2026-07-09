# Tech Debt Tracker

Known debt preserved for planning. Not urgent enough to block current tasks.

| Date | Area | Debt | Why it exists | Planned follow-up |
| --- | --- | --- | --- | --- |
| 2026-07-07 | Layout | Flat root packages + `app/` HTTP; conftest import aliases | Historical growth | Finish `app/` refactor; simplify imports |
| 2026-07-07 | Executor | Read-only tools | Safe default | Sandboxed write/patch tools |
| 2026-07-07 | Infra | No Docker Compose or CI | Core loop first | Compose + GitHub Actions (see `CICD.md`) |
| 2026-07-07 | Security | Open API routes | Localhost dev | Auth + rate limiting |
| 2026-07-07 | Frontend | Vite separate from API | Fast iteration | Static mount or unified deploy |
| 2026-07-07 | Ops | No `Makefile` / `scripts/` | Docs-only scaffold | Port upstream harness scripts |
| 2026-07-09 | Docs | `REFERENCE.md` renamed to `IMPLEMENTATION.md` | Clarify as-built vs spec/references | — |
| 2026-07-08 | Observability | No `logging_config.py` | Per-module loggers | Central config + `thread_id` in format |
| 2026-07-08 | API | No thread list endpoint | Console uses manual `thread_id` | `GET /threads` with checkpoint metadata |
| 2026-07-08 | UI tests | No Playwright/Vitest e2e | Manual browser verify | Add minimal e2e for run/resume |

Add rows when deferring work intentionally. Link active plans in
[`exec-plans/active/`](active/).
