import { useEffect, useState } from 'react'
import type {
  ClarificationAnswer,
  InterruptPayload,
  MemoryResumeRow,
  ResumeOverrides,
} from '../types/api'
import {
  actionReviewMemories,
  isActionReviewInterrupt,
} from '../lib/actionReview'
import {
  clarificationQuestions,
  isClarificationInterrupt,
} from '../lib/clarification'
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
  const memories = actionReviewMemories(interrupt)

  const [planOverrideText, setPlanOverrideText] = useState('')
  const [refineOverride, setRefineOverride] = useState<
    ResumeOverrides['refine_from'] | ''
  >('')
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>(
    {},
  )
  const [memoryDrafts, setMemoryDrafts] = useState<
    Record<string, MemoryResumeRow>
  >({})

  useEffect(() => {
    if (!canResume) {
      setPlanOverrideText('')
      setRefineOverride('')
      setAnswerDrafts({})
      setMemoryDrafts({})
      return
    }
    const next: Record<string, string> = {}
    for (const question of questions) {
      next[question.id] = ''
    }
    setAnswerDrafts(next)
    const nextMemoryDrafts: Record<string, MemoryResumeRow> = {}
    for (const memory of memories) {
      nextMemoryDrafts[memory.id] = {
        id: memory.id,
        keep: true,
        content: memory.content,
        memory_type: memory.memory_type,
        importance: memory.importance,
      }
    }
    setMemoryDrafts(nextMemoryDrafts)
  }, [canResume, interrupt?.id])

  const setAnswer = (id: string, value: string) => {
    setAnswerDrafts((prev) => ({ ...prev, [id]: value }))
  }

  const setMemoryDraft = (id: string, patch: Partial<MemoryResumeRow>) => {
    setMemoryDrafts((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] ?? { id, keep: true }),
        ...patch,
        id,
      },
    }))
  }

  const buildPayload = (): {
    overrides?: ResumeOverrides
    answers?: ClarificationAnswer[]
    interrupt_resume?:
      | { memories: MemoryResumeRow[] }
      | { answers: ClarificationAnswer[] }
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
    let interrupt_resume:
      | { memories: MemoryResumeRow[] }
      | { answers: ClarificationAnswer[] }
      | undefined
    if (isActionReviewInterrupt(interrupt)) {
      interrupt_resume = {
        memories: memories.map(
          (memory) =>
            memoryDrafts[memory.id] ?? {
              id: memory.id,
              keep: true,
              content: memory.content,
              memory_type: memory.memory_type,
              importance: memory.importance,
            },
        ),
      }
    } else if (isClarificationInterrupt(interrupt) && answers?.length) {
      interrupt_resume = { answers }
    }
    return {
      overrides:
        Object.keys(overrides).length > 0 ? overrides : undefined,
      answers,
      interrupt_resume,
    }
  }

  return {
    canResume,
    questions,
    memories,
    planOverrideText,
    setPlanOverrideText,
    refineOverride,
    setRefineOverride,
    answerDrafts,
    setAnswer,
    memoryDrafts,
    setMemoryDraft,
    buildPayload,
  }
}
