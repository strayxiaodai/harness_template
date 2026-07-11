# Center Workplace + Timeline Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the center column the primary workplace (clarification or step payloads), dock Trace timeline as a bottom drawer, keep Command as a thin control bar with secondary Continue, and collapse the Inspector to a rail during clarification.

**Architecture:** Introduce `CenterColumn` (GraphSpine + `Workplace` + drawer `TraceTimeline`) and wire it from `App`. Lift resume draft state (answers + overrides) into a small hook so Workplace (primary Continue) and Command (secondary Continue) share drafts. Inspector gains collapse rail mode; primary plan/tools/review render in Workplace when a step is selected.

**Tech Stack:** React 19 + Vite + existing CSS tokens. No new dependencies. Verification: `cd app/frontend && npm run build` + browser smoke (no frontend unit-test runner).

**Spec:** [`docs/superpowers/specs/2026-07-11-center-workplace-timeline-drawer-design.md`](../specs/2026-07-11-center-workplace-timeline-drawer-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `app/frontend/src/hooks/useResumeDraft.ts` | Shared plan/refine overrides + clarification answer drafts |
| `app/frontend/src/lib/clarification.ts` | `clarificationQuestions(interrupt)` helper (extracted from CommandColumn) |
| `app/frontend/src/components/Workplace.tsx` + `.css` | Center workplace: clarification XOR step payloads XOR idle |
| `app/frontend/src/components/CenterColumn.tsx` + `.css` | Spine + Workplace + timeline drawer layout |
| `app/frontend/src/components/TraceTimeline.tsx` + `.css` | Collapsed bar / expanded drawer |
| `app/frontend/src/components/CommandColumn.tsx` | Remove clarification form; secondary Continue + shared overrides |
| `app/frontend/src/components/InspectorStack.tsx` + `.css` | Rail collapse; secondary-only (RAG/audit/skill) |
| `app/frontend/src/App.tsx` + `App.css` | Compose CenterColumn; inspector collapse; grid areas |
| `docs/DESIGN.md`, `docs/FRONTEND.md` | Layout map |
| `docs/histories/2026-07/…` | History after code lands |

---

### Task 1: Extract clarification helper + resume draft hook

**Files:**
- Create: `app/frontend/src/lib/clarification.ts`
- Create: `app/frontend/src/hooks/useResumeDraft.ts`
- Modify: `app/frontend/src/components/CommandColumn.tsx` (import helper; wire to hook props later in Task 4)

- [ ] **Step 1: Add `clarificationQuestions` helper**

```ts
// app/frontend/src/lib/clarification.ts
import type {
  ClarificationQuestion,
  InterruptPayload,
} from '../types/api'

export function clarificationQuestions(
  interrupt: InterruptPayload | null,
): ClarificationQuestion[] {
  const value = interrupt?.value
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return []
  }
  const record = value as Record<string, unknown>
  if (record.kind !== 'clarification') {
    return []
  }
  const questions = record.questions
  if (!Array.isArray(questions)) {
    return []
  }
  return questions.filter(
    (q): q is ClarificationQuestion =>
      typeof q === 'object' &&
      q !== null &&
      typeof (q as ClarificationQuestion).id === 'string' &&
      typeof (q as ClarificationQuestion).prompt === 'string',
  )
}

export function clarificationReason(
  interrupt: InterruptPayload | null,
): string {
  const value = interrupt?.value
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return ''
  }
  return String((value as Record<string, unknown>).reason ?? '')
}

export function isClarificationInterrupt(
  interrupt: InterruptPayload | null,
): boolean {
  return clarificationQuestions(interrupt).length > 0
}
```

- [ ] **Step 2: Add `useResumeDraft`**

```ts
// app/frontend/src/hooks/useResumeDraft.ts
import { useEffect, useState } from 'react'
import type {
  ClarificationAnswer,
  InterruptPayload,
  ResumeOverrides,
} from '../types/api'
import { clarificationQuestions } from '../lib/clarification'
import type { RunPhase } from './useConsole'

function parsePlanLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function useResumeDraft(
  phase: RunPhase,
  interrupt: InterruptPayload | null,
) {
  const canResume =
    phase === 'awaiting_human' || phase === 'error'
  const questions = clarificationQuestions(interrupt)

  const [planOverrideText, setPlanOverrideText] = useState('')
  const [refineOverride, setRefineOverride] = useState<
    ResumeOverrides['refine_from'] | ''
  >('')
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>(
    {},
  )

  useEffect(() => {
    if (!canResume) {
      setPlanOverrideText('')
      setRefineOverride('')
      setAnswerDrafts({})
      return
    }
    const next: Record<string, string> = {}
    for (const question of questions) {
      next[question.id] = ''
    }
    setAnswerDrafts(next)
  }, [canResume, interrupt?.id])

  const setAnswer = (id: string, value: string) => {
    setAnswerDrafts((prev) => ({ ...prev, [id]: value }))
  }

  const buildPayload = (): {
    overrides?: ResumeOverrides
    answers?: ClarificationAnswer[]
  } => {
    const overrides: ResumeOverrides = {}
    const plan = parsePlanLines(planOverrideText)
    if (plan.length > 0) {
      overrides.plan = plan
    }
    if (refineOverride) {
      overrides.refine_from = refineOverride
    }
    const answers =
      questions.length > 0
        ? questions
            .map((q) => ({
              question_id: q.id,
              answer: (answerDrafts[q.id] ?? '').trim(),
            }))
            .filter((a) => a.answer.length > 0)
        : undefined
    return {
      overrides:
        Object.keys(overrides).length > 0 ? overrides : undefined,
      answers,
    }
  }

  return {
    canResume,
    questions,
    planOverrideText,
    setPlanOverrideText,
    refineOverride,
    setRefineOverride,
    answerDrafts,
    setAnswer,
    buildPayload,
  }
}
```

- [ ] **Step 3: Build check**

Run: `cd app/frontend && npm run build`  
Expected: PASS (new files unused yet is fine if exported; if unused-import lint fails, temporarily import from CommandColumn only the helper).

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/lib/clarification.ts app/frontend/src/hooks/useResumeDraft.ts
git commit -m "Add shared clarification helper and resume draft hook."
```

---

### Task 2: Workplace component

**Files:**
- Create: `app/frontend/src/components/Workplace.tsx`
- Create: `app/frontend/src/components/Workplace.css`
- Read for payload UI patterns: `app/frontend/src/components/InspectorStack.tsx`

- [ ] **Step 1: Implement `Workplace`**

Priority: clarification → selected step payloads → idle.

```tsx
// app/frontend/src/components/Workplace.tsx
import type {
  ClarificationQuestion,
  InterruptPayload,
  ResumeOverrides,
  TimelineStep,
} from '../types/api'
import type { RunPhase } from '../hooks/useConsole'
import {
  clarificationReason,
  isClarificationInterrupt,
} from '../lib/clarification'
import { formatJson } from '../lib/api'
import './Workplace.css'

interface WorkplaceProps {
  phase: RunPhase
  interrupt: InterruptPayload | null
  selectedStep: TimelineStep | null
  questions: ClarificationQuestion[]
  answerDrafts: Record<string, string>
  onAnswerChange: (id: string, value: string) => void
  planOverrideText: string
  refineOverride: ResumeOverrides['refine_from'] | ''
  onPlanOverrideChange: (value: string) => void
  onRefineOverrideChange: (
    value: ResumeOverrides['refine_from'] | '',
  ) => void
  onContinue: () => void
  streaming: boolean
}

export function Workplace({
  phase,
  interrupt,
  selectedStep,
  questions,
  answerDrafts,
  onAnswerChange,
  planOverrideText,
  refineOverride,
  onPlanOverrideChange,
  onRefineOverrideChange,
  onContinue,
  streaming,
}: WorkplaceProps) {
  const clarifying =
    phase === 'awaiting_human' && isClarificationInterrupt(interrupt)

  if (clarifying) {
    const reason = clarificationReason(interrupt)
    return (
      <section
        className="workplace panel workplace--hitl"
        aria-label="Workplace"
      >
        <h2 className="panel-title">Clarification</h2>
        <div className="workplace__body">
          {reason ? <p className="workplace__reason">{reason}</p> : null}
          {questions.map((q) => (
            <div key={q.id} className="workplace__field">
              <label className="field-label" htmlFor={`wp-clarify-${q.id}`}>
                {q.prompt}
              </label>
              {q.why ? <p className="workplace__hint">{q.why}</p> : null}
              <textarea
                id={`wp-clarify-${q.id}`}
                className="field-textarea"
                rows={3}
                value={answerDrafts[q.id] ?? ''}
                onChange={(e) => onAnswerChange(q.id, e.target.value)}
                placeholder="Your answer"
                disabled={streaming}
              />
            </div>
          ))}
          <details className="workplace__overrides">
            <summary>Overrides before continue</summary>
            {/* same fields as Command OverrideForm: plan textarea + refine select */}
            <label className="field-label" htmlFor="wp-override-plan">
              Replace plan (one step per line)
            </label>
            <textarea
              id="wp-override-plan"
              className="field-textarea"
              rows={3}
              value={planOverrideText}
              onChange={(e) => onPlanOverrideChange(e.target.value)}
              disabled={streaming}
            />
            <label className="field-label" htmlFor="wp-override-refine">
              Refine from (optional)
            </label>
            <select
              id="wp-override-refine"
              className="field-input"
              value={refineOverride}
              onChange={(e) =>
                onRefineOverrideChange(
                  e.target.value as ResumeOverrides['refine_from'] | '',
                )
              }
              disabled={streaming}
            >
              <option value="">No change</option>
              <option value="planner">planner</option>
              <option value="executor">executor</option>
              <option value="finish">finish</option>
            </select>
          </details>
          <button
            type="button"
            className="btn btn-accent"
            onClick={onContinue}
            disabled={streaming}
          >
            Continue
          </button>
        </div>
      </section>
    )
  }

  if (selectedStep) {
    const s = selectedStep.state
    return (
      <section className="workplace panel" aria-label="Workplace">
        <h2 className="panel-title">
          Step · {selectedStep.node}
        </h2>
        <div className="workplace__body workplace__payloads">
          {/* Reuse InspectorStack section patterns: Plan, Execution, Tools, Review */}
          {s.plan?.length ? (
            <div>
              <h3 className="workplace__sub">Plan</h3>
              <ol className="inspector-list">
                {s.plan.map((item, i) => (
                  <li key={`${i}-${item}`}>{item}</li>
                ))}
              </ol>
            </div>
          ) : null}
          {s.execution ? (
            <div>
              <h3 className="workplace__sub">Execution</h3>
              <p className="inspector-prose">{s.execution.summary}</p>
            </div>
          ) : null}
          {s.tool_calls?.length ? (
            <div>
              <h3 className="workplace__sub">Tools</h3>
              <pre className="inspector-json mono">
                {formatJson(s.tool_calls)}
              </pre>
            </div>
          ) : null}
          {s.review ? (
            <div>
              <h3 className="workplace__sub">Review</h3>
              <p className="inspector-prose">
                {s.review.verdict}: {s.review.reason}
              </p>
            </div>
          ) : null}
          {!s.plan?.length &&
            !s.execution &&
            !s.tool_calls?.length &&
            !s.review && (
              <p className="empty-state">No primary payloads on this step.</p>
            )}
        </div>
      </section>
    )
  }

  return (
    <section className="workplace panel" aria-label="Workplace">
      <h2 className="panel-title">Workplace</h2>
      <div className="workplace__idle">
        <p className="empty-state empty-state--centered">
          Ready for a run
        </p>
        <p className="empty-state__hint">
          Start a thread from Command. Clarification and step payloads
          appear here.
        </p>
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Add `Workplace.css`**

```css
.workplace {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.workplace--hitl {
  border-color: color-mix(in oklch, var(--accent) 45%, var(--border));
}

.workplace__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4) var(--space-4);
  overflow: auto;
  min-height: 0;
}

.workplace__idle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 8rem;
  margin: var(--space-2) var(--space-3) var(--space-3);
  padding: var(--space-4);
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: var(--radius-control);
}

.workplace__reason,
.workplace__hint {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--muted);
  white-space: pre-wrap;
}

.workplace__sub {
  margin: 0 0 var(--space-2);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.workplace__payloads {
  gap: var(--space-4);
}
```

- [ ] **Step 3: Build**

Run: `cd app/frontend && npm run build`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/components/Workplace.tsx app/frontend/src/components/Workplace.css
git commit -m "Add center Workplace for clarification and step payloads."
```

---

### Task 3: CenterColumn + timeline drawer

**Files:**
- Create: `app/frontend/src/components/CenterColumn.tsx`
- Create: `app/frontend/src/components/CenterColumn.css`
- Modify: `app/frontend/src/components/TraceTimeline.tsx`
- Modify: `app/frontend/src/components/TraceTimeline.css`

- [ ] **Step 1: Convert TraceTimeline to drawer**

Add props:

```tsx
interface TraceTimelineProps {
  steps: TimelineStep[]
  selectedId: string | null
  activeNode: string | null
  onSelect: (id: string) => void
  expanded: boolean
  onToggle: () => void
}
```

Structure:

```tsx
<section className={`trace-timeline panel ${expanded ? 'trace-timeline--expanded' : 'trace-timeline--collapsed'}`}>
  <button
    type="button"
    className="trace-timeline__toggle"
    aria-expanded={expanded}
    onClick={onToggle}
  >
    <span className="panel-title">Trace timeline</span>
    <span className="trace-timeline__meta mono">
      {steps.length} step{steps.length === 1 ? '' : 's'}
      {activeNode ? ` · ${activeNode}` : ''}
    </span>
    <span aria-hidden="true">{expanded ? '▾' : '▴'}</span>
  </button>
  {expanded && (
    /* existing empty or list */
  )}
</section>
```

CSS: collapsed = single bar (`flex: 0 0 auto`); expanded body `max-height: 220px; overflow: auto`. Remove old `flex: 1` fill-middle behavior.

- [ ] **Step 2: Create CenterColumn**

```tsx
// app/frontend/src/components/CenterColumn.tsx
import { useState } from 'react'
import { GraphSpine } from './GraphSpine'
import { Workplace } from './Workplace'
import { TraceTimeline } from './TraceTimeline'
import type { GraphNode, TimelineStep } from '../types/api'
// ... props for spine + workplace + timeline

export function CenterColumn(props: /* compose */) {
  const [timelineOpen, setTimelineOpen] = useState(false)

  const handleSelect = (id: string) => {
    props.onSelectStep(id)
    setTimelineOpen(true)
  }

  return (
    <div className="center-column">
      <GraphSpine /* ... */ />
      <Workplace /* ... */ />
      <TraceTimeline
        expanded={timelineOpen}
        onToggle={() => setTimelineOpen((v) => !v)}
        onSelect={handleSelect}
        /* ... */
      />
    </div>
  )
}
```

```css
.center-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  min-height: 0;
  grid-area: center;
}
```

- [ ] **Step 3: Open drawer on `j`/`k` from App**

In `App` key handler, after `selectAdjacent`, also set timeline open. Prefer lifting `timelineOpen` state to `App` and passing into `CenterColumn` so keyboard can open the drawer:

```tsx
const [timelineOpen, setTimelineOpen] = useState(false)
// on j/k:
selectAdjacent(1)
setTimelineOpen(true)
```

Pass `timelineOpen` / `setTimelineOpen` into `CenterColumn`.

- [ ] **Step 4: Build + commit**

```bash
cd app/frontend && npm run build
git add app/frontend/src/components/CenterColumn.* app/frontend/src/components/TraceTimeline.*
git commit -m "Add CenterColumn with timeline drawer."
```

---

### Task 4: Wire App shell + Command secondary Continue

**Files:**
- Modify: `app/frontend/src/App.tsx`
- Modify: `app/frontend/src/App.css`
- Modify: `app/frontend/src/components/CommandColumn.tsx`

- [ ] **Step 1: App composition**

```tsx
const draft = useResumeDraft(phase, runResponse?.interrupt ?? null)
const clarifying =
  phase === 'awaiting_human' &&
  isClarificationInterrupt(runResponse?.interrupt ?? null)
const [inspectorOpen, setInspectorOpen] = useState(!clarifying)
// when clarifying becomes true, auto-collapse unless user pinned open:
useEffect(() => {
  if (clarifying) setInspectorOpen(false)
}, [clarifying])

const handleContinue = () => {
  const { overrides, answers } = draft.buildPayload()
  void resume(overrides, answers)
}

<main
  className={`app-main ${inspectorOpen ? '' : 'app-main--inspector-collapsed'}`}
  ...
>
  <InspectorStack
    mode="secondary"
    collapsed={!inspectorOpen && desktop}
    onExpand={() => setInspectorOpen(true)}
    onCollapse={() => setInspectorOpen(false)}
    step={selectedStep}
    accumulated={accumulated}
  />
  {desktop && inspectorOpen && (
    <ColumnSplit side="inspector" ... />
  )}
  <CenterColumn
    /* spine + workplace + timeline props */
    onContinue={handleContinue}
    draft={draft}
  />
  <ColumnSplit side="command" ... />
  <CommandColumn
    /* remove interrupt clarification UI */
    onResume={handleContinue}
    planOverrideText={draft.planOverrideText}
    /* ... shared override props */
    showSecondaryContinue={phase === 'awaiting_human'}
  />
</main>
```

Grid when inspector open (keep splitters):

```css
.app-main {
  grid-template-columns:
    var(--col-inspector, 280px) 8px minmax(0, 1fr) 8px var(--col-command, 268px);
  grid-template-areas:
    "inspector split-l center split-r command"
    "inspector split-l center split-r command";
  /* single row for center column that stacks internally */
  grid-template-rows: minmax(0, 1fr);
}
.app-main--inspector-collapsed {
  grid-template-columns:
    36px minmax(0, 1fr) 8px var(--col-command, 268px);
  grid-template-areas:
    "inspector center split-r command";
}
```

Narrow stack:

```css
grid-template-areas:
  "center"
  "inspector"
  "command";
```

(CenterColumn already stacks spine/workplace/timeline internally.)

- [ ] **Step 2: Slim CommandColumn**

- Delete local `clarificationQuestions`, answer drafts, `ClarificationForm` usage.
- Keep HITL toggle + secondary Continue calling `onResume` (shared handler).
- Keep `OverrideForm` bound to shared draft props from App.
- Import helper only if still needed for nothing — remove.

- [ ] **Step 3: Build + commit**

```bash
cd app/frontend && npm run build
git add app/frontend/src/App.tsx app/frontend/src/App.css app/frontend/src/components/CommandColumn.tsx
git commit -m "Wire CenterColumn shell and secondary Continue in Command."
```

---

### Task 5: Inspector secondary + rail

**Files:**
- Modify: `app/frontend/src/components/InspectorStack.tsx`
- Modify: `app/frontend/src/components/InspectorStack.css`

- [ ] **Step 1: Secondary mode**

When `mode === 'secondary'`:
- Show RAG / audit / skill sections only (keep existing sections for those).
- Do **not** render Plan / Execution / Tools / Review (Workplace owns those).
- Empty secondary: short hint “Secondary context (RAG, audit)”.

When `collapsed`:
- Render a vertical strip button `Inspector ▸` that calls `onExpand`.
- `aria-expanded={false}`.

- [ ] **Step 2: CSS for rail**

```css
.inspector-stack--rail {
  display: flex;
  align-items: stretch;
  justify-content: center;
  min-width: 0;
  padding: var(--space-2) 0;
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  cursor: pointer;
  /* keep panel border */
}
```

- [ ] **Step 3: Build + commit**

```bash
cd app/frontend && npm run build
git add app/frontend/src/components/InspectorStack.*
git commit -m "Make inspector a collapsible secondary rail."
```

---

### Task 6: Docs + history + visual smoke

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `docs/FRONTEND.md`
- Create: `docs/histories/2026-07/20260711-HHMM-center-workplace-timeline-drawer.md`

- [ ] **Step 1: Update DESIGN layout diagram** to CenterColumn + workplace + timeline drawer + inspector rail + dual Continue.

- [ ] **Step 2: Update FRONTEND component map** — add `CenterColumn`, `Workplace`; note timeline drawer; inspector secondary.

- [ ] **Step 3: History entry** per `docs/HISTORY_GUIDE.md`.

- [ ] **Step 4: Visual smoke**

1. Idle desktop: workplace idle hint; timeline collapsed bar; inspector open; command thin.
2. Select step (expand timeline): payloads in workplace; inspector secondary only.
3. Clarification interrupt: workplace amber form + primary Continue; inspector auto-collapsed; command secondary Continue; resume from both.
4. Narrow: center (spine/workplace/drawer) then inspector then command.
5. `j`/`k` opens drawer; `r` continues.

- [ ] **Step 5: `graphify update .`** after code changes.

- [ ] **Step 6: Commit docs**

```bash
git add docs/DESIGN.md docs/FRONTEND.md docs/histories/2026-07/*.md
git commit -m "Document center workplace and timeline drawer layout."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Workplace swap (clarification / payloads / idle) | 2, 4 |
| Command control bar + secondary Continue | 4 |
| Timeline bottom drawer, collapsed default | 3 |
| Inspector collapsible rail, auto-collapse on clarification | 4, 5 |
| Dual Continue shared drafts | 1, 2, 4 |
| `j`/`k` open drawer; `r` resume | 3, 4 |
| DESIGN / FRONTEND | 6 |
| Narrow stack | 4 |

## Self-review notes

- No API changes; interrupt schema unchanged.
- Shared draft hook avoids divergent Continue payloads.
- Primary payloads move to Workplace; inspector secondary avoids duplication.
