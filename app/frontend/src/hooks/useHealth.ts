import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHealth } from '../lib/api'

export type HealthStatus = 'checking' | 'ok' | 'degraded' | 'offline'

export function useHealth(pollMs = 15000) {
  const [status, setStatus] = useState<HealthStatus>('checking')
  const [detail, setDetail] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const refresh = useCallback(async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const body = await fetchHealth(controller.signal)
      if (controller.signal.aborted) {
        return
      }
      setStatus(body.status === 'ok' ? 'ok' : 'degraded')
      setDetail(body.detail ?? null)
    } catch (err) {
      if (controller.signal.aborted) {
        return
      }
      setStatus('offline')
      if (err instanceof DOMException && err.name === 'AbortError') {
        return
      }
      setDetail('API unreachable — start with: uvicorn app.main:app --reload')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => {
      void refresh()
    }, pollMs)
    return () => {
      window.clearInterval(id)
      abortRef.current?.abort()
    }
  }, [pollMs, refresh])

  return { status, detail, refresh }
}
