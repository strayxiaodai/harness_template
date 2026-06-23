import { useEffect, useRef } from 'react'
import type { TimelineStep } from '../types/api'
import './TraceTimeline.css'

interface TraceTimelineProps {
  steps: TimelineStep[]
  selectedId: string | null
  activeNode: string | null
  onSelect: (id: string) => void
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function TraceTimeline({
  steps,
  selectedId,
  activeNode,
  onSelect,
}: TraceTimelineProps) {
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    if (!selectedId || !listRef.current) {
      return
    }
    const row = listRef.current.querySelector(
      `[data-step-id="${selectedId}"]`,
    )
    row?.scrollIntoView({ block: 'nearest' })
  }, [selectedId, steps.length])

  return (
    <section className="trace-timeline panel" aria-label="Trace timeline">
      <h2 className="panel-title">Trace timeline</h2>
      {steps.length === 0 ? (
        <p className="empty-state">
          No steps yet — start a thread or run a saved skill.
        </p>
      ) : (
        <ul ref={listRef} className="trace-timeline__list">
          {steps.map((step) => {
            const isSelected = step.id === selectedId
            const isLive = step.node === activeNode
            const preview = previewForStep(step)
            return (
              <li key={step.id} data-step-id={step.id}>
                <button
                  type="button"
                  className={`trace-row ${
                    isSelected ? 'trace-row--selected' : ''
                  } ${isLive ? 'trace-row--live' : ''}`}
                  onClick={() => onSelect(step.id)}
                  aria-pressed={isSelected}
                  aria-label={`${step.node} at ${formatTime(step.timestamp)}, ${step.source}${isLive ? ', running' : ''}. ${preview}`}
                >
                  <span className="trace-row__lane mono">{step.node}</span>
                  <span className="trace-row__meta">
                    {formatTime(step.timestamp)} · {step.source}
                  </span>
                  <span className="trace-row__preview mono">
                    {previewForStep(step)}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function previewForStep(step: TimelineStep): string {
  const s = step.state
  if (s.execution?.summary) {
    return s.execution.summary.slice(0, 120)
  }
  if (s.review?.verdict) {
    return `review: ${s.review.verdict} — ${s.review.reason}`.slice(0, 120)
  }
  if (s.plan?.length) {
    return `plan: ${s.plan.length} steps`
  }
  if (s.result) {
    return s.result.slice(0, 120)
  }
  if (s.role) {
    return `role: ${s.role}`
  }
  return '—'
}
