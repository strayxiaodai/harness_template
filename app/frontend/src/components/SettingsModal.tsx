import { useEffect, useState } from 'react'
import type { SystemSettingsResponse, UserSettings } from '../types/api'
import './SettingsModal.css'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
  systemSettings: SystemSettingsResponse | null
  userSettings: UserSettings
  onUpdateUserSettings: (settings: Partial<UserSettings>) => void
  onResetColumnWidths?: () => void
}

type SettingsTab =
  | 'overview'
  | 'general'
  | 'models'
  | 'plugins'
  | 'skills'

export function SettingsModal({
  open,
  onClose,
  systemSettings,
  userSettings,
  onUpdateUserSettings,
  onResetColumnWidths,
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('overview')

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  const mcpServers = systemSettings?.mcp?.servers ?? {}
  const mcpServerKeys = Object.keys(mcpServers)
  const mcpTools = systemSettings?.mcp?.tools ?? []
  const isMcpEnabled = systemSettings?.mcp?.enabled ?? false
  const activeProvider =
    userSettings.llmProvider || systemSettings?.llm_provider || 'openai'
  const activeModel =
    userSettings.llmModel || 'gpt-4o'

  return (
    <div
      className="harness-settings-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="harness-settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="harness-settings-heading"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="harness-settings-header">
          <h2 id="harness-settings-heading" className="harness-settings-title">
            Settings &amp; Harness Config
          </h2>
          <div className="harness-settings-header__actions">
            <button
              type="button"
              className="harness-config-btn"
              onClick={() => {
                alert(
                  'Configuration sources:\n- Environment: .env\n- Prompts: config/prompts.yaml\n- MCP Servers: mcp/servers.json\n- Skills: .agents/skills/',
                )
              }}
            >
              Configuration Files
            </button>
            <button
              type="button"
              className="harness-close-btn"
              onClick={onClose}
              aria-label="Close settings"
            >
              <svg
                viewBox="0 0 16 16"
                fill="currentColor"
                className="harness-close-icon"
              >
                <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z" />
              </svg>
            </button>
          </div>
        </header>

        {/* Content Layout */}
        <div className="harness-settings-body">
          {/* Left Navigation Sidebar */}
          <nav
            className="harness-settings-sidebar"
            aria-label="Settings categories"
          >
            <button
              type="button"
              className={`harness-nav-item ${
                activeTab === 'overview' ? 'harness-nav-item--active' : ''
              }`}
              onClick={() => setActiveTab('overview')}
            >
              <span className="harness-nav-item__icon">🖥️</span>
              <span>Engine Status</span>
            </button>

            <button
              type="button"
              className={`harness-nav-item ${
                activeTab === 'general' ? 'harness-nav-item--active' : ''
              }`}
              onClick={() => setActiveTab('general')}
            >
              <span className="harness-nav-item__icon">⚙️</span>
              <span>General Loop</span>
            </button>

            <button
              type="button"
              className={`harness-nav-item ${
                activeTab === 'models' ? 'harness-nav-item--active' : ''
              }`}
              onClick={() => setActiveTab('models')}
            >
              <span className="harness-nav-item__icon">🗄️</span>
              <span>Models &amp; LLMs</span>
            </button>

            <button
              type="button"
              className={`harness-nav-item ${
                activeTab === 'plugins' ? 'harness-nav-item--active' : ''
              }`}
              onClick={() => setActiveTab('plugins')}
            >
              <span className="harness-nav-item__icon">🧩</span>
              <span>MCP &amp; Plugins</span>
              {mcpServerKeys.length > 0 && (
                <span className="harness-nav-pill">{mcpServerKeys.length}</span>
              )}
            </button>

            <button
              type="button"
              className={`harness-nav-item ${
                activeTab === 'skills' ? 'harness-nav-item--active' : ''
              }`}
              onClick={() => setActiveTab('skills')}
            >
              <span className="harness-nav-item__icon">🤖</span>
              <span>Skills &amp; Presets</span>
            </button>
          </nav>

          {/* Right Main Content */}
          <main className="harness-settings-main">
            {activeTab === 'overview' && (
              <div className="harness-cards-stack">
                {/* Engine Runtime Card */}
                <div className="harness-card harness-overview-card">
                  <div className="harness-overview-card__left">
                    <div className="harness-overview-avatar">
                      <span className="harness-pulse-dot" />
                    </div>
                    <div className="harness-overview-info">
                      <h4 className="harness-overview-name">
                        Harness Engine (Local Runtime)
                      </h4>
                      <p className="harness-overview-detail">
                        API: <code>http://localhost:8000</code> • Checkpointer:{' '}
                        <code>SQLite (async)</code>
                      </p>
                    </div>
                  </div>
                  <span className="harness-status-badge harness-status-badge--live">
                    Online &amp; Healthy
                  </span>
                </div>

                {/* Diagnostics / Loop Architecture Card */}
                <div className="harness-card">
                  <h4 className="harness-card-title">LangGraph Execution Loop</h4>
                  <div className="harness-prop-row">
                    <span>Graph Architecture</span>
                    <span className="mono">
                      Planner ➔ Executor ➔ Learner ➔ Actioner
                    </span>
                  </div>
                  <div className="harness-prop-row">
                    <span>Task Prompt Rewrite</span>
                    <span
                      className={`harness-tag ${
                        userSettings.taskRewriteEnabled
                          ? 'harness-tag--ok'
                          : 'harness-tag--muted'
                      }`}
                    >
                      {userSettings.taskRewriteEnabled
                        ? 'Active (Structured Spec)'
                        : 'Raw Input'}
                    </span>
                  </div>
                  <div className="harness-prop-row">
                    <span>Human-in-the-Loop Mode</span>
                    <span
                      className={`harness-tag ${
                        userSettings.humanInTheLoop
                          ? 'harness-tag--accent'
                          : 'harness-tag--muted'
                      }`}
                    >
                      {userSettings.humanInTheLoop
                        ? 'Pauses at node boundaries'
                        : 'Autonomous loop'}
                    </span>
                  </div>
                  <div className="harness-prop-row">
                    <span>MCP Tool Integration</span>
                    <span className="harness-tag">
                      {isMcpEnabled
                        ? `${mcpServerKeys.length} server(s), ${mcpTools.length} tool(s)`
                        : 'Disabled (HARNESS_MCP_ENABLED=false)'}
                    </span>
                  </div>
                </div>

                {/* Active Providers Card */}
                <div className="harness-card">
                  <h4 className="harness-card-title">Model Provider</h4>
                  <div className="harness-prop-row">
                    <span>Primary LLM</span>
                    <span className="mono">
                      {activeProvider} / {activeModel}
                    </span>
                  </div>
                  <div className="harness-prop-row">
                    <span>RAG Vector Memory</span>
                    <span className="mono">
                      {systemSettings?.rag_enabled ? 'Active (ChromaDB)' : 'Disabled'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'general' && (
              <div className="harness-cards-stack">
                <div className="harness-card">
                  <h4 className="harness-card-title">Agent Execution Controls</h4>

                  {/* Task Rewrite */}
                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-task-rewrite"
                        className="harness-setting-label"
                      >
                        Task Prompt Rewrite (<code>TASK_REWRITE_ENABLED</code>)
                      </label>
                      <p className="harness-setting-desc">
                        Automatically rewrites raw user prompts before Planner execution into
                        a standardized engineering specification:
                        <br />
                        <code>
                          # Role, # Context, # Objectives, # Specs, # Constraints, # Acceptance Criteria
                        </code>
                      </p>
                    </div>
                    <input
                      id="harness-task-rewrite"
                      type="checkbox"
                      className="harness-switch"
                      checked={userSettings.taskRewriteEnabled}
                      onChange={(e) =>
                        onUpdateUserSettings({
                          taskRewriteEnabled: e.target.checked,
                        })
                      }
                    />
                  </div>

                  {/* HITL */}
                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-hitl"
                        className="harness-setting-label"
                      >
                        Human in the Loop (HITL Interrupts)
                      </label>
                      <p className="harness-setting-desc">
                        Pauses execution at graph node boundaries so you can inspect proposed
                        actions, edit tool inputs, or clarify requirements before proceeding.
                      </p>
                    </div>
                    <input
                      id="harness-hitl"
                      type="checkbox"
                      className="harness-switch"
                      checked={userSettings.humanInTheLoop}
                      onChange={(e) =>
                        onUpdateUserSettings({ humanInTheLoop: e.target.checked })
                      }
                    />
                  </div>
                </div>

                <div className="harness-card">
                  <h4 className="harness-card-title">Limits &amp; Safety</h4>

                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-max-rounds"
                        className="harness-setting-label"
                      >
                        Max Planning Rounds
                      </label>
                      <p className="harness-setting-desc">
                        Maximum loop iterations before the graph halts (configured via{' '}
                        <code>HARNESS_MAX_ROUNDS</code>).
                      </p>
                    </div>
                    <input
                      id="harness-max-rounds"
                      type="number"
                      min={1}
                      max={50}
                      className="harness-input harness-input--number"
                      value={userSettings.maxRounds}
                      onChange={(e) =>
                        onUpdateUserSettings({
                          maxRounds: Math.max(1, parseInt(e.target.value) || 10),
                        })
                      }
                    />
                  </div>

                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-timeout"
                        className="harness-setting-label"
                      >
                        Task Execution Timeout (seconds)
                      </label>
                      <p className="harness-setting-desc">
                        Task deadline before aborting long-running executor processes.
                      </p>
                    </div>
                    <input
                      id="harness-timeout"
                      type="number"
                      min={10}
                      max={1800}
                      className="harness-input harness-input--number"
                      value={userSettings.timeoutSeconds}
                      onChange={(e) =>
                        onUpdateUserSettings({
                          timeoutSeconds: Math.max(
                            10,
                            parseInt(e.target.value) || 120,
                          ),
                        })
                      }
                    />
                  </div>

                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-autoscroll"
                        className="harness-setting-label"
                      >
                        Auto-expand Timeline Stream
                      </label>
                      <p className="harness-setting-desc">
                        Automatically expands newly created steps in the execution timeline.
                      </p>
                    </div>
                    <input
                      id="harness-autoscroll"
                      type="checkbox"
                      className="harness-switch"
                      checked={userSettings.autoExpandTimeline}
                      onChange={(e) =>
                        onUpdateUserSettings({
                          autoExpandTimeline: e.target.checked,
                        })
                      }
                    />
                  </div>

                  {onResetColumnWidths && (
                    <div className="harness-setting-row">
                      <div className="harness-setting-row__info">
                        <span className="harness-setting-label">
                          Reset Layout Widths
                        </span>
                        <p className="harness-setting-desc">
                          Reset the three-column console panels to default proportions.
                        </p>
                      </div>
                      <button
                        type="button"
                        className="harness-btn harness-btn--outline"
                        onClick={onResetColumnWidths}
                      >
                        Reset Columns
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'models' && (
              <div className="harness-cards-stack">
                <div className="harness-card">
                  <h4 className="harness-card-title">LLM Provider Configuration</h4>
                  <p className="harness-card-desc">
                    Select your active model provider. Provider API keys must be configured in{' '}
                    <code>.env</code>.
                  </p>

                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-provider-select"
                        className="harness-setting-label"
                      >
                        Active Provider
                      </label>
                      <p className="harness-setting-desc">
                        Supported: OpenAI, Anthropic, Ollama, vLLM, Gemini.
                      </p>
                    </div>
                    <select
                      id="harness-provider-select"
                      className="harness-select"
                      value={activeProvider}
                      onChange={(e) =>
                        onUpdateUserSettings({ llmProvider: e.target.value })
                      }
                    >
                      <option value="openai">OpenAI (GPT-4o, o3)</option>
                      <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                      <option value="ollama">Ollama (Local Qwen / Llama)</option>
                      <option value="vllm">vLLM (Self-hosted OpenAI-compatible)</option>
                      <option value="gemini">Google Gemini (Gemini 2.0 Flash)</option>
                    </select>
                  </div>

                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-model-name"
                        className="harness-setting-label"
                      >
                        Model Identifier
                      </label>
                      <p className="harness-setting-desc">
                        Model string passed to provider (e.g. <code>gpt-4o</code>,{' '}
                        <code>claude-3-5-sonnet-latest</code>, <code>qwen2.5-coder:32b</code>).
                      </p>
                    </div>
                    <input
                      id="harness-model-name"
                      type="text"
                      className="harness-input"
                      value={activeModel}
                      onChange={(e) =>
                        onUpdateUserSettings({ llmModel: e.target.value })
                      }
                    />
                  </div>

                  <div className="harness-setting-row">
                    <div className="harness-setting-row__info">
                      <label
                        htmlFor="harness-base-url"
                        className="harness-setting-label"
                      >
                        Custom Base URL (Local / Proxy)
                      </label>
                      <p className="harness-setting-desc">
                        Endpoint for local servers like Ollama (<code>http://localhost:11434/v1</code>)
                        or vLLM.
                      </p>
                    </div>
                    <input
                      id="harness-base-url"
                      type="text"
                      placeholder="https://api.openai.com/v1"
                      className="harness-input"
                      value={userSettings.llmBaseUrl || ''}
                      onChange={(e) =>
                        onUpdateUserSettings({ llmBaseUrl: e.target.value })
                      }
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'plugins' && (
              <div className="harness-cards-stack">
                <div className="harness-card">
                  <div className="harness-card__header-row">
                    <div>
                      <h4 className="harness-card-title">Model Context Protocol (MCP)</h4>
                      <p className="harness-card-desc">
                        Harness executes external tools via MCP servers defined in{' '}
                        <code>mcp/servers.json</code>.
                      </p>
                    </div>
                    <span
                      className={`harness-tag ${
                        isMcpEnabled ? 'harness-tag--ok' : 'harness-tag--muted'
                      }`}
                    >
                      {isMcpEnabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>

                  <div className="harness-mcp-status-block">
                    <div className="harness-prop-row">
                      <span>Server count</span>
                      <span className="mono">{mcpServerKeys.length}</span>
                    </div>
                    <div className="harness-prop-row">
                      <span>Discovered tools</span>
                      <span className="mono">{mcpTools.length}</span>
                    </div>
                  </div>
                </div>

                {mcpServerKeys.length > 0 ? (
                  <div className="harness-card">
                    <h4 className="harness-card-title">Configured MCP Servers</h4>
                    <div className="harness-servers-list">
                      {mcpServerKeys.map((name) => {
                        const srv = mcpServers[name]
                        return (
                          <div key={name} className="harness-server-row">
                            <div className="harness-server-row__info">
                              <span className="harness-server-name mono">{name}</span>
                              <span className="harness-server-transport">
                                {srv.transport || 'stdio'}
                              </span>
                            </div>
                            <span className="harness-tag harness-tag--ok">Active</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="harness-card harness-empty-card">
                    <p>No MCP servers registered in <code>mcp/servers.json</code>.</p>
                    <p className="harness-setting-desc">
                      Add server configs to <code>mcp/servers.json</code> to make tools available
                      to the Harness Executor node.
                    </p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'skills' && (
              <div className="harness-cards-stack">
                <div className="harness-card">
                  <h4 className="harness-card-title">Harness Skills &amp; Presets</h4>
                  <p className="harness-card-desc">
                    Skills provide reusable procedural prompts and behavioral instructions
                    loaded by the Planner and Executor.
                  </p>

                  <div className="harness-skills-list">
                    <div className="harness-skill-item">
                      <div className="harness-skill-item__head">
                        <span className="harness-skill-title">impeccable</span>
                        <span className="harness-tag">Frontend &amp; UX</span>
                      </div>
                      <p className="harness-skill-desc">
                        Design, polish, clarify, distill, harden, and optimize frontend interfaces
                        with meticulous visual hierarchy and accessibility standards.
                      </p>
                    </div>

                    <div className="harness-skill-item">
                      <div className="harness-skill-item__head">
                        <span className="harness-skill-title">task_rewrite</span>
                        <span className="harness-tag harness-tag--ok">Prompt Spec</span>
                      </div>
                      <p className="harness-skill-desc">
                        Synthesizes ambiguous task descriptions into high-clarity engineering
                        prompts with explicit roles, constraints, and verifiable acceptance criteria.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}
