import type {
  ClarificationQuestion,
  InterruptPayload,
  MemoryResumeRow,
  MemoryType,
  PendingMemory,
  ResumeOverrides,
  TimelineStep,
} from '../types/api'
import type { RunPhase } from '../hooks/useConsole'
import {
  clarificationReason,
  isClarificationInterrupt,
} from '../lib/clarification'
import {
  isActionReviewInterrupt,
} from '../lib/actionReview'
import { formatJson } from '../lib/api'
import './Workplace.css'

const MEMORY_TYPES: MemoryType[] = ['fact', 'preference', 'entity', 'summary']

interface ActionReviewMeta {
  score?: number
  threshold?: number
  skillPreviewReady: boolean
  message: string
}

interface WorkplaceProps {
  phase: RunPhase
  interrupt: InterruptPayload | null
  selectedStep: TimelineStep | null
  questions: ClarificationQuestion[]
  answerDrafts: Record<string, string>
  onAnswerChange: (id: string, value: string) => void
  memories: PendingMemory[]
  memoryDrafts: Record<string, MemoryResumeRow>
  actionReviewMeta: ActionReviewMeta
  onMemoryDraftChange: (id: string, patch: Partial<MemoryResumeRow>) => void
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
  memories,
  memoryDrafts,
  actionReviewMeta,
  onMemoryDraftChange,
  planOverrideText,
  refineOverride,
  onPlanOverrideChange,
  onRefineOverrideChange,
  onContinue,
  streaming,
}: WorkplaceProps) {
  const clarifying =
    phase === 'awaiting_human' && isClarificationInterrupt(interrupt)
  const actionReviewing =
    phase === 'awaiting_human' && isActionReviewInterrupt(interrupt)

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
            <label className="field-label" htmlFor="wp-override-plan">
              Replace plan (one step per line)
            </label>
            <textarea
              id="wp-override-plan"
              className="field-textarea"
              rows={3}
              value={planOverrideText}
              onChange={(e) => onPlanOverrideChange(e.target.value)}
              placeholder="Leave empty to keep current plan"
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
              <option value="finish">finish</option>
            </select>
          </details>
          <button
            type="button"
            className="btn btn-accent"
            onClick={onContinue}
            disabled={streaming}
            aria-keyshortcuts="r"
          >
            Continue
          </button>
        </div>
      </section>
    )
  }

  if (actionReviewing) {
    return (
      <section
        className="workplace panel workplace--hitl"
        aria-label="Workplace"
      >
        <h2 className="panel-title">Action review</h2>
        <div className="workplace__body">
          {actionReviewMeta.message ? (
            <p className="workplace__reason">{actionReviewMeta.message}</p>
          ) : null}
          {actionReviewMeta.score !== undefined ? (
            <p className="workplace__hint">
              Score: {actionReviewMeta.score}
              {actionReviewMeta.skillPreviewReady &&
              actionReviewMeta.threshold !== undefined
                ? ` / threshold ${actionReviewMeta.threshold}`
                : ''}
            </p>
          ) : null}
          {actionReviewMeta.skillPreviewReady ? (
            <p className="workplace__hint">
              Distill / skill preview is available in Command.
            </p>
          ) : null}

          {memories.length > 0 ? (
            <div className="workplace__memory-list" aria-label="Memory drafts">
              {memories.map((memory) => {
                const draft = memoryDrafts[memory.id] ?? {
                  id: memory.id,
                  keep: true,
                  content: memory.content,
                  memory_type: memory.memory_type,
                  importance: memory.importance,
                }
                return (
                  <div key={memory.id} className="workplace__memory-row">
                    <label className="workplace__memory-keep">
                      <input
                        type="checkbox"
                        checked={draft.keep}
                        onChange={(e) =>
                          onMemoryDraftChange(memory.id, {
                            keep: e.target.checked,
                          })
                        }
                        disabled={streaming}
                      />
                      Keep
                    </label>
                    <div className="workplace__field">
                      <label
                        className="field-label"
                        htmlFor={`wp-memory-content-${memory.id}`}
                      >
                        Memory
                      </label>
                      <textarea
                        id={`wp-memory-content-${memory.id}`}
                        className="field-textarea"
                        rows={3}
                        value={draft.content ?? memory.content}
                        onChange={(e) =>
                          onMemoryDraftChange(memory.id, {
                            content: e.target.value,
                          })
                        }
                        disabled={streaming}
                      />
                    </div>
                    <div className="workplace__memory-controls">
                      <div className="workplace__field">
                        <label
                          className="field-label"
                          htmlFor={`wp-memory-type-${memory.id}`}
                        >
                          Type
                        </label>
                        <select
                          id={`wp-memory-type-${memory.id}`}
                          className="field-input"
                          value={draft.memory_type ?? memory.memory_type}
                          onChange={(e) =>
                            onMemoryDraftChange(memory.id, {
                              memory_type: e.target.value as MemoryType,
                            })
                          }
                          disabled={streaming}
                        >
                          {MEMORY_TYPES.map((type) => (
                            <option key={type} value={type}>
                              {type}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="workplace__field">
                        <label
                          className="field-label"
                          htmlFor={`wp-memory-importance-${memory.id}`}
                        >
                          Importance
                        </label>
                        <input
                          id={`wp-memory-importance-${memory.id}`}
                          className="field-input"
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          value={draft.importance ?? memory.importance}
                          onChange={(e) =>
                            onMemoryDraftChange(memory.id, {
                              importance: Number(e.target.value),
                            })
                          }
                          disabled={streaming}
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="empty-state">Nothing to store this round</p>
          )}

          <button
            type="button"
            className="btn btn-accent"
            onClick={onContinue}
            disabled={streaming}
            aria-keyshortcuts="r"
          >
            Continue
          </button>
        </div>
      </section>
    )
  }

  if (selectedStep) {
    const s = selectedStep.state
    const node = selectedStep.node
    const showPlan = node === 'planner' && Boolean(s.plan?.length)
    const showExecution =
      node === 'executor' && Boolean(s.execution || s.tool_calls?.length)
    const showLearning = node === 'learner' && Boolean(s.learning)
    const showActioner =
      node === 'actioner' &&
      (s.loop_score !== undefined ||
        Boolean(s.refine_from) ||
        s.memory_cursor !== undefined ||
        s.skill_preview_ready !== undefined)
    const empty =
      !showPlan && !showExecution && !showLearning && !showActioner

    return (
      <section className="workplace panel" aria-label="Workplace">
        <h2 className="panel-title">Step · {selectedStep.node}</h2>
        <div className="workplace__body workplace__payloads">
          {showPlan ? (
            <div>
              <h3 className="workplace__sub">Plan</h3>
              <ol className="inspector-list">
                {s.plan!.map((item, i) => (
                  <li key={`${i}-${item}`}>{item}</li>
                ))}
              </ol>
            </div>
          ) : null}
          {showExecution && s.execution ? (
            <div>
              <h3 className="workplace__sub">Execution</h3>
              <p className="inspector-prose">{s.execution.summary}</p>
            </div>
          ) : null}
          {showExecution && s.tool_calls?.length ? (
            <div>
              <h3 className="workplace__sub">Tools</h3>
              <pre className="inspector-json mono">
                {formatJson(s.tool_calls)}
              </pre>
            </div>
          ) : null}
          {showLearning && s.learning ? (
            <div>
              <h3 className="workplace__sub">Learning</h3>
              <p className="inspector-prose">
                {s.learning.verdict}: {s.learning.reason}
              </p>
              <p className="workplace__hint mono">
                suggested: {s.learning.suggested_step}
              </p>
              {s.learning.lessons ? (
                <dl className="inspector-dl">
                  <div>
                    <dt>Worked</dt>
                    <dd>{s.learning.lessons.worked.join('; ') || '—'}</dd>
                  </div>
                  <div>
                    <dt>Failed</dt>
                    <dd>{s.learning.lessons.failed.join('; ') || '—'}</dd>
                  </div>
                  <div>
                    <dt>Risks</dt>
                    <dd>{s.learning.lessons.risks.join('; ') || '—'}</dd>
                  </div>
                  <div>
                    <dt>Next time</dt>
                    <dd>{s.learning.lessons.next_time.join('; ') || '—'}</dd>
                  </div>
                </dl>
              ) : null}
              {s.learning_candidates?.length ? (
                <p className="workplace__hint">
                  {s.learning_candidates.length} learning candidate
                  {s.learning_candidates.length === 1 ? '' : 's'}
                </p>
              ) : null}
            </div>
          ) : null}
          {showActioner ? (
            <div>
              <h3 className="workplace__sub">Action</h3>
              <dl className="inspector-dl">
                <div>
                  <dt>Loop score</dt>
                  <dd className="mono">
                    {s.loop_score !== undefined ? s.loop_score : '—'}
                  </dd>
                </div>
                <div>
                  <dt>Refine from</dt>
                  <dd className="mono">{s.refine_from ?? '—'}</dd>
                </div>
                <div>
                  <dt>Skill preview</dt>
                  <dd>{s.skill_preview_ready ? 'ready' : 'not ready'}</dd>
                </div>
                <div>
                  <dt>Memory cursor</dt>
                  <dd className="mono">
                    {s.memory_cursor !== undefined ? s.memory_cursor : '—'}
                  </dd>
                </div>
              </dl>
            </div>
          ) : null}
          {empty ? (
            <p className="empty-state">No primary payloads on this step.</p>
          ) : null}
        </div>
      </section>
    )
  }

  return (
    <section className="workplace panel" aria-label="Workplace">
      <h2 className="panel-title">Workplace</h2>
      <div className="workplace__idle">
        <p className="empty-state empty-state--centered">Ready for a run</p>
        <p className="empty-state__hint">
          Start a thread from Command. Clarification and step payloads appear
          here.
        </p>
      </div>
    </section>
  )
}
