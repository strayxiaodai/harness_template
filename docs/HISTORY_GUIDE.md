# Change History Guide

Record finished **code-change** tasks in `docs/histories/`. Pure Q&A or analysis
without repo changes does not need an entry.

## Requirements

- One history file per completed code-change task
- Concise user request (redact secrets and local paths)
- Main code + doc changes, design intent, key files
- Multi-round tasks: update the same file, do not duplicate

## Layout And Naming

```text
docs/histories/
  YYYY-MM/
    YYYYMMDD-HHmm-task-slug.md
```

Template: [`template.md`](template.md)

**Example:**

```text
docs/histories/2026-07/20260708-1930-refine-docs-folder.md
```

## What To Include

```markdown
## [2026-07-08 19:30] | Task: Short title

### User Query
> Redacted or summarized request

### Changes Overview
- Area: ...
- Key actions: ...

### Design Intent
Why this approach; tradeoffs chosen

### Files Modified
- `path/to/file`
```

## Redaction Rules

| Do not record | Instead |
| --- | --- |
| API keys, tokens | `OPENAI_API_KEY=***` |
| `/Users/...` paths | `harness_template/agent/` |
| Private Slack context | Summarize decision only |

## Related

- Collaboration norms: [`REPO_COLLAB_GUIDE.md`](../REPO_COLLAB_GUIDE.md)
- Release notes (user-visible): [`releases/README.md`](../releases/README.md)
