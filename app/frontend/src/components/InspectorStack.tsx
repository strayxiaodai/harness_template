import type { ReactNode } from 'react'
import { formatJson } from '../lib/api'
import type { AgentStateSnapshot, TimelineStep } from '../types/api'
import './InspectorStack.css'

interface InspectorStackProps {
  step: TimelineStep | null
  accumulated: AgentStateSnapshot
}

export function InspectorStack({ step, accumulated }: InspectorStackProps) {
  const state = step?.state ?? accumulated

  return (
    <aside className="inspector-stack" aria-label="Inspector">
      <InspectorSection title="Plan" empty={!state.plan?.length}>
        {state.plan?.length ? (
          <ol className="inspector-list">
            {state.plan.map((item, i) => (
              <li key={`${i}-${item}`}>{item}</li>
            ))}
          </ol>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title="Execution"
        empty={!state.execution}
      >
        {state.execution && (
          <div className="inspector-prose">
            <p>{state.execution.summary}</p>
            {state.execution.changes.length > 0 && (
              <>
                <h3 className="inspector-sub">Changes</h3>
                <ul>
                  {state.execution.changes.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </>
            )}
            {state.execution.risks.length > 0 && (
              <>
                <h3 className="inspector-sub">Risks</h3>
                <ul>
                  {state.execution.risks.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </InspectorSection>

      <InspectorSection
        title="Tool calls"
        empty={!state.tool_calls?.length}
      >
        {state.tool_calls && state.tool_calls.length > 0 && (
          <table className="tool-table">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Tool</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {state.tool_calls.map((tc, i) => (
                <tr key={`${tc.tool}-${i}`}>
                  <td>{tc.iteration}</td>
                  <td className="mono">{tc.tool}</td>
                  <td>{tc.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {state.tool_calls?.map((tc, i) => (
          <pre key={`args-${i}`} className="inspector-json mono">
            {formatJson(tc.args)}
          </pre>
        ))}
      </InspectorSection>

      <InspectorSection title="Review" empty={!state.review}>
        {state.review && (
          <dl className="inspector-dl">
            <div>
              <dt>Verdict</dt>
              <dd>{state.review.verdict}</dd>
            </div>
            <div>
              <dt>Reason</dt>
              <dd>{state.review.reason}</dd>
            </div>
            <div>
              <dt>Suggested step</dt>
              <dd className="mono">{state.review.suggested_step}</dd>
            </div>
          </dl>
        )}
      </InspectorSection>

      <InspectorSection
        title="Skill playbook"
        empty={!state.skill_context}
      >
        {state.skill_context ? (
          <pre className="inspector-json mono">{state.skill_context}</pre>
        ) : (
          <p className="empty-state">No skill loaded for this thread.</p>
        )}
      </InspectorSection>

      <InspectorSection
        title="Memory recall"
        empty={!state.memory_context}
      >
        {state.memory_context ? (
          <pre className="inspector-json mono">{state.memory_context}</pre>
        ) : (
          <p className="empty-state">No recalled memories for this step.</p>
        )}
      </InspectorSection>

      <InspectorSection title="Result" empty={!state.result}>
        {state.result && (
          <pre className="inspector-json mono">{state.result}</pre>
        )}
      </InspectorSection>

      <AuditPanel />
    </aside>
  )
}

function InspectorSection({
  title,
  empty,
  children,
}: {
  title: string
  empty: boolean
  children: ReactNode
}) {
  return (
    <section className="inspector-section panel">
      <h2 className="panel-title">{title}</h2>
      {empty ? (
        <p className="empty-state">No {title.toLowerCase()} in this step.</p>
      ) : (
        <div className="inspector-section__body">{children}</div>
      )}
    </section>
  )
}

function AuditPanel() {
  return (
    <section className="inspector-section panel">
      <h2 className="panel-title">Audit log</h2>
      <p className="empty-state">
        Audit log needs Postgres. Events appear here when DATABASE_URL is set
        and the audit API is wired.
      </p>
    </section>
  )
}
