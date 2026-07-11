import { GraphSpine } from './GraphSpine'
import { Workplace } from './Workplace'
import { TraceTimeline } from './TraceTimeline'
import type {
  ClarificationQuestion,
  GraphNode,
  InterruptPayload,
  ResumeOverrides,
  TimelineStep,
} from '../types/api'
import type { RunPhase } from '../hooks/useConsole'
import './CenterColumn.css'

interface CenterColumnProps {
  activeNode: string | null
  completedNodes: Set<string>
  refineFrom: string | null
  onSelectNode: (node: GraphNode) => void
  phase: RunPhase
  interrupt: InterruptPayload | null
  selectedStep: TimelineStep | null
  questions: ClarificationQuestion[]
  answerDrafts: Record<string, string>
  onAnswerChange: (id: string, value: string) => void
  planOverrideText: string
  refineOverride: ResumeOverrides['refine_from'] | ''
  onPlanOverrideChange: (value: string) => void
  onRefineOverrideChange: (
    value: ResumeOverrides['refine_from'] | '',
  ) => void
  onContinue: () => void
  streaming: boolean
  steps: TimelineStep[]
  selectedStepId: string | null
  onSelectStep: (id: string) => void
  timelineOpen: boolean
  onTimelineOpenChange: (open: boolean) => void
}

export function CenterColumn({
  activeNode,
  completedNodes,
  refineFrom,
  onSelectNode,
  phase,
  interrupt,
  selectedStep,
  questions,
  answerDrafts,
  onAnswerChange,
  planOverrideText,
  refineOverride,
  onPlanOverrideChange,
  onRefineOverrideChange,
  onContinue,
  streaming,
  steps,
  selectedStepId,
  onSelectStep,
  timelineOpen,
  onTimelineOpenChange,
}: CenterColumnProps) {
  const handleSelectStep = (id: string) => {
    onSelectStep(id)
    onTimelineOpenChange(true)
  }

  const handleSelectNode = (node: GraphNode) => {
    onSelectNode(node)
    onTimelineOpenChange(true)
  }

  return (
    <div className="center-column">
      <GraphSpine
        activeNode={activeNode}
        completedNodes={completedNodes}
        refineFrom={refineFrom}
        onSelectNode={handleSelectNode}
      />
      <Workplace
        phase={phase}
        interrupt={interrupt}
        selectedStep={selectedStep}
        questions={questions}
        answerDrafts={answerDrafts}
        onAnswerChange={onAnswerChange}
        planOverrideText={planOverrideText}
        refineOverride={refineOverride}
        onPlanOverrideChange={onPlanOverrideChange}
        onRefineOverrideChange={onRefineOverrideChange}
        onContinue={onContinue}
        streaming={streaming}
      />
      <TraceTimeline
        steps={steps}
        selectedId={selectedStepId}
        activeNode={activeNode}
        onSelect={handleSelectStep}
        expanded={timelineOpen}
        onToggle={() => onTimelineOpenChange(!timelineOpen)}
      />
    </div>
  )
}
