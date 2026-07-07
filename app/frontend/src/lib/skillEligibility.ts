import type { AgentStateSnapshot, RunResponse, TimelineStep } from '../types/api'

const MIN_ROUNDS_FOR_SKILL = 1

export function threadEligibleForSkill(
  state: AgentStateSnapshot,
  rounds: number,
  timeline: TimelineStep[] = [],
): boolean {
  const fromState = Boolean(state.execution || state.review)
  const fromTimeline = timeline.some(
    (step) => Boolean(step.state.execution || step.state.review),
  )
  const hasLoopOutput = fromState || fromTimeline
  const previewReady = Boolean(
    state.skill_preview_ready ||
      timeline.some((step) => step.state.skill_preview_ready),
  )
  return (
    rounds >= MIN_ROUNDS_FOR_SKILL && hasLoopOutput && previewReady
  )
}

export function resolveSkillEligible(
  runResponse: RunResponse | null,
  state: AgentStateSnapshot,
  rounds: number,
  timeline: TimelineStep[] = [],
): boolean {
  if (runResponse) {
    return runResponse.skill_eligible
  }
  return threadEligibleForSkill(state, rounds, timeline)
}

export function resolveSkillIneligibleReason(
  runResponse: RunResponse | null,
): string {
  if (runResponse?.skill_ineligible_reason) {
    return runResponse.skill_ineligible_reason
  }
  return SKILL_ELIGIBILITY_HINT
}

export const SKILL_ELIGIBILITY_HINT =
  'Finish at least one full loop with a quality score of 80+ at the actioner before previewing or saving a skill.'
