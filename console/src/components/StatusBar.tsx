import type { HealthStatus } from '../hooks/useHealth'
import type { RunPhase } from '../hooks/useConsole'
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
}: StatusBarProps) {
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
        <span
          className="status-bar__meta mono"
          title={threadId}
          aria-label={`Thread ${threadId}`}
        >
          thread {threadId.slice(0, 8)}…
        </span>
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
