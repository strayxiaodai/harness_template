import { formatApiError } from './errors'
import type {
  AgentStateSnapshot,
  DistillSkillRequest,
  DistillSkillResponse,
  GraphNode,
  ResumeRequest,
  RunRequest,
  RunResponse,
  SaveSkillRequest,
  SkillDetail,
  SkillSummary,
  StreamPayload,
  TimelineStep,
} from '../types/api'
import { GRAPH_NODES, isErrorPayload, isFinalPayload } from '../types/api'

const API_BASE = '/api'

export async function fetchHealth(
  signal?: AbortSignal,
): Promise<{ status: string; detail?: string }> {
  const res = await fetch(`${API_BASE}/health`, { signal })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(formatApiError(res.status, body, 'Health check failed'))
  }
  return res.json()
}

export async function postRun(body: RunRequest): Promise<RunResponse> {
  const res = await fetch(`${API_BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(formatApiError(res.status, body, 'Run failed'))
  }
  return res.json()
}

export async function postResume(body: ResumeRequest): Promise<RunResponse> {
  const res = await fetch(`${API_BASE}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const bodyText = await res.text()
    throw new Error(formatApiError(res.status, bodyText, 'Resume failed'))
  }
  return res.json()
}

export async function fetchSkills(signal?: AbortSignal): Promise<SkillSummary[]> {
  const res = await fetch(`${API_BASE}/skills`, { signal })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(formatApiError(res.status, body, 'List skills failed'))
  }
  return res.json()
}

export async function fetchSkill(
  slug: string,
  signal?: AbortSignal,
): Promise<SkillDetail> {
  const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(slug)}`, {
    signal,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(formatApiError(res.status, body, 'Load skill failed'))
  }
  return res.json()
}

export async function postDistillSkill(
  body: DistillSkillRequest,
): Promise<DistillSkillResponse> {
  const res = await fetch(`${API_BASE}/skills/distill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const bodyText = await res.text()
    throw new Error(formatApiError(res.status, bodyText, 'Distill skill failed'))
  }
  return res.json()
}

export async function postSaveSkill(
  body: SaveSkillRequest,
): Promise<DistillSkillResponse> {
  const res = await fetch(`${API_BASE}/skills/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const bodyText = await res.text()
    throw new Error(formatApiError(res.status, bodyText, 'Save skill failed'))
  }
  return res.json()
}

export async function streamRun(
  body: RunRequest,
  onPayload: (payload: StreamPayload) => void,
  signal?: AbortSignal,
): Promise<RunResponse | null> {
  const res = await fetch(`${API_BASE}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(formatApiError(res.status, body, 'Stream failed'))
  }

  if (!res.body) {
    throw new Error('Stream response has no body')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let final: RunResponse | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n')
    buffer = parts.pop() ?? ''

    for (const line of parts) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) {
        continue
      }
      const jsonText = trimmed.slice(5).trim()
      if (!jsonText) {
        continue
      }
      let payload: StreamPayload
      try {
        payload = JSON.parse(jsonText) as StreamPayload
      } catch {
        throw new Error('Malformed stream event from API')
      }
      onPayload(payload)
      if (isFinalPayload(payload)) {
        final = payload.final
      }
      if (isErrorPayload(payload)) {
        throw new Error(payload.error)
      }
    }
  }

  return final
}

let stepCounter = 0

export function nextStepId(): string {
  stepCounter += 1
  return `step-${stepCounter}-${Date.now()}`
}

export function mergeNodeUpdate(
  node: string,
  patch: AgentStateSnapshot,
  accumulated: AgentStateSnapshot,
): AgentStateSnapshot {
  return {
    ...accumulated,
    ...patch,
    role: node,
  }
}

export function nodePatchFromUpdate(
  node: string,
  patch: AgentStateSnapshot,
): AgentStateSnapshot {
  return { ...patch, role: node }
}

export function payloadToTimelineStep(
  node: string,
  patch: AgentStateSnapshot,
  source: TimelineStep['source'],
): TimelineStep {
  return {
    id: nextStepId(),
    node,
    timestamp: Date.now(),
    state: nodePatchFromUpdate(node, patch),
    source,
  }
}

export function patchFromRunResponse(
  node: string,
  response: RunResponse,
): AgentStateSnapshot {
  return {
    role: response.last_role ?? node,
    rounds: response.rounds,
    max_rounds: response.max_rounds,
    approved: response.approved,
    result: response.result ?? undefined,
    refine_from: response.refine_from ?? undefined,
    loop_score: response.loop_score ?? undefined,
    skill_preview_ready: response.skill_preview_ready ?? undefined,
    memory_cursor: response.memory_cursor ?? undefined,
    plan: response.plan ?? undefined,
    execution: response.execution ?? undefined,
    tool_calls: response.tool_calls ?? undefined,
    learning: response.learning ?? undefined,
    learning_candidates: response.learning_candidates ?? undefined,
  }
}

export function responseToTimelineStep(response: RunResponse): TimelineStep {
  const node = response.last_role || response.next_action || 'unknown'
  return {
    id: nextStepId(),
    node,
    timestamp: Date.now(),
    state: patchFromRunResponse(node, response),
    source: 'resume',
  }
}

export function isGraphNode(value: string): value is GraphNode {
  return (GRAPH_NODES as readonly string[]).includes(value)
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}
