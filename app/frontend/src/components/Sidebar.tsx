import { useState } from 'react'
import type { ThreadSummary } from '../types/api'
import { formatThreadSelectLabel } from '../lib/threadAttach'
import './Sidebar.css'

interface SidebarProps {
  threads: ThreadSummary[]
  activeThreadId: string
  onSelectThread: (thread: ThreadSummary) => void
  onNewSession: () => void
  onOpenSettings: () => void
  onOpenPlugins?: () => void
  onOpenSkills?: () => void
}

export function Sidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewSession,
  onOpenSettings,
  onOpenPlugins,
  onOpenSkills,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [showSearch, setShowSearch] = useState(false)

  const filteredThreads = threads.filter((t) =>
    (t.task || t.thread_id).toLowerCase().includes(searchQuery.toLowerCase()),
  )

  return (
    <aside className="harness-sidebar" aria-label="Sidebar navigation">
      {/* Brand Header */}
      <div className="harness-brand">
        <div className="harness-brand__logo-cluster">
          {/* Harness Node Graph Icon */}
          <svg
            className="harness-logo-icon"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <circle cx="5" cy="12" r="3" fill="#4d6cb0" />
            <circle cx="12" cy="5" r="3" fill="#4d6cb0" />
            <circle cx="12" cy="19" r="3" fill="#4d6cb0" />
            <circle cx="19" cy="12" r="3" fill="#4d6cb0" />
            <path
              d="M7.5 10.5L9.5 6.5M7.5 13.5L9.5 17.5M14.5 6.5L16.5 10.5M14.5 17.5L16.5 13.5"
              stroke="#6b86c2"
              strokeWidth="1.5"
            />
          </svg>
          <span className="harness-brand__wordmark">Harness</span>
          <span className="harness-brand__badge">CONSOLE</span>
        </div>
      </div>

      {/* New Session Button */}
      <div className="harness-action-section">
        <button
          type="button"
          className="harness-new-session-btn"
          onClick={onNewSession}
        >
          <span className="harness-plus-icon">+</span>
          <span>New Session</span>
        </button>
      </div>

      {/* Primary Navigation Menu */}
      <nav className="harness-nav" aria-label="Main navigation">
        <button
          type="button"
          className="harness-nav__item"
          onClick={onOpenPlugins ?? onOpenSettings}
        >
          <span className="harness-nav__icon">🧩</span>
          <span>Plugins & MCP</span>
        </button>
        <button
          type="button"
          className="harness-nav__item"
          onClick={onOpenSkills}
        >
          <span className="harness-nav__icon">⏱️</span>
          <span>Automation tasks</span>
        </button>
        <button
          type="button"
          className="harness-nav__item"
          onClick={onOpenSettings}
        >
          <span className="harness-nav__icon">⚙️</span>
          <span>Settings</span>
        </button>
      </nav>

      {/* Workspaces Section */}
      <div className="harness-workspaces">
        <div className="harness-workspaces__header">
          <span className="harness-workspaces__title">Workspaces</span>
          <div className="harness-workspaces__tools">
            <button
              type="button"
              className="harness-icon-btn"
              title="Search workspaces"
              onClick={() => setShowSearch(!showSearch)}
              aria-label="Search workspaces"
            >
              🔍
            </button>
            <button
              type="button"
              className="harness-icon-btn"
              title="Workspace settings"
              onClick={onOpenSettings}
              aria-label="Workspace settings"
            >
              ⚙
            </button>
            <button
              type="button"
              className="harness-icon-btn"
              title="New workspace session"
              onClick={onNewSession}
              aria-label="New workspace session"
            >
              ⊞
            </button>
          </div>
        </div>

        {showSearch && (
          <div className="harness-workspaces__search">
            <input
              type="text"
              className="harness-search-input"
              placeholder="Search sessions…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
          </div>
        )}

        <div className="harness-workspaces__list">
          <button
            type="button"
            className={`harness-workspace-item ${
              activeThreadId === 'default' ? 'harness-workspace-item--active' : ''
            }`}
            onClick={onNewSession}
          >
            <span className="harness-folder-icon">📁</span>
            <span className="harness-workspace-item__name">Default workspace</span>
          </button>

          {filteredThreads.map((thread) => {
            const isActive = thread.thread_id === activeThreadId
            return (
              <button
                key={thread.thread_id}
                type="button"
                className={`harness-workspace-item ${
                  isActive ? 'harness-workspace-item--active' : ''
                }`}
                onClick={() => onSelectThread(thread)}
                title={thread.task || thread.thread_id}
              >
                <span className="harness-folder-icon">📁</span>
                <span className="harness-workspace-item__name">
                  {formatThreadSelectLabel(thread)}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Engine Status / Settings Footer */}
      <div className="harness-footer">
        <button
          type="button"
          className="harness-user-pill"
          onClick={onOpenSettings}
          title="Open harness engine settings"
        >
          <div className="harness-user-avatar">
            <span className="harness-status-dot" />
          </div>
          <span className="harness-user-name">Harness Engine (Local)</span>
          <span className="harness-gear-indicator">⚙</span>
        </button>
      </div>
    </aside>
  )
}
