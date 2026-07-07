# Tech Debt Tracker

Known debt that is real enough to preserve but not urgent enough to block the
current task.

| Date | Area | Debt | Why It Exists | Planned Follow-Up |
| --- | --- | --- | --- | --- |
| 2026-07-07 | Layout | Flat root packages + `app/` HTTP layer with conftest import aliases | Historical growth before `app/` refactor | Finish refactor; document in ARCHITECTURE.md |
| 2026-07-07 | Executor | Read-only tools (`read_file`, `list_dir`) | Safe default for early harness | Add sandboxed write/patch tools |
| 2026-07-07 | Infra | No Docker Compose or CI | Deferred to focus on core loop | Add compose stack + GitHub Actions pytest gate |
| 2026-07-07 | Security | Open API routes | Localhost dev assumption | Auth middleware + rate limiting |
| 2026-07-07 | Frontend | Vite dev server separate from API | Fast iteration | Optional static mount or unified deploy |
| 2026-07-07 | Ops | No `Makefile` / `scripts/` from upstream template | Scaffolding added in docs pass only | Port `init-project`, `new-history`, `new-plan` scripts |
