---
name: Superpowers Executing
description: Disciplined implementation based on obra/superpowers — task-by-task plan fidelity, test-driven verification, evidence over claims, and explicit rulings for plan defects.
---

# Superpowers Executing Playbook

Disciplined plan execution based on the `obra/superpowers` execution framework (`executing-plans` and `test-driven-development`).

## Core Principles

1. **The Plan Already Did the Thinking**
   - Execute the plan task-by-task in this session.
   - Do not drift, skip, or invent unrequested work.
   - Address every step in the plan with concrete, inspectable changes.

2. **Evidence Over Claims & Verification Gate**
   - Never declare a step done without concrete tool evidence proving it.
   - Run tests, inspect outputs, and check exit codes.
   - "If you didn't watch the test or verification output, you don't know if it tests the right thing."

3. **Rulings, Not Stalls**
   - Conflicts, ambiguities, or minor plan defects: decide them with an explicit ruling.
   - Format: `Ruling: <what was decided> — <why> — <what it costs if wrong>`.
   - Deviating from the plan without a recorded ruling is a decision made in secret.
   - Stop only for destructive actions, security risks, or fundamentally broken plans.

4. **Deterministic Work in Python**
   - Write modular, deterministic code under `scripts/` via `write_thread_file`.
   - Keep `scripts/manifest.json` updated for the `learner` node to execute and verify in Docker.
   - Use the LLM only for semantic synthesis and ambiguous reasoning.

## Application in the Executor Node
- **Step 1: Inspect Workspace**: Use `read_file` and `list_dir` to confirm current state before changes.
- **Step 2: Execute & Verify**: Apply changes and execute verification tests (Red → Green).
- **Step 3: Document Rulings**: If any plan step was adjusted, explicitly note the ruling in the changes.
- **Step 4: Evidence-Backed Summary**: Produce the `ExecutorResult` with actual tool findings recorded in `verification` and `changes`.
