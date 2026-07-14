# Frontend Guide

Harness developer console under `app/frontend/`. Built as an **instrument
panel** for the graph loop — not a chat UI. See [`PRODUCT.md`](PRODUCT.md)
and [`DESIGN.md`](DESIGN.md).

## Stack

| Piece | Location |
| --- | --- |
| React 19 + TypeScript | `src/` |
| Vite 8 dev server | port `5173` |
| Design tokens | `src/styles/tokens.css` |
| API client | `src/lib/api.ts` |
| Console state machine | `src/hooks/useConsole.ts` |
| Thread library list | `src/hooks/useThreads.ts` |

## Local Development

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd app/frontend
npm install
npm run dev
# → http://localhost:5173
```

### API proxy

Vite rewrites `/api/*` → `http://127.0.0.1:8000/*`:

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}
```

Frontend calls `fetch('/api/run')`; FastAPI sees `POST /run`.

**Example — verify proxy:**

```bash
curl -s http://localhost:5173/api/health
# {"status":"ok"}
```

CORS on the API allows `localhost:5173` for direct calls; the proxy avoids CORS
during normal dev.

## Build And Lint

```bash
cd app/frontend
npm run lint      # ESLint
npm run build     # tsc + vite build
npm run preview   # serve production build locally
```

## Layout (three-column shell)

From [`DESIGN.md`](DESIGN.md): inspector rail · `CenterColumn` · command bar.
`StatusBar` spans the top; footer holds keyboard shortcuts. On desktop
(≥1024px), drag the vertical handles between columns to resize inspector and
command when the inspector rail is open; widths persist in `localStorage`
(`harness.console.columnWidths`). Double-click a handle to reset.

```text
┌──────────────────────────────────────────────────────────┐
│ StatusBar — health, thread picker, rounds                │
├──────────────┬─┬───────────────────────┬─┬───────────────┤
│ Inspector    │⁞│ GraphSpine            │⁞│ CommandColumn │
│  rail        │ │ Workplace (flex)      │ │  control bar  │
│  (≈280px)    │ │ TraceTimeline drawer  │ │  (≈268px)     │
├──────────────┴─┴───────────────────────┴─┴───────────────┤
│ Footer shortcuts                                         │
└──────────────────────────────────────────────────────────┘
```

Narrow (&lt;1024px): spine → workplace → timeline drawer → inspector → command.

## Components

| Component | Role | Key hooks / data |
| --- | --- | --- |
| `ColumnSplit` | Drag handles to resize inspector / command | `useResizableColumns` |
| `CenterColumn` | Spine + workplace + timeline drawer shell | `timelineOpen`, `useResumeDraft` |
| `Workplace` | Clarification / action-review HITL, step payloads, or phase-aware status (ready / running / paused / complete / error) | `phase`, `activeNode`, `interrupt`, `selectedStep`, `useResumeDraft` |
| `CommandColumn` | Thin control bar: task, run, skills, HITL toggle, secondary Continue | `useConsole`, `useSkills` |
| `GraphSpine` | Four nodes: planner → executor → learner → actioner | `GRAPH_NODES`, `completedNodes`, `activeNode` |
| `TraceTimeline` | Bottom drawer; collapsed by default; chronological steps | `timeline`, `selectStep`, `timelineOpen` |
| `InspectorStack` | Collapsible rail; secondary RAG/audit when open | `mode="secondary"`, `collapsed`, `memory_context` |
| `StatusBar` | API health, thread attach picker, round counter | `useHealth`, `useThreads`, `runResponse` |

The frontend talks to the API only — no LangGraph or Python imports.

## API ↔ UI Data Flow

**Run (auto mode):**

```text
CommandColumn [Run]
  → postStreamRun() or postRun()
  → SSE chunks update timeline + accumulated state
  → final RunResponse → StatusBar (rounds, skill_eligible)
```

**HITL mode:**

```text
Run with human_in_the_loop: true
  → stream pauses when status === "awaiting_human"
  → GraphSpine shows next_action as pending
  → clarification: Workplace shows questions + primary Continue; inspector auto-collapses
  → action_review: Workplace shows editable memory candidates + score context
  → command bar shows secondary Continue only (no question list)
  → [Continue] (either surface) → postResume()
```

For `action_review`, `useResumeDraft` seeds one editable row per pending memory
from `interrupt.value.memories`. Continue sends
`interrupt_resume: { memories: [...] }`, where each row can keep, drop, or edit
content, `memory_type`, and `importance`. The Command column keeps Distill /
skill preview controls; the Workplace only notes when `skill_preview_ready` is
true.

**Skill workflow:**

```text
List skills     → GET /api/skills
Run with skill  → POST /api/run { skill_slug }
Distill preview → POST /api/skills/distill { save: false }
Save skill      → POST /api/skills/save
```

**Thread attach (recovery):**

```text
List threads → GET /api/threads  (from app/threads/ index + meta)
Pick in StatusBar → attachThread: set thread_id + Task + Plan
  (does not rebuild timeline or call /resume)
Continue / Distill → existing /resume and /skills paths when checkpoint exists
```

**Example — skill eligibility in UI:**

`RunResponse.skill_eligible === false` shows `skill_ineligible_reason` in the
command column (e.g. "Loop quality score must be at least 80…"). Logic mirrored
in `src/lib/skillEligibility.ts`.

## Type Alignment

TypeScript types in `src/types/api.ts` mirror backend Pydantic models in
`app/schemas/`. When API schemas change, update both sides and
[`IMPLEMENTATION.md`](IMPLEMENTATION.md).

**Example — shared shape:**

```typescript
interface RunResponse {
  status: 'complete' | 'awaiting_human'
  skill_eligible: boolean
  skill_ineligible_reason: string | null
  interrupt?: InterruptPayload | null
  // ...
}
```

## Design System

- Tokens: `src/styles/tokens.css` (must match [`DESIGN.md`](DESIGN.md) OKLCH palette)
- **Cyan** — active node / primary actions
- **Amber** — HITL interrupt / warnings only
- Monospace for JSON payloads in inspector panels

## Keyboard And Accessibility

Target WCAG 2.1 AA per product spec:

- Run, resume, and step selection keyboard-operable
- Visible focus rings (`--focus-ring` token)
- `prefers-reduced-motion` respected in `App.css`

## Testing Strategy

| Check | Command |
| --- | --- |
| Lint | `npm run lint` |
| Typecheck + build | `npm run build` |
| Manual smoke | Run + HITL resume against local API |
| Automated UI tests | Not implemented yet |

**Example — PR frontend gate:**

```bash
cd app/frontend && npm run lint && npm run build
```

## Known Gaps

| Gap | Workaround |
| --- | --- |
| Frontend not served by FastAPI | Run Vite dev server alongside API |
| Attach-only thread list | StatusBar picks `GET /threads`; fills Task/Plan; no checkpoint hydrate |
| No audit panel | Postgres audit not exposed via HTTP yet |
| SSE only during active stream | Use curl `/stream` for headless debugging |

See [`exec-plans/tech-debt-tracker.md`](exec-plans/tech-debt-tracker.md).
