import type { HealthStatus } from '../hooks/useHealth'
import type { RunPhase } from '../hooks/useConsole'
import type { ThreadSummary } from '../types/api'
import {
  formatThreadSelectLabel,
  shouldDisableThreadPicker,
} from '../lib/threadAttach'
import './StatusBar.css'

interface StatusBarProps {
  health: HealthStatus
  healthDetail: string | null
  threadId: string
  phase: RunPhase
  rounds: number
  maxRounds: number
  humanInTheLoop: boolean
  nextAction: string | null
  threads: ThreadSummary[]
  threadsLoading: boolean
  threadsError: string | null
  onAttachThread: (thread: ThreadSummary) => void
  onRefreshThreads: () => void
}

const PHASE_LABEL: Record<RunPhase, string> = {
  idle: 'Idle',
  streaming: 'Running',
  awaiting_human: 'Awaiting human',
  complete: 'Complete',
  error: 'Error',
}

export function StatusBar({
  health,
  healthDetail,
  threadId,
  phase,
  rounds,
  maxRounds,
  humanInTheLoop,
  nextAction,
  threads,
  threadsLoading,
  threadsError,
  onAttachThread,
  onRefreshThreads,
}: StatusBarProps) {
  const known = threads.some((t) => t.thread_id === threadId)
  const disabled = shouldDisableThreadPicker(phase) || threadsLoading

  return (
    <header className="status-bar" role="banner">
      <div className="status-bar__cluster">
        <span
          className={`status-pill status-pill--${health}`}
          title={healthDetail ?? undefined}
          role="status"
        >
          API {health}
        </span>
        <label className="status-bar__thread" htmlFor="thread-select">
          <span className="sr-only">Thread</span>
          <select
            id="thread-select"
            className="status-bar__thread-select mono"
            value={threadId}
            disabled={disabled}
            title={threadsError ? threadsError : threadId}
            aria-label="Attach existing thread"
            onChange={(e) => {
              const id = e.target.value
              const match = threads.find((t) => t.thread_id === id)
              if (match) {
                onAttachThread(match)
              }
            }}
          >
            {!known && (
              <option value={threadId}>
                current {threadId.slice(0, 8)}…
              </option>
            )}
            {threads.map((thread) => (
              <option
                key={thread.thread_id}
                value={thread.thread_id}
                title={`${thread.task} · ${thread.thread_id}`}
              >
                {formatThreadSelectLabel(thread)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="status-bar__refresh"
          onClick={onRefreshThreads}
          disabled={threadsLoading || phase === 'streaming'}
          aria-label="Refresh thread list"
          title="Refresh thread list"
        >
          {threadsLoading ? '…' : '↻'}
        </button>
        <span className="status-bar__meta">
          round {rounds}/{maxRounds}
        </span>
        {humanInTheLoop && (
          <span className="status-bar__meta status-bar__hitl">HITL on</span>
        )}
      </div>
      <div className="status-bar__cluster">
        <span
          className={`status-phase ${
            phase === 'awaiting_human' ? 'status-phase--interrupt' : ''
          }`}
          aria-live="polite"
        >
          {PHASE_LABEL[phase]}
          {nextAction && phase === 'awaiting_human' && (
            <span className="status-phase__next">
              {' '}
              · next: <strong>{nextAction}</strong>
            </span>
          )}
        </span>
      </div>
    </header>
  )
}
