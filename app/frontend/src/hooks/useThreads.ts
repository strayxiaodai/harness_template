import { useCallback, useEffect, useState } from 'react'
import { fetchThreads } from '../lib/api'
import { formatFetchError } from '../lib/errors'
import type { ThreadSummary } from '../types/api'

export function useThreads() {
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshThreads = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const items = await fetchThreads()
      setThreads(items)
    } catch (err) {
      setError(formatFetchError(err, 'Failed to load threads'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshThreads()
  }, [refreshThreads])

  return {
    threads,
    loading,
    error,
    refreshThreads,
    clearError: () => setError(null),
  }
}
