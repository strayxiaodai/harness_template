## [2026-07-13 23:12] | Task: Thread run artifacts + app/skills

### User Query

> When starting a new thread, create a folder named from Command → Task under
> `app/`, with planner/executor/learner/actioner markdown recording contents and
> status as the run progresses (for pickup and distill). Distilled skills should
> live under `app/skills/`.

### Changes Overview

- Area: harness services, skills store, docs
- Key actions: `app/threads/<slug>/` stage notes on run/stream/resume; default
  skills root → `app/skills/`; gitignore threads; docs sync

### Design Intent

Keep run pickup notes local and task-named without colliding with the Python
package tree (`app/threads/` namespace). Keep distilled playbooks under `app/`
alongside the HTTP app, separate from Cursor agent skills in `.cursor/skills/`.

### Files Modified

- `skills/store.py`
- `app/skills/.gitkeep`
- `app/services/thread_artifacts.py`
- `app/services/harness.py`
- `app/api/skills.py`
- `.gitignore`
- `tests/test_skills_store_root.py`
- `tests/test_thread_artifacts.py`
- `tests/test_harness_thread_artifacts.py`
- `docs/IMPLEMENTATION.md`
- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- `docs/superpowers/specs/2026-07-13-thread-run-artifacts-design.md`
- `docs/superpowers/plans/2026-07-13-thread-run-artifacts.md`
