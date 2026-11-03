import { useState } from 'react'
import type { SkillSummary } from '../types/api'
import './HeroWorkspace.css'

export interface HeroWorkspaceProps {
  task: string
  onTaskChange: (task: string) => void
  taskRewrite: boolean
  onTaskRewriteChange: (rewrite: boolean) => void
  humanInTheLoop: boolean
  onHitlChange: (hitl: boolean) => void
  planText: string
  onPlanChange: (plan: string) => void
  skills: SkillSummary[]
  selectedSkillSlug: string
  onSkillSelect: (slug: string) => void
  onRun: () => void
  isStreaming: boolean
  workspaceName?: string
}

export function HeroWorkspace({
  task,
  onTaskChange,
  taskRewrite,
  onTaskRewriteChange,
  humanInTheLoop,
  onHitlChange,
  planText,
  onPlanChange,
  skills,
  selectedSkillSlug,
  onSkillSelect,
  onRun,
  isStreaming,
  workspaceName = 'Default workspace',
}: HeroWorkspaceProps) {
  const [showPlusMenu, setShowPlusMenu] = useState(false)
  const [showModeMenu, setShowModeMenu] = useState(false)
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false)

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      if (task.trim() && !isStreaming) {
        onRun()
      }
    }
  }

  return (
    <div className="harness-hero">
      {/* Title / Identity Group */}
      <div className="harness-hero__title-group">
        <div className="harness-hero__logo">
          <svg
            className="harness-hero__logo-svg"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <circle cx="5" cy="12" r="3" fill="#4d6cb0" />
            <circle cx="12" cy="5" r="3" fill="#3b82f6" />
            <circle cx="12" cy="19" r="3" fill="#38bdf8" />
            <circle cx="19" cy="12" r="3" fill="#60a5fa" />
            <path
              d="M7.5 10.5L9.5 6.5M7.5 13.5L9.5 17.5M14.5 6.5L16.5 10.5M14.5 17.5L16.5 13.5"
              stroke="#6b86c2"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <h1 className="harness-hero__title">Harness Agent Engine</h1>
        <span className="harness-hero__pill">LangGraph Loop</span>
      </div>

      {/* Selectors Row */}
      <div className="harness-selectors-row">
        <div className="harness-dropdown-anchor">
          <button
            type="button"
            className="harness-dropdown-btn"
            onClick={() => setShowWorkspaceMenu(!showWorkspaceMenu)}
          >
            <span className="harness-dropdown-icon">📁</span>
            <span>{workspaceName}</span>
            <span className="harness-dropdown-caret">▾</span>
          </button>
        </div>

        <div className="harness-dropdown-anchor">
          <button
            type="button"
            className="harness-dropdown-btn"
            onClick={() => setShowModeMenu(!showModeMenu)}
          >
            <span className="harness-dropdown-icon">🔄</span>
            <span>{humanInTheLoop ? 'HITL mode' : 'Standard mode'}</span>
            <span className="harness-dropdown-caret">▾</span>
          </button>

          {showModeMenu && (
            <div className="harness-popover-menu">
              <button
                type="button"
                className={`harness-popover-item ${
                  !humanInTheLoop ? 'harness-popover-item--active' : ''
                }`}
                onClick={() => {
                  onHitlChange(false)
                  setShowModeMenu(false)
                }}
              >
                <strong>Standard mode</strong>
                <span>Runs autonomously to completion</span>
              </button>
              <button
                type="button"
                className={`harness-popover-item ${
                  humanInTheLoop ? 'harness-popover-item--active' : ''
                }`}
                onClick={() => {
                  onHitlChange(true)
                  setShowModeMenu(false)
                }}
              >
                <strong>HITL mode</strong>
                <span>Pauses at node boundaries for human review</span>
              </button>
            </div>
          )}
        </div>

        {taskRewrite && (
          <span className="harness-mode-badge" title="TASK_REWRITE_ENABLED active">
            ✨ Prompt Rewrite On
          </span>
        )}
      </div>

      {/* Big Prompt Card */}
      <div className="harness-prompt-card">
        <textarea
          className="harness-prompt-textarea"
          rows={5}
          placeholder="Describe your task or goal to execute..."
          value={task}
          onChange={(e) => onTaskChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
        />

        {planText && (
          <div className="harness-prompt-plan-preview">
            <span className="harness-plan-tag">Pre-defined Plan:</span>
            <pre className="harness-plan-text mono">{planText}</pre>
          </div>
        )}

        <div className="harness-prompt-card__footer">
          <div className="harness-prompt-card__tools">
            <div className="harness-dropdown-anchor">
              <button
                type="button"
                className={`harness-tool-circle-btn ${
                  showPlusMenu ? 'harness-tool-circle-btn--active' : ''
                }`}
                onClick={() => setShowPlusMenu(!showPlusMenu)}
                title="Task options & skills"
                aria-label="Task options and skills"
              >
                +
              </button>

              {showPlusMenu && (
                <div className="harness-popover-menu harness-popover-menu--up">
                  <label className="harness-popover-check-row">
                    <input
                      type="checkbox"
                      checked={taskRewrite}
                      onChange={(e) => onTaskRewriteChange(e.target.checked)}
                    />
                    <span>Rewrite task prompt with structured template</span>
                  </label>

                  {skills.length > 0 && (
                    <div className="harness-popover-sublist">
                      <span className="harness-popover-subhead">Apply Skill:</span>
                      {skills.map((s) => (
                        <button
                          key={s.slug}
                          type="button"
                          className={`harness-popover-skill-btn ${
                            selectedSkillSlug === s.slug
                              ? 'harness-popover-skill-btn--active'
                              : ''
                          }`}
                          onClick={() => {
                            onSkillSelect(s.slug)
                            setShowPlusMenu(false)
                          }}
                        >
                          {s.name}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="harness-popover-plan-input">
                    <span className="harness-popover-subhead">Pre-defined Plan Steps:</span>
                    <textarea
                      rows={2}
                      className="harness-sub-textarea mono"
                      placeholder={'Step 1\nStep 2'}
                      value={planText}
                      onChange={(e) => onPlanChange(e.target.value)}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          <button
            type="button"
            className="harness-submit-circle-btn"
            onClick={onRun}
            disabled={isStreaming || !task.trim()}
            title="Start harness run (⌘+Enter)"
            aria-label="Start harness run"
          >
            <svg
              className="harness-arrow-up-svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 17a1 1 0 01-1-1V5.414L5.707 8.707a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0l5 5a1 1 0 01-1.414 1.414L11 5.414V16a1 1 0 01-1 1z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
