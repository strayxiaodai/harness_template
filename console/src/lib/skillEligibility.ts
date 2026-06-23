import type { AgentStateSnapshot } from '../types/api'

const MIN_ROUNDS_FOR_SKILL = 1

export function threadEligibleForSkill(
  state: AgentStateSnapshot,
  rounds: number,
): boolean {
  const hasLoopOutput = Boolean(state.execution || state.review)
  return rounds >= MIN_ROUNDS_FOR_SKILL && hasLoopOutput
}

export const SKILL_ELIGIBILITY_HINT =
  'Finish at least one full loop (planner → executor → reviewer → actioner → memorize) before previewing or saving a skill.'
