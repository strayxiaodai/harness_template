import { useCallback, useEffect, useRef, useState } from 'react'
import {
  mergeNodeUpdate,
  payloadToTimelineStep,
  postDistillSkill,
  postResume,
  postSaveSkill,
  responseToTimelineStep,
  streamRun,
} from '../lib/api'
import { clampRounds, formatFetchError } from '../lib/errors'
import {
  resolveSkillEligible,
  resolveSkillIneligibleReason,
} from '../lib/skillEligibility'
import type {
  AgentStateSnapshot,
  ClarificationAnswer,
  DistillSkillResponse,
  ResumeOverrides,
  RunResponse,
  TimelineStep,
} from '../types/api'
import { isNodePayload } from '../types/api'

export type RunPhase = 'idle' | 'streaming' | 'awaiting_human' | 'complete' | 'error'

function newThreadId(): string {
  return crypto.randomUUID()
}

function parsePlan(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function useConsole() {
  const [threadId, setThreadId] = useState(newThreadId)
  const [task, setTask] = useState('')
  const [planText, setPlanText] = useState('')
  const [maxRounds, setMaxRoundsState] = useState(3)
  const [humanInTheLoop, setHumanInTheLoop] = useState(true)
  const [phase, setPhase] = useState<RunPhase>('idle')
  const [activeNode, setActiveNode] = useState<string | null>(null)
  const [accumulated, setAccumulated] = useState<AgentStateSnapshot>({})
  const [timeline, setTimeline] = useState<TimelineStep[]>([])
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [runResponse, setRunResponse] = useState<RunResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refineFrom, setRefineFrom] = useState<string | null>(null)
  const [skillName, setSkillName] = useState('')
  const [distillResult, setDistillResult] = useState<DistillSkillResponse | null>(
    null,
  )
  const [distillBusy, setDistillBusy] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const busyRef = useRef(false)

  const selectedStep =
    timeline.find((step) => step.id === selectedStepId) ?? null

  const setMaxRounds = useCallback((value: number) => {
    setMaxRoundsState(clampRounds(value))
  }, [])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const resetThread = useCallback(() => {
    abortRef.current?.abort()
    busyRef.current = false
    setThreadId(newThreadId())
    setPhase('idle')
    setActiveNode(null)
    setAccumulated({})
    setTimeline([])
    setSelectedStepId(null)
    setRunResponse(null)
    setError(null)
    setRefineFrom(null)
    setSkillName('')
    setDistillResult(null)
    setDistillBusy(false)
  }, [])

  const clearError = useCallback(() => {
    setError(null)
    if (phase === 'error') {
      setPhase(runResponse?.needs_human ? 'awaiting_human' : 'idle')
    }
  }, [phase, runResponse?.needs_human])

  const startStream = useCallback(
    async (params: {
      nextThreadId: string
      runTask: string
      skillSlug?: string
    }) => {
      if (busyRef.current) {
        return
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      busyRef.current = true

      setError(null)
      setPhase('streaming')
      setActiveNode(null)
      setAccumulated({
        task: params.runTask,
        plan: parsePlan(planText),
        skill_slug: params.skillSlug,
      })
      setTimeline([])
      setSelectedStepId(null)
      setRunResponse(null)
      setRefineFrom(null)

      let localAccumulated: AgentStateSnapshot = {
        task: params.runTask,
        plan: parsePlan(planText),
        skill_slug: params.skillSlug,
      }

      try {
        const final = await streamRun(
          {
            thread_id: params.nextThreadId,
            task: params.runTask,
            plan: parsePlan(planText),
            max_rounds: maxRounds,
            human_in_the_loop: humanInTheLoop,
            skill_slug: params.skillSlug,
          },
          (payload) => {
            if (!isNodePayload(payload)) {
              return
            }
            for (const [node, patch] of Object.entries(payload)) {
              if (!patch) {
                continue
              }
              setActiveNode(node)
              localAccumulated = mergeNodeUpdate(node, patch, localAccumulated)
              const step = payloadToTimelineStep(node, localAccumulated, 'stream')
              setAccumulated({ ...localAccumulated })
              setTimeline((prev) => [...prev, step])
              setSelectedStepId(step.id)
              if (patch.refine_from) {
                setRefineFrom(patch.refine_from)
              }
            }
          },
          controller.signal,
        )

        if (controller.signal.aborted) {
          return
        }

        if (final) {
          setRunResponse(final)
          if (final.needs_human) {
            setPhase('awaiting_human')
            setActiveNode(final.next_action)
          } else {
            setPhase('complete')
            setActiveNode(null)
          }
        } else {
          setPhase('idle')
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return
        }
        setPhase('error')
        setError(formatFetchError(err, 'Stream failed'))
        setActiveNode(null)
      } finally {
        busyRef.current = false
      }
    },
    [humanInTheLoop, maxRounds, planText],
  )

  const run = useCallback(async () => {
    if (!task.trim()) {
      setError('Enter a task before running.')
      return
    }
    await startStream({
      nextThreadId: threadId,
      runTask: task.trim(),
    })
  }, [startStream, task, threadId])

  const runSkill = useCallback(
    async (skillSlug: string) => {
      if (!skillSlug) {
        setError('Select a saved skill to run.')
        return
      }
      const nextThreadId = newThreadId()
      setThreadId(nextThreadId)
      await startStream({
        nextThreadId,
        runTask: task.trim(),
        skillSlug,
      })
    },
    [startStream, task],
  )

  const resume = useCallback(
    async (overrides?: ResumeOverrides, answers?: ClarificationAnswer[]) => {
      if (busyRef.current) {
        return
      }
      if (phase !== 'awaiting_human' && phase !== 'error') {
        return
      }

      busyRef.current = true
      setError(null)
      setPhase('streaming')
      setActiveNode(runResponse?.next_action ?? null)

      const wasAwaitingHuman = runResponse?.needs_human ?? false

      try {
        const response = await postResume({
          thread_id: threadId,
          overrides: overrides ?? undefined,
          answers: answers ?? undefined,
        })
        const step = responseToTimelineStep(response)
        setTimeline((prev) => [...prev, step])
        setSelectedStepId(step.id)
        setRunResponse(response)
        setAccumulated((prev) => ({
          ...prev,
          ...step.state,
          role: response.last_role ?? prev.role,
          result: response.result ?? prev.result,
          approved: response.approved,
          rounds: response.rounds,
        }))

        if (response.needs_human) {
          setPhase('awaiting_human')
          setActiveNode(response.next_action)
        } else {
          setPhase('complete')
          setActiveNode(null)
        }
      } catch (err) {
        setPhase(wasAwaitingHuman ? 'awaiting_human' : 'error')
        setError(formatFetchError(err, 'Resume failed'))
        setActiveNode(runResponse?.next_action ?? null)
      } finally {
        busyRef.current = false
      }
    },
    [phase, runResponse?.needs_human, runResponse?.next_action, threadId],
  )

  const distillSkill = useCallback(async () => {
    if (distillBusy || busyRef.current) {
      return
    }
    if (phase !== 'complete' && phase !== 'awaiting_human') {
      setError('Finish or pause the thread before distilling a skill.')
      return
    }

    const rounds = runResponse?.rounds ?? accumulated.rounds ?? 0
    const eligible = resolveSkillEligible(
      runResponse,
      accumulated,
      rounds,
      timeline,
    )
    if (!eligible) {
      setError(resolveSkillIneligibleReason(runResponse))
      return
    }

    setDistillBusy(true)
    setError(null)

    try {
      const response = await postDistillSkill({
        thread_id: threadId,
        name: skillName.trim() || undefined,
        refine: true,
        save: false,
      })
      setDistillResult(response)
    } catch (err) {
      setError(formatFetchError(err, 'Distill skill failed'))
    } finally {
      setDistillBusy(false)
    }
  }, [accumulated, distillBusy, phase, runResponse, skillName, threadId, timeline])

  const saveSkill = useCallback(async () => {
    if (distillBusy || !distillResult || distillResult.saved) {
      return
    }

    setDistillBusy(true)
    setError(null)

    try {
      const response = await postSaveSkill({
        thread_id: threadId,
        slug: distillResult.slug,
        name: distillResult.name,
        description: distillResult.description,
        body: distillResult.body,
      })
      setDistillResult(response)
    } catch (err) {
      setError(formatFetchError(err, 'Save skill failed'))
    } finally {
      setDistillBusy(false)
    }
  }, [distillBusy, distillResult, threadId])

  const discardSkill = useCallback(() => {
    setDistillResult(null)
  }, [])

  const selectStep = useCallback((id: string) => {
    setSelectedStepId(id)
  }, [])

  const selectAdjacent = useCallback(
    (direction: 1 | -1) => {
      if (timeline.length === 0) {
        return
      }
      const idx = timeline.findIndex((s) => s.id === selectedStepId)
      const nextIdx =
        idx < 0
          ? direction === 1
            ? 0
            : timeline.length - 1
          : Math.min(
              timeline.length - 1,
              Math.max(0, idx + direction),
            )
      setSelectedStepId(timeline[nextIdx].id)
    },
    [selectedStepId, timeline],
  )

  return {
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
  }
}
