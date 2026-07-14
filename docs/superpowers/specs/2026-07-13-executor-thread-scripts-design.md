# Executor thread scripts + Docker-sandboxed learner runs

Date: 2026-07-13  
Status: approved for planning  
Surface: executor tools + prompts; learner tool loop; Docker S2 runner; `app/threads/`  
Related:

- [`2026-07-13-thread-run-skills-design.md`](2026-07-13-thread-run-skills-design.md) (`app/threads/<task-slug>/` artifacts)
- [`2026-07-13-learner-actioner-loop-design.md`](2026-07-13-learner-actioner-loop-design.md) (learner stage)
- [`SECURITY.md`](../../SECURITY.md) (tool surface)
- [`PRODUCT_SENSE.md`](../../PRODUCT_SENSE.md) (no unsandboxed shell)

## Problem

1. The executor is **read-only** (`read_file`, `list_dir`). It can reason about
   deterministic work but cannot materialize reusable Python helpers under the
   thread workspace.
2. Deterministic logic is often left to LLM reasoning even when Python would be
   cheaper, more reliable, and testable.
3. The learner reviews executor claims without **executable evidence** from
   scripts the executor authored.
4. Any future “promote scripts into skills” path (phase D) needs a **safe
   write + run contract** before distillation.

## Goals

1. Executor can **write** scripts under `app/threads/<task-slug>/scripts/`.
2. Always-on executor system guidance: prefer Python for deterministic work;
   leave semantic/ambiguous work to the LLM (Deterministic / LLM / Hybrid).
3. Executor maintains `scripts/manifest.json` as the allowlist contract.
4. Learner runs a **bounded tool loop** and may call `run_thread_script` only
   for manifest-listed `.py` files.
5. Script execution uses **Docker S2** isolation (no host-Python fallback).
6. Document phase D (summarize into `app/skills/`) as an explicit follow-up;
   do not implement distill in this change.

## Non-goals

- Workspace-wide `write_file` / repo mutation tools.
- Host subprocess execution of thread scripts (S0/S1 as production path).
- Bubblewrap / Podman as the v1 runtime.
- Auto-run-before-learner graph node (rejected; Approach 2 — learner tool).
- Distilling thread scripts into `app/skills/<slug>/` companion modules (phase D).
- Executing arbitrary shell, network installs, or non-manifest paths.
- Changing planner / actioner topology or HITL pause set.

## Decisions

| Decision | Choice |
| --- | --- |
| Primary ship | Phase B: persist scripts under thread dir |
| Later | Phase D: summarize into `app/skills` when approved |
| Write root | Thread dir via existing index; **writes allowed only under `scripts/`** |
| Scripts subtree | `scripts/` + `scripts/manifest.json` |
| Executor run | No — write only |
| Learner run | Yes — `run_thread_script` tool |
| Manifest role | Allowlist of runnable relative `.py` paths (+ purpose, optional args) |
| Architect prompt | Always-on in `executor.system` |
| Isolation | S2 Docker |
| Docker miss | Hard-fail tool (no silent host fallback); tests mock runner |
| Graph topology | Unchanged; no new node |
| Approach | Learner owns tool loop (Approach 2) |

## Architecture

```text
planner → executor → learner → actioner
              │           │
              │           └─ tool: run_thread_script → Docker S2
              └─ tool: write_thread_file → app/threads/<slug>/scripts/
```

### Stage ownership

| Stage | Role |
| --- | --- |
| Executor | Classify Deterministic / LLM / Hybrid; write modules; update manifest; no execute |
| Learner | Challenge result using Docker run evidence from `run_thread_script`; emit `LearningResult` |
| Actioner | Unchanged. Phase D (later): on distill, copy/summarize scripts into skill pack |

### Path resolution

All thread file tools resolve:

```text
thread_id → app/threads/.index.json → <task-slug> → app/threads/<task-slug>/
```

Any resolved path that is not relative to that thread directory raises.

## Thread layout

Extends existing thread artifacts:

```text
app/threads/<task-slug>/
  meta.json
  planner.md
  executor.md
  learner.md
  actioner.md
  scripts/
    manifest.json
    *.py
```

### Manifest schema

```json
{
  "entries": [
    {
      "path": "validate_invariants.py",
      "purpose": "Assert plan step invariants from stdin/fixtures",
      "args": []
    }
  ]
}
```

Rules:

- `path` is relative to `scripts/` only; must end with `.py`; no `..` segments.
- File must exist under `scripts/` before it is runnable.
- `args` is an optional list of strings (no shell interpolation).
- Unknown keys ignored; missing `entries` treated as empty (nothing runnable).

## Tools

### Executor

| Tool | Default allow-list | Behavior |
| --- | --- | --- |
| `write_thread_file` | Yes (with this feature) | Write/overwrite under `scripts/` only (`.py` or `manifest.json`); create parents; size cap |
| `read_thread_file` | Yes | Read text under thread dir (cap same order as `read_file`) |
| `read_file` / `list_dir` | Unchanged | Workspace read for repo context |

`EXECUTOR_TOOLS` default becomes:

```text
read_file,list_dir,write_thread_file,read_thread_file
```

Implementation notes:

- Reuse `lookup_thread_dir(thread_id)` from `app/services/thread_artifacts.py`.
- Pass `thread_id` from agent state into tool args via closure/partial binding
  (tools must not trust model-supplied thread ids if avoidable — bind from state).
- Max file size: 128 KiB (align with `read_file` upper bound).
- Reject writes outside `scripts/`; allow only `*.py` and `manifest.json`;
  reject symlink escapes.

### Learner

Mirror the executor’s bounded tool-loop pattern (`MAX_TOOL_ITERATIONS`, default 5):

1. System + human context (task, plan, execution, tool_calls, list of manifest entries).
2. Optional tool calls.
3. Structured `LearningResult` summarize pass (separate LLM instance from tool binding).

| Tool | Allow-list | Behavior |
| --- | --- | --- |
| `run_thread_script` | Learner-only | Run one manifest entry via Docker S2; return exit/stdout/stderr (truncated) |
| `read_thread_file` | Learner-only (optional) | Inspect script sources if needed |

Learner does **not** get `write_thread_file`.

Compact learner tool records go in state key `learner_tool_calls` (same
`ToolCallRecord` shape as executor). Audit events also set `node: "learner"`.

## Docker S2 runner

Module responsibility (suggested): `tools/sandbox_docker.py` (or
`harness_sandbox/docker.py`) called only by `run_thread_script`.

### Invoke contract

```text
docker run --rm \
  --network=none \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --memory=256m \
  --cpus=1 \
  --workdir /workspace \
  -v <abs-thread-scripts>:/workspace:ro \
  <HARNESS_SCRIPT_IMAGE> \
  python <path> <args...>
```

Defaults:

| Knob | Default | Env override |
| --- | --- | --- |
| Image | `python:3.12-slim` (pin digest in docs/ops) | `HARNESS_SCRIPT_IMAGE` |
| Timeout | 30s | `HARNESS_SCRIPT_TIMEOUT_SECONDS` |
| Stdout/stderr cap | 32 KiB each | `HARNESS_SCRIPT_OUTPUT_BYTES` |
| Docker binary | `docker` | `HARNESS_DOCKER_BIN` |

### Failure modes

| Condition | Tool result |
| --- | --- |
| Docker CLI missing / daemon down | `status=error`, message explains Docker required |
| Path not in manifest | Permission / validation error |
| Non-`.py` or path escape | Validation error |
| Timeout | `status=error`, `exit_code=null`, note timeout |
| Non-zero exit | `status=ok` with exit code + streams (learner judges) |

Tests **mock** the runner; CI unit tests do not require Docker. Optional
integration marker (`@pytest.mark.docker`) for real daemon runs.

## Prompts

### `executor.system` (always-on)

Extend with the architect principles (condensed, production tone):

- Analyze the plan; prefer Python when a deterministic algorithm with known
  rules exists.
- Classify work Deterministic / LLM / Hybrid; minimize LLM-only work.
- For Deterministic/Hybrid: write modular Python under `scripts/`, define
  inputs/outputs, update `manifest.json` for anything the learner should run.
- Do not duplicate logic already expressible as code; do not execute scripts
  yourself.
- Keep using workspace `read_file` / `list_dir` for repo context when needed.

### `learner.system`

- Challenge correctness using script run evidence when available.
- Prefer calling `run_thread_script` for relevant manifest entries before
  final verdict when scripts exist.
- Treat sandbox errors (Docker unavailable) as verification gaps, not as
  automatic pass.

## State / API / artifacts

| Item | Change |
| --- | --- |
| Graph edges | None |
| HITL pauses | Unchanged (`planner`, `executor`, `learner`) |
| `AgentState` | Optional `learner_tool_calls`; optional `script_runs` summary for UI |
| Stage markdown | Include learner tool / script run notes in `learner.md` payload when present |
| `RunResponse` | Surface compact script-run summary only if already exposing stage fields; no new public route required for v1 |
| Audit | `tool_call` events for executor writes and learner runs (`node` field set) |

## Security

| Threat | Mitigation |
| --- | --- |
| Path escape | Resolve + `is_relative_to(thread_dir)` |
| Arbitrary code on host | Docker only; no host Python fallback |
| Network exfil from script | `--network=none` |
| Priv-esc in container | `--cap-drop=ALL`, `no-new-privileges`, read-only root |
| Resource abuse | memory/cpu limits, timeout, output caps |
| Manifest spoof mid-run | Re-read manifest at run time; path must be listed |
| Model-supplied thread_id | Bind thread dir from graph state, not tool args |

Update [`docs/SECURITY.md`](../../SECURITY.md) and
[`docs/IMPLEMENTATION.md`](../../IMPLEMENTATION.md) in the same
implementation change.

## Phase D (follow-up, not in this ship)

When a thread is approved / distilled:

1. Read `app/threads/<slug>/scripts/` (+ manifest).
2. Summarize into `app/skills/<skill-slug>/` as companion modules + playbook
   references (Deterministic modules stay Python; LLM steps stay in markdown).
3. Reuse the same architect bias: do not re-LLM what is already coded.

This design only ensures B produces clean inputs for D.

## Testing

| Area | Cases |
| --- | --- |
| `write_thread_file` | Happy path; escape rejected; size cap; creates `scripts/` |
| Manifest | Invalid path rejected by runner; missing file; empty entries |
| `run_thread_script` | Mock Docker: success, non-zero exit, timeout, daemon missing |
| Learner loop | Calls tool then structured output; no write tool bound |
| Executor prompt | Config loads new system text (smoke) |
| Registry | Default allow-list includes new executor tools; learner registry separate |

## Rollout

1. Implement thread file tools + prompt updates (executor write path usable
   without Docker).
2. Implement Docker runner + learner tool loop.
3. Docs + SECURITY allow-list tables.
4. Optional docker integration test behind marker.

Operator requirements for full verify path: Docker daemon available locally or
in the deployment environment.
