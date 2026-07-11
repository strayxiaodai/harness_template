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
