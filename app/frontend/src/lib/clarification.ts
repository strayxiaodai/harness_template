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
