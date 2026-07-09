# Product Sense

Tradeoff heuristics for agents and contributors. Full product spec: [`PRODUCT.md`](PRODUCT.md).

## Who We Optimize For

Solo developers running the harness locally: API on `:8000`, optional console on
`:5173`, terminal nearby. Success = **control and clarity** over the graph loop.

## Decision Heuristics

When choosing between implementations, prefer options that:

1. **Expose graph state** — inspectable plans, tools, reviews, RAG recall
2. **Treat HITL as normal** — resume and override are primary controls
3. **Stay local-first honest** — signal when Postgres audit or MCP is unavailable
4. **Resist chat-app patterns** — graph spine over message bubbles
5. **Favor operator competence** — instrument panel, not marketing polish

## Quality Priority

```text
1. Control and clarity
2. Payload visibility
3. Local dev simplicity (SQLite default)
4. Harness loop throughput (rounds, skills)
5. Visual polish within instrument aesthetic
```

## Example Tradeoffs

| Choice | Prefer | Avoid |
| --- | --- | --- |
| Show run status | Structured panels with node role + rounds | Single "assistant" stream |
| Skill save gate | Require loop score ≥ 80 + completed round | Save on any partial run |
| Error display | StatusBar + inline reason from API | Toast-only dismissal |
| Trace view | Timeline per graph node | Generic nested span tree |
| Default tools | Read-only `read_file`, `list_dir` | Shell execution without sandbox |

## Early vs Mature

| Early (now) | Mature (target) |
| --- | --- |
| Manual `thread_id` | Thread list + search |
| Vite + API two-process dev | Single deployable unit |
| Read-only executor | Sandboxed write/patch tools |
| Manual pytest | CI gate on every PR |
| File-based skills | Registry with versioning |

## Anti-References (from product spec)

Do not drift toward:

- LangSmith / Langfuse trace-viewer UX
- Centered chat bubble primary surface
- Marketing-dashboard SaaS chrome on app screens

## Related

- Visual rules: [`DESIGN.md`](DESIGN.md)
- API behavior: [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
- Console implementation: [`FRONTEND.md`](FRONTEND.md)
