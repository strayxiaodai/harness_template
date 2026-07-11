export const GRAPH_NODES = [
  'planner',
  'executor',
  'reviewer',
  'actioner',
  'memorize',
] as const

export type GraphNode = (typeof GRAPH_NODES)[number]

export interface ExecutionRecord {
  summary: string
  changes: string[]
  risks: string[]
  verification: string[]
}

export interface ReviewRecord {
  verdict: string
  reason: string
  suggested_step: string
}

export interface ToolCallRecord {
  iteration: number
  tool: string
  args: Record<string, unknown>
  status: string
}

export interface AgentStateSnapshot {
  thread_id?: string
  task?: string
  plan?: string[]
  rounds?: number
  max_rounds?: number
  role?: string
  result?: string
  execution?: ExecutionRecord
  approved?: boolean
  review?: ReviewRecord
  refine_from?: string
  tool_calls?: ToolCallRecord[]
  human_in_the_loop?: boolean
  memory_context?: string
  memory_context_round?: number
  memory_cursor?: number
  skill_slug?: string
  skill_context?: string
  loop_score?: number
  skill_preview_ready?: boolean
}

export interface RunRequest {
  task: string
  thread_id: string
  plan?: string[]
  max_rounds?: number
  timeout_seconds?: number
  human_in_the_loop?: boolean
  skill_slug?: string
}

export interface ReviewOverride {
  verdict: 'pass' | 'fail'
  reason: string
  suggested_step: 'planner' | 'executor' | 'finish'
}

export interface ClarificationQuestion {
  id: string
  prompt: string
  why?: string
}

export interface ClarificationAnswer {
  question_id: string
  answer: string
}

export type MemoryType = 'fact' | 'preference' | 'entity' | 'summary'

export interface PendingMemory {
  id: string
  content: string
  memory_type: MemoryType
  importance: number
}

export interface MemoryResumeRow {
  id: string
  keep: boolean
  content?: string
  memory_type?: MemoryType
  importance?: number
}

export interface InterruptPayload {
  id?: string | null
  value?: {
    kind?: string
    node?: string
    reason?: string
    message?: string
    score?: number
    threshold?: number
    questions?: ClarificationQuestion[]
    [key: string]: unknown
  } | unknown
}

export interface ResumeOverrides {
  plan?: string[]
  task?: string
  result?: string
  review?: ReviewOverride
  refine_from?: 'planner' | 'executor' | 'finish'
}

export interface ResumeRequest {
  thread_id: string
  timeout_seconds?: number
  overrides?: ResumeOverrides
  answers?: ClarificationAnswer[]
  interrupt_resume?: unknown
}

export interface RunResponse {
  thread_id: string
  status: 'complete' | 'awaiting_human'
  approved: boolean
  needs_human: boolean
  result: string | null
  next_action: string | null
  last_role: string | null
  rounds: number
  max_rounds: number
  skill_eligible: boolean
  skill_ineligible_reason: string | null
  interrupt?: InterruptPayload | null
}

export interface DistillSkillRequest {
  thread_id: string
  name?: string
  refine?: boolean
  save?: boolean
}

export interface SaveSkillRequest {
  thread_id: string
  slug: string
  name: string
  description: string
  body: string
}

export interface DistillSkillResponse {
  thread_id: string
  slug: string
  path: string | null
  saved: boolean
  created: boolean
  refined: boolean
  description: string
  name: string
  body: string
  status: 'complete' | 'in_progress'
}

export interface SkillSummary {
  slug: string
  name: string
  description: string
  path: string
  thread_count: number
  updated_at: string | null
}

export interface SkillDetail extends SkillSummary {
  body: string
}

export interface TimelineStep {
  id: string
  node: GraphNode | string
  timestamp: number
  state: AgentStateSnapshot
  source: 'stream' | 'resume'
}

export interface StreamFinalPayload {
  final: RunResponse
}

export interface StreamErrorPayload {
  error: string
}

export type StreamNodePayload = Partial<Record<GraphNode, AgentStateSnapshot>>

export type StreamPayload =
  | StreamNodePayload
  | StreamFinalPayload
  | StreamErrorPayload

export function isFinalPayload(
  payload: StreamPayload,
): payload is StreamFinalPayload {
  return 'final' in payload
}

export function isErrorPayload(
  payload: StreamPayload,
): payload is StreamErrorPayload {
  return 'error' in payload
}

export function isNodePayload(
  payload: StreamPayload,
): payload is StreamNodePayload {
  return !isFinalPayload(payload) && !isErrorPayload(payload)
}
