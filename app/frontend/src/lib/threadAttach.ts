import type { ThreadSummary } from '../types/api'

/** Fields attach must not clear — documented for tests. */
export const ATTACH_PRESERVED_KEYS: readonly string[] = [
  'timeline',
  'phase',
  'runResponse',
  'selectedStepId',
  'distillResult',
]

export function shouldDisableThreadPicker(
  phase: string,
  busy = false,
): boolean {
  return busy || phase === 'streaming'
}

export function formatThreadSelectLabel(
  thread: Pick<ThreadSummary, 'thread_id' | 'task'>,
  maxLen = 36,
): string {
  const task = (thread.task || '').trim()
  const short = String(thread.thread_id || '').slice(0, 8)
  if (!task) {
    return `${short}…`
  }
  const truncated = task.length > maxLen ? `${task.slice(0, maxLen)}…` : task
  return `${truncated} (${short}…)`
}

export function applyAttachFields(thread: ThreadSummary): {
  threadId: string
  task: string
  planText: string
} {
  return {
    threadId: thread.thread_id,
    task: thread.task || '',
    planText: Array.isArray(thread.plan) ? thread.plan.join('\n') : '',
  }
}
