import type { InterruptPayload, PendingMemory } from '../types/api'

export function isActionReviewInterrupt(
  interrupt: InterruptPayload | null,
): boolean {
  const value = interrupt?.value
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  return (value as Record<string, unknown>).kind === 'action_review'
}

export function actionReviewMemories(
  interrupt: InterruptPayload | null,
): PendingMemory[] {
  if (!isActionReviewInterrupt(interrupt)) {
    return []
  }
  const record = interrupt!.value as Record<string, unknown>
  const memories = record.memories
  if (!Array.isArray(memories)) {
    return []
  }
  return memories.filter(
    (m): m is PendingMemory =>
      typeof m === 'object' &&
      m !== null &&
      typeof (m as PendingMemory).id === 'string' &&
      typeof (m as PendingMemory).content === 'string',
  )
}

export function actionReviewMeta(interrupt: InterruptPayload | null): {
  score?: number
  threshold?: number
  skillPreviewReady: boolean
  message: string
} {
  if (!isActionReviewInterrupt(interrupt)) {
    return { skillPreviewReady: false, message: '' }
  }
  const record = interrupt!.value as Record<string, unknown>
  return {
    score: typeof record.score === 'number' ? record.score : undefined,
    threshold:
      typeof record.threshold === 'number' ? record.threshold : undefined,
    skillPreviewReady: Boolean(record.skill_preview_ready),
    message: String(record.message ?? ''),
  }
}
