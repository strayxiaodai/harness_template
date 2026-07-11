import { useEffect, useState } from 'react'
import type {
  ClarificationAnswer,
  ClarificationQuestion,
  DistillSkillResponse,
  InterruptPayload,
  ResumeOverrides,
  SkillDetail,
  SkillSummary,
} from '../types/api'
import type { RunPhase } from '../hooks/useConsole'
import { useNarrowViewport } from '../hooks/useNarrowViewport'
import './CommandColumn.css'

interface CommandColumnProps {
  task: string
  planText: string
  maxRounds: number
  humanInTheLoop: boolean
  phase: RunPhase
  error: string | null
  skillsError: string | null
  skills: SkillSummary[]
  selectedSkillSlug: string
  selectedSkill: SkillDetail | null
  skillsLoading: boolean
  skillDetailLoading: boolean
  skillName: string
  distillResult: DistillSkillResponse | null
  distillBusy: boolean
  interrupt: InterruptPayload | null
  onTaskChange: (value: string) => void
  onPlanChange: (value: string) => void
  onMaxRoundsChange: (value: number) => void
  onHitlChange: (value: boolean) => void
  onSkillNameChange: (value: string) => void
  onSkillSelect: (slug: string) => void
  onRefreshSkills: () => void
  onClearSkillsError: () => void
  onRun: () => void
  onRunSkill: () => void
  onResume: (
    overrides?: ResumeOverrides,
    answers?: ClarificationAnswer[],
  ) => void
  onDistillSkill: () => void
  onSaveSkill: () => void | Promise<void>
  onDiscardSkill: () => void
  onReset: () => void
  onClearError: () => void
  nextAction: string | null
  skillEligible: boolean
  skillIneligibleReason: string
}

function parsePlanLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function buildOverrides(
  planOverrideText: string,
  refineFrom: ResumeOverrides['refine_from'] | '',
): ResumeOverrides | undefined {
  const plan = parsePlanLines(planOverrideText)
  const overrides: ResumeOverrides = {}
  if (plan.length > 0) {
    overrides.plan = plan
  }
  if (refineFrom) {
    overrides.refine_from = refineFrom
  }
  return Object.keys(overrides).length > 0 ? overrides : undefined
}

function clarificationQuestions(
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

export function CommandColumn({
  task,
  planText,
  maxRounds,
  humanInTheLoop,
  phase,
  error,
  skillsError,
  skills,
  selectedSkillSlug,
  selectedSkill,
  skillsLoading,
  skillDetailLoading,
  skillName,
  distillResult,
  distillBusy,
  interrupt,
  onTaskChange,
  onPlanChange,
  onMaxRoundsChange,
  onHitlChange,
  onSkillNameChange,
  onSkillSelect,
  onRefreshSkills,
  onClearSkillsError,
  onRun,
  onRunSkill,
  onResume,
  onDistillSkill,
  onSaveSkill,
  onDiscardSkill,
  onReset,
  onClearError,
  nextAction: _nextAction,
  skillEligible,
  skillIneligibleReason,
}: CommandColumnProps) {
  const isStreaming = phase === 'streaming'
  const canResume =
    (phase === 'awaiting_human' || phase === 'error') && !isStreaming
  const canDistill =
    (phase === 'complete' || phase === 'awaiting_human') &&
    !isStreaming &&
    skillEligible
  const canRunSkill = !isStreaming && Boolean(selectedSkillSlug)
  const isNarrow = useNarrowViewport()
  const questions = clarificationQuestions(interrupt)

  const [planOverrideText, setPlanOverrideText] = useState('')
  const [refineOverride, setRefineOverride] = useState<
    ResumeOverrides['refine_from'] | ''
  >('')
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({})

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

  const handleResume = () => {
    const answers: ClarificationAnswer[] | undefined =
      questions.length > 0
        ? questions
            .map((question) => ({
              question_id: question.id,
              answer: (answerDrafts[question.id] ?? '').trim(),
            }))
            .filter((item) => item.answer.length > 0)
        : undefined
    onResume(buildOverrides(planOverrideText, refineOverride), answers)
  }

  return (
    <aside className="command-column panel" aria-label="Run controls">
      <h2 className="panel-title">Command</h2>

      <div className="command-column__body">
        <div className="command-section command-section--run">
          <p className="command-section__label">Run</p>

          <label className="field-label" htmlFor="task-input">
            Task
          </label>
          <textarea
            id="task-input"
            className="field-textarea"
            value={task}
            onChange={(e) => onTaskChange(e.target.value)}
            placeholder="Describe what the harness should accomplish"
            disabled={isStreaming}
            rows={3}
            aria-describedby="task-hint"
          />
          <p id="task-hint" className="command-column__hint">
            Required for Start thread. Optional when running a saved skill.
          </p>

          <label className="field-label" htmlFor="plan-input">
            Plan steps (optional, one per line)
          </label>
          <textarea
            id="plan-input"
            className="field-textarea command-column__plan"
            value={planText}
            onChange={(e) => onPlanChange(e.target.value)}
            placeholder={'Step one\nStep two'}
            disabled={isStreaming}
            rows={2}
          />

          <div className="command-column__row">
            <label className="field-label" htmlFor="max-rounds">
              Max rounds
            </label>
            <input
              id="max-rounds"
              className="field-input"
              type="number"
              min={1}
              max={20}
              step={1}
              value={maxRounds}
              onChange={(e) => onMaxRoundsChange(Number(e.target.value))}
              disabled={isStreaming}
              aria-describedby="max-rounds-hint"
            />
            <p id="max-rounds-hint" className="command-column__hint">
              Clamped to 1–20 to match the API.
            </p>
          </div>

          <div className="command-column__actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={onRun}
              disabled={isStreaming || !task.trim()}
              aria-busy={isStreaming}
            >
              {isStreaming ? 'Running…' : 'Start thread'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onReset}
              disabled={isStreaming}
            >
              New thread
            </button>
          </div>
        </div>

        <details className="skill-library">
          <summary className="skill-library__summary">Skills</summary>
          <div
            className="skill-library__body"
            aria-busy={skillsLoading || skillDetailLoading}
            aria-live="polite"
          >
            <p className="command-column__hint">
              Pick a distilled skill and start a new harness thread with its
              playbook injected into planner and executor.
            </p>
            <div className="command-column__row command-column__row--skill">
              <label className="field-label" htmlFor="skill-select">
                Saved skill
              </label>
              <select
                id="skill-select"
                className="field-input field-input--touch"
                value={selectedSkillSlug}
                onChange={(e) => onSkillSelect(e.target.value)}
                disabled={isStreaming || skillsLoading}
              >
                <option value="">
                  {skillsLoading ? 'Loading skills…' : 'Select a skill'}
                </option>
                {skills.map((skill) => (
                  <option key={skill.slug} value={skill.slug}>
                    {skill.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary btn-compact skill-library__refresh"
                onClick={onRefreshSkills}
                disabled={skillsLoading || isStreaming}
                aria-busy={skillsLoading}
              >
                {skillsLoading ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
            {skillsError && (
              <div className="command-column__inline-error" role="alert">
                <p className="command-column__error-text">{skillsError}</p>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  onClick={() => {
                    onClearSkillsError()
                    onRefreshSkills()
                  }}
                  disabled={skillsLoading}
                >
                  Retry load
                </button>
              </div>
            )}
            {skillDetailLoading && (
              <p className="command-column__hint" aria-live="polite">
                Loading skill preview…
              </p>
            )}
            {selectedSkill && !skillDetailLoading && (
              <>
                <p className="command-column__hint">{selectedSkill.description}</p>
                <pre className="inspector-json mono skill-library__preview">
                  {selectedSkill.body}
                </pre>
              </>
            )}
            {!skillsLoading && skills.length === 0 && (
              <p className="command-column__hint">
                No saved skills yet. Complete a thread and distill one below.
              </p>
            )}
            <button
              type="button"
              className="btn btn-primary"
              onClick={onRunSkill}
              disabled={!canRunSkill}
              aria-busy={isStreaming}
            >
              Run skill
            </button>
            <p className="command-column__hint">
              Optional: add text in Task above to narrow this run. Leave Task
              empty to use the skill description as the goal.
            </p>
          </div>
        </details>

        <div
          className={
            phase === 'awaiting_human'
              ? 'command-section command-section--hitl command-section--active'
              : 'command-section command-section--hitl'
          }
        >
          <p className="command-section__label">HITL</p>
          <label className="command-column__check" htmlFor="hitl-toggle">
            <input
              id="hitl-toggle"
              type="checkbox"
              className="command-column__checkbox"
              checked={humanInTheLoop}
              onChange={(e) => onHitlChange(e.target.checked)}
              disabled={isStreaming}
            />
            Pause after each node (HITL)
          </label>

          {canResume && phase === 'awaiting_human' && (
            <>
              <button
                type="button"
                className="btn btn-accent"
                onClick={handleResume}
                disabled={isStreaming}
                aria-keyshortcuts="r"
              >
                Continue from interrupt
              </button>
              <OverrideForm
                planOverrideText={planOverrideText}
                refineOverride={refineOverride}
                onPlanChange={setPlanOverrideText}
                onRefineChange={setRefineOverride}
                disabled={isStreaming}
              />
              {questions.length > 0 && (
                <ClarificationForm
                  questions={questions}
                  reason={
                    typeof interrupt?.value === 'object' &&
                    interrupt?.value !== null &&
                    !Array.isArray(interrupt.value)
                      ? String(
                          (interrupt.value as Record<string, unknown>).reason ??
                            '',
                        )
                      : ''
                  }
                  answers={answerDrafts}
                  onAnswerChange={(id, value) =>
                    setAnswerDrafts((prev) => ({ ...prev, [id]: value }))
                  }
                  disabled={isStreaming}
                />
              )}
            </>
          )}
        </div>

        <details
          className="skill-distill"
          open={!isNarrow && canDistill}
        >
          <summary className="skill-distill__summary">
            Distill
          </summary>
          <div className="skill-distill__body">
            <p className="command-column__hint">
              Preview turns this thread into a skill draft after at least one
              full loop scores 80+ at the actioner, so you can confirm the
              workflow worked before saving.
            </p>
            {!skillEligible &&
              (phase === 'complete' || phase === 'awaiting_human') &&
              !isStreaming && (
                <p className="command-column__hint skill-distill__blocked">
                  {skillIneligibleReason}
                </p>
              )}
            <label className="field-label" htmlFor="skill-name">
              Skill slug (optional)
            </label>
            <input
              id="skill-name"
              className="field-input"
              value={skillName}
              onChange={(e) => onSkillNameChange(e.target.value)}
              placeholder="auto from task, e.g. add-sqlite-checkpoints"
              disabled={!canDistill || distillBusy || Boolean(distillResult?.saved)}
            />
            <button
              type="button"
              className="btn btn-accent"
              onClick={onDistillSkill}
              disabled={!canDistill || distillBusy || Boolean(distillResult?.saved)}
              aria-busy={distillBusy}
            >
              {distillBusy && (!distillResult || distillResult.saved)
                ? 'Previewing…'
                : distillResult && !distillResult.saved
                  ? 'Preview again'
                  : 'Preview skill'}
            </button>
            {distillResult && !distillResult.saved && (
              <div className="skill-distill__preview" role="region" aria-label="Skill preview">
                <p>
                  <strong>{distillResult.slug}</strong>
                  <span className="command-column__hint"> — preview only</span>
                </p>
                <p className="command-column__hint">{distillResult.description}</p>
                <pre className="inspector-json mono skill-distill__body-preview">
                  {distillResult.body}
                </pre>
                <div className="skill-distill__confirm">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={onSaveSkill}
                    disabled={distillBusy}
                    aria-busy={distillBusy}
                  >
                    {distillBusy ? 'Saving…' : 'Save skill'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={onDiscardSkill}
                    disabled={distillBusy}
                  >
                    Don&apos;t save
                  </button>
                </div>
              </div>
            )}
            {distillResult?.saved && (
              <div className="skill-distill__result skill-distill__result--saved" role="status">
                <p>
                  <strong>{distillResult.slug}</strong>
                  {distillResult.refined ? ' (refined)' : ' (created)'}
                </p>
                <p className="command-column__hint">{distillResult.description}</p>
                {distillResult.path && (
                  <p className="mono skill-distill__path">{distillResult.path}</p>
                )}
              </div>
            )}
          </div>
        </details>

        {error && (
          <div className="command-column__error" role="alert">
            <p className="command-column__error-text">{error}</p>
            <div className="command-column__error-actions">
              {phase === 'error' && (
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  onClick={onRun}
                  disabled={isStreaming || !task.trim()}
                >
                  Retry run
                </button>
              )}
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                onClick={onClearError}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

function OverrideForm({
  planOverrideText,
  refineOverride,
  onPlanChange,
  onRefineChange,
  disabled,
}: {
  planOverrideText: string
  refineOverride: ResumeOverrides['refine_from'] | ''
  onPlanChange: (value: string) => void
  onRefineChange: (value: ResumeOverrides['refine_from'] | '') => void
  disabled: boolean
}) {
  return (
    <details className="override-form">
      <summary className="override-form__summary">Overrides before resume</summary>
      <div className="override-form__fields">
        <label className="field-label" htmlFor="override-plan">
          Replace plan (one step per line)
        </label>
        <textarea
          id="override-plan"
          className="field-textarea"
          rows={3}
          value={planOverrideText}
          onChange={(e) => onPlanChange(e.target.value)}
          placeholder="Leave empty to keep current plan"
          disabled={disabled}
        />
        <label className="field-label" htmlFor="override-refine">
          Refine from (optional)
        </label>
        <select
          id="override-refine"
          className="field-input"
          value={refineOverride}
          onChange={(e) =>
            onRefineChange(
              e.target.value as ResumeOverrides['refine_from'] | '',
            )
          }
          disabled={disabled}
        >
          <option value="">No change</option>
          <option value="planner">planner</option>
          <option value="executor">executor</option>
          <option value="finish">finish</option>
        </select>
        <p className="override-form__note">
          Overrides apply when you click Continue from interrupt.
        </p>
      </div>
    </details>
  )
}

function ClarificationForm({
  questions,
  reason,
  answers,
  onAnswerChange,
  disabled,
}: {
  questions: ClarificationQuestion[]
  reason: string
  answers: Record<string, string>
  onAnswerChange: (id: string, value: string) => void
  disabled: boolean
}) {
  return (
    <div className="override-form clarification-form">
      <p className="override-form__summary">Clarification required</p>
      {reason ? <p className="command-column__hint">{reason}</p> : null}
      <div className="override-form__fields">
        {questions.map((question) => (
          <div key={question.id}>
            <label className="field-label" htmlFor={`clarify-${question.id}`}>
              {question.prompt}
            </label>
            {question.why ? (
              <p className="command-column__hint">{question.why}</p>
            ) : null}
            <textarea
              id={`clarify-${question.id}`}
              className="field-textarea"
              rows={2}
              value={answers[question.id] ?? ''}
              onChange={(e) => onAnswerChange(question.id, e.target.value)}
              placeholder="Your answer"
              disabled={disabled}
            />
          </div>
        ))}
        <p className="override-form__note">
          Answers are sent with resume as structured question_id mappings.
        </p>
      </div>
    </div>
  )
}
