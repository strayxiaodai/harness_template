import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { CenterColumn } from './components/CenterColumn'
import { ColumnSplit } from './components/ColumnSplit'
import { CommandColumn } from './components/CommandColumn'
import { InspectorStack } from './components/InspectorStack'
import { SettingsModal } from './components/SettingsModal'
import { Sidebar } from './components/Sidebar'
import { StatusBar } from './components/StatusBar'
import { useConsole } from './hooks/useConsole'
import { useResumeDraft } from './hooks/useResumeDraft'
import { useHealth } from './hooks/useHealth'
import { useResizableColumns } from './hooks/useResizableColumns'
import { useSettings } from './hooks/useSettings'
import { useSkills } from './hooks/useSkills'
import { useThreads } from './hooks/useThreads'
import {
  isClarificationInterrupt,
} from './lib/clarification'
import {
  actionReviewMeta,
  isActionReviewInterrupt,
} from './lib/actionReview'
import {
  resolveSkillEligible,
  resolveSkillIneligibleReason,
} from './lib/skillEligibility'
import type { GraphNode } from './types/api'
import './App.css'

function App() {
  const { status, detail } = useHealth()
  const {
    widths,
    desktop,
    setInspectorWidth,
    setCommandWidth,
    resetWidths,
  } = useResizableColumns()
  const {
    threadId,
    task,
    setTask,
    planText,
    setPlanText,
    maxRounds,
    setMaxRounds,
    humanInTheLoop,
    setHumanInTheLoop,
    taskRewrite,
    setTaskRewrite,
    setTimeoutSeconds,
    phase,
    activeNode,
    accumulated,
    timeline,
    selectedStep,
    selectedStepId,
    runResponse,
    error,
    refineFrom,
    skillName,
    setSkillName,
    distillResult,
    distillBusy,
    run,
    runSkill,
    resume,
    distillSkill,
    saveSkill,
    discardSkill,
    resetThread,
    attachThread,
    selectStep,
    selectAdjacent,
    clearError,
  } = useConsole()

  const {
    threads,
    loading: threadsLoading,
    error: threadsError,
    refreshThreads,
  } = useThreads()

  const {
    skills,
    selectedSlug,
    selectedSkill,
    loading: skillsLoading,
    detailLoading: skillDetailLoading,
    error: skillsError,
    refreshSkills,
    selectSkill,
    clearError: clearSkillsError,
  } = useSkills()

  const {
    systemSettings,
    userSettings,
    updateUserSettings,
  } = useSettings()

  const [settingsOpen, setSettingsOpen] = useState(false)

  // Initialize console parameters from user settings
  const settingsInitializedRef = useRef(false)
  useEffect(() => {
    if (!settingsInitializedRef.current) {
      settingsInitializedRef.current = true
      setTaskRewrite(userSettings.taskRewriteEnabled)
      setHumanInTheLoop(userSettings.humanInTheLoop)
      setMaxRounds(userSettings.maxRounds)
      setTimeoutSeconds(userSettings.timeoutSeconds)
    }
  }, [
    userSettings.taskRewriteEnabled,
    userSettings.humanInTheLoop,
    userSettings.maxRounds,
    userSettings.timeoutSeconds,
    setTaskRewrite,
    setHumanInTheLoop,
    setMaxRounds,
    setTimeoutSeconds,
  ])

  const completedNodes = useMemo(() => {
    const set = new Set<string>()
    for (const step of timeline) {
      set.add(step.node)
    }
    return set
  }, [timeline])

  const rounds = runResponse?.rounds ?? accumulated.rounds ?? 0
  const maxRoundsDisplay = runResponse?.max_rounds ?? maxRounds
  const skillEligible = resolveSkillEligible(
    runResponse,
    accumulated,
    rounds,
    timeline,
  )
  const skillIneligibleReason = resolveSkillIneligibleReason(runResponse)

  const [timelineOpen, setTimelineOpen] = useState(false)

  const draft = useResumeDraft(phase, runResponse?.interrupt ?? null)
  const { buildPayload } = draft
  const clarifying =
    phase === 'awaiting_human' &&
    isClarificationInterrupt(runResponse?.interrupt ?? null)
  const actionReviewing =
    phase === 'awaiting_human' &&
    isActionReviewInterrupt(runResponse?.interrupt ?? null)
  const [inspectorCollapsed, setInspectorCollapsed] = useState(
    clarifying || actionReviewing,
  )

  const handleSelectNode = useCallback(
    (node: GraphNode) => {
      const match = [...timeline].reverse().find((s) => s.node === node)
      if (match) {
        selectStep(match.id)
      }
    },
    [selectStep, timeline],
  )

  const handleContinue = useCallback(() => {
    const { overrides, answers, interrupt_resume } = buildPayload()
    void resume(overrides, answers, interrupt_resume)
  }, [buildPayload, resume])

  const heroProps = useMemo(
    () => ({
      task,
      onTaskChange: setTask,
      taskRewrite,
      onTaskRewriteChange: setTaskRewrite,
      humanInTheLoop,
      onHitlChange: setHumanInTheLoop,
      planText,
      onPlanChange: setPlanText,
      skills,
      selectedSkillSlug: selectedSlug,
      onSkillSelect: (slug: string) => void selectSkill(slug),
      onRun: () => void run(),
      isStreaming: phase === 'streaming',
      workspaceName: threadId ? `Session ${threadId.slice(0, 8)}…` : 'Default workspace',
    }),
    [
      task,
      setTask,
      taskRewrite,
      setTaskRewrite,
      humanInTheLoop,
      setHumanInTheLoop,
      planText,
      setPlanText,
      skills,
      selectedSlug,
      selectSkill,
      run,
      phase,
      threadId,
    ],
  )

  useEffect(() => {
    if (clarifying || actionReviewing) {
      setInspectorCollapsed(true)
    }
  }, [clarifying, actionReviewing])

  useEffect(() => {
    if (phase === 'complete' || phase === 'awaiting_human') {
      void refreshThreads()
    }
  }, [phase, refreshThreads])

  const phaseRef = useRef(phase)
  useEffect(() => {
    phaseRef.current = phase
  }, [phase])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return
      }
      if (e.key === 'j') {
        e.preventDefault()
        selectAdjacent(1)
        setTimelineOpen(true)
      }
      if (e.key === 'k') {
        e.preventDefault()
        selectAdjacent(-1)
        setTimelineOpen(true)
      }
      if (e.key === 'r' && phaseRef.current === 'awaiting_human') {
        e.preventDefault()
        handleContinue()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handleContinue, selectAdjacent])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <h1 className="sr-only">Harness Console</h1>

      <Sidebar
        threads={threads}
        activeThreadId={threadId}
        onSelectThread={(t) =>
          attachThread({
            threadId: t.thread_id,
            task: t.task,
            plan: t.plan,
          })
        }
        onNewSession={resetThread}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className="app-main-viewport">
        <StatusBar
          health={status}
          healthDetail={detail}
          threadId={threadId}
          phase={phase}
          rounds={rounds}
          maxRounds={maxRoundsDisplay}
          humanInTheLoop={humanInTheLoop}
          nextAction={runResponse?.next_action ?? null}
          threads={threads}
          threadsLoading={threadsLoading}
          threadsError={threadsError}
          onAttachThread={(thread) =>
            attachThread({
              threadId: thread.thread_id,
              task: thread.task,
              plan: thread.plan,
            })
          }
          onRefreshThreads={() => {
            void refreshThreads()
          }}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        <main
          className={
            desktop && inspectorCollapsed
              ? 'app-main app-main--inspector-collapsed'
              : 'app-main'
          }
          id="main-content"
          style={
            {
              '--col-inspector': `${widths.inspector}px`,
              '--col-command': `${widths.command}px`,
            } as CSSProperties
          }
        >
          <InspectorStack
            mode="secondary"
            step={selectedStep}
            accumulated={accumulated}
            collapsed={desktop && inspectorCollapsed}
            onExpand={() => setInspectorCollapsed(false)}
            onCollapse={() => setInspectorCollapsed(true)}
          />

          {desktop && !inspectorCollapsed && (
            <ColumnSplit
              side="inspector"
              disabled={!desktop}
              label="Resize inspector column"
              onResize={setInspectorWidth}
              onReset={resetWidths}
            />
          )}

          <CenterColumn
            activeNode={activeNode}
            completedNodes={completedNodes}
            refineFrom={refineFrom}
            onSelectNode={handleSelectNode}
            phase={phase}
            interrupt={runResponse?.interrupt ?? null}
            selectedStep={selectedStep}
            questions={draft.questions}
            answerDrafts={draft.answerDrafts}
            onAnswerChange={draft.setAnswer}
            memories={draft.memories}
            memoryDrafts={draft.memoryDrafts}
            actionReviewMeta={actionReviewMeta(runResponse?.interrupt ?? null)}
            onMemoryDraftChange={draft.setMemoryDraft}
            planOverrideText={draft.planOverrideText}
            refineOverride={draft.refineOverride}
            onPlanOverrideChange={draft.setPlanOverrideText}
            onRefineOverrideChange={draft.setRefineOverride}
            onContinue={handleContinue}
            streaming={phase === 'streaming'}
            steps={timeline}
            selectedStepId={selectedStepId}
            onSelectStep={selectStep}
            timelineOpen={timelineOpen}
            onTimelineOpenChange={setTimelineOpen}
            heroProps={heroProps}
          />

          <ColumnSplit
            side="command"
            disabled={!desktop}
            label="Resize command column"
            onResize={setCommandWidth}
            onReset={resetWidths}
          />

          <CommandColumn
            task={task}
            taskRewrite={taskRewrite}
            planText={planText}
            maxRounds={maxRounds}
            humanInTheLoop={humanInTheLoop}
            phase={phase}
            error={error}
            skillsError={skillsError}
            skills={skills}
            selectedSkillSlug={selectedSlug}
            selectedSkill={selectedSkill}
            skillsLoading={skillsLoading}
            skillDetailLoading={skillDetailLoading}
            skillName={skillName}
            distillResult={distillResult}
            distillBusy={distillBusy}
            planOverrideText={draft.planOverrideText}
            refineOverride={draft.refineOverride}
            showSecondaryContinue={phase === 'awaiting_human'}
            onTaskChange={setTask}
            onTaskRewriteChange={setTaskRewrite}
            onPlanChange={setPlanText}
            onMaxRoundsChange={setMaxRounds}
            onHitlChange={setHumanInTheLoop}
            onPlanOverrideChange={draft.setPlanOverrideText}
            onRefineOverrideChange={draft.setRefineOverride}
            onSkillNameChange={setSkillName}
            onSkillSelect={(slug) => void selectSkill(slug)}
            onRefreshSkills={() => void refreshSkills()}
            onClearSkillsError={clearSkillsError}
            onRun={() => void run()}
            onRunSkill={() => void runSkill(selectedSlug)}
            onResume={handleContinue}
            onDistillSkill={() => void distillSkill()}
            onSaveSkill={async () => {
              await saveSkill()
              void refreshSkills()
            }}
            onDiscardSkill={discardSkill}
            onReset={resetThread}
            onClearError={clearError}
            skillEligible={skillEligible}
            skillIneligibleReason={skillIneligibleReason}
          />
        </main>

        <footer className="app-footer">
          <section aria-label="Keyboard shortcuts" className="app-footer__shortcuts">
            <kbd className="kbd">j</kbd>/<kbd className="kbd">k</kbd> timeline
            <span aria-hidden="true"> · </span>
            <kbd className="kbd">r</kbd> resume when interrupted
            <span aria-hidden="true"> · </span>
            drag column edges to resize
            <span aria-hidden="true"> · </span>
            Tab to skip link and panels
          </section>
        </footer>
      </div>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        systemSettings={systemSettings}
        userSettings={userSettings}
        onUpdateUserSettings={(patch) => {
          updateUserSettings(patch)
          if (patch.taskRewriteEnabled !== undefined) {
            setTaskRewrite(patch.taskRewriteEnabled)
          }
          if (patch.humanInTheLoop !== undefined) {
            setHumanInTheLoop(patch.humanInTheLoop)
          }
          if (patch.maxRounds !== undefined) {
            setMaxRounds(patch.maxRounds)
          }
          if (patch.timeoutSeconds !== undefined) {
            setTimeoutSeconds(patch.timeoutSeconds)
          }
        }}
        onResetColumnWidths={resetWidths}
      />
    </div>
  )
}

export default App
