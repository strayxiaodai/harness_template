# Core Beliefs

These beliefs shape the repository before feature-specific rules exist.

## Agent-First Operating Principles

- Humans steer; agents execute.
- Repository-local knowledge beats private human context.
- The right fix for repeated agent failure is usually better scaffolding, not
  more prompt pressure.
- Short stable entry points are better than large unstable instruction dumps.
- Mechanical checks are preferred over soft conventions whenever feasible.
- Throughput matters, but unmanaged entropy compounds quickly; keep cleanup and
  simplification continuous.

## Harness-Specific Beliefs

- The graph loop (Plan → Do → Check → Action) is the product spine — UI, API,
  and docs should reflect it honestly.
- Checkpoints and audit trails make agent work inspectable and resumable.
- Skills distilled from successful threads are reusable playbooks, not
  replacements for tests and docs.

**Example — agent failure loop:**

```text
Agent keeps misconfiguring CHECKPOINT_BACKEND
→ update IMPLEMENTATION.md + LANGGRAPH.md with explicit examples
→ add test in test_checkpoint_config.py
→ not: add 500 words to AGENTS.md
```
