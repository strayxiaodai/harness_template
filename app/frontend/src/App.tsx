import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { CenterColumn } from './components/CenterColumn'
import { ColumnSplit } from './components/ColumnSplit'
import { CommandColumn } from './components/CommandColumn'
import { InspectorStack } from './components/InspectorStack'
import { StatusBar } from './components/StatusBar'
import { useConsole } from './hooks/useConsole'
import { useResumeDraft } from './hooks/useResumeDraft'
import { useHealth } from './hooks/useHealth'
import { useResizableColumns } from './hooks/useResizableColumns'
import { useSkills } from './hooks/useSkills'
import {
  isClarificationInterrupt,
} from './lib/clarification'
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
    selectStep,
    selectAdjacent,
    clearError,
  } = useConsole()

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
  const [inspectorCollapsed, setInspectorCollapsed] = useState(clarifying)

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

  useEffect(() => {
    if (clarifying) {
      setInspectorCollapsed(true)
    }
  }, [clarifying])

  const phaseRef = useRef(phase)
  phaseRef.current = phase

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
      <StatusBar
        health={status}
        healthDetail={detail}
        threadId={threadId}
        phase={phase}
        rounds={rounds}
        maxRounds={maxRoundsDisplay}
        humanInTheLoop={humanInTheLoop}
        nextAction={runResponse?.next_action ?? null}
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
  )
}

export default App
