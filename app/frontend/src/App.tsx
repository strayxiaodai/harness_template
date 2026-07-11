import { useCallback, useEffect, useMemo, useRef } from 'react'
import { CommandColumn } from './components/CommandColumn'
import { GraphSpine } from './components/GraphSpine'
import { InspectorStack } from './components/InspectorStack'
import { StatusBar } from './components/StatusBar'
import { TraceTimeline } from './components/TraceTimeline'
import { useConsole } from './hooks/useConsole'
import { useHealth } from './hooks/useHealth'
import { useSkills } from './hooks/useSkills'
import {
  resolveSkillEligible,
  resolveSkillIneligibleReason,
} from './lib/skillEligibility'
import type { GraphNode } from './types/api'
import './App.css'

function App() {
  const { status, detail } = useHealth()
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

  const handleSelectNode = useCallback(
    (node: GraphNode) => {
      const match = [...timeline].reverse().find((s) => s.node === node)
      if (match) {
        selectStep(match.id)
      }
    },
    [selectStep, timeline],
  )

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
      }
      if (e.key === 'k') {
        e.preventDefault()
        selectAdjacent(-1)
      }
      if (e.key === 'r' && phaseRef.current === 'awaiting_human') {
        e.preventDefault()
        void resume()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [resume, selectAdjacent])

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

      <main className="app-main" id="main-content">
        <InspectorStack
          step={selectedStep}
          accumulated={accumulated}
        />

        <GraphSpine
          activeNode={activeNode}
          completedNodes={completedNodes}
          refineFrom={refineFrom}
          onSelectNode={handleSelectNode}
        />

        <TraceTimeline
          steps={timeline}
          selectedId={selectedStepId}
          activeNode={activeNode}
          onSelect={selectStep}
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
          onTaskChange={setTask}
          onPlanChange={setPlanText}
          onMaxRoundsChange={setMaxRounds}
          onHitlChange={setHumanInTheLoop}
          onSkillNameChange={setSkillName}
          onSkillSelect={(slug) => void selectSkill(slug)}
          onRefreshSkills={() => void refreshSkills()}
          onClearSkillsError={clearSkillsError}
          onRun={() => void run()}
          onRunSkill={() => void runSkill(selectedSlug)}
          onResume={(o, answers) => void resume(o, answers)}
          onDistillSkill={() => void distillSkill()}
          onSaveSkill={async () => {
            await saveSkill()
            void refreshSkills()
          }}
          onDiscardSkill={discardSkill}
          onReset={resetThread}
          onClearError={clearError}
          nextAction={runResponse?.next_action ?? null}
          interrupt={runResponse?.interrupt ?? null}
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
          Tab to skip link and panels
        </section>
      </footer>
    </div>
  )
}

export default App
