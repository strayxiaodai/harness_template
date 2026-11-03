import { useCallback, useEffect, useState } from 'react'
import { fetchSettings } from '../lib/api'
import type { SystemSettingsResponse, UserSettings } from '../types/api'

const STORAGE_KEY = 'harness.console.settings'

const DEFAULT_USER_SETTINGS: UserSettings = {
  taskRewriteEnabled: false,
  humanInTheLoop: true,
  maxRounds: 3,
  timeoutSeconds: 120,
  autoExpandTimeline: false,
}

function loadStoredSettings(): Partial<UserSettings> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return JSON.parse(raw) as Partial<UserSettings>
    }
  } catch {
    // ignore parse error
  }
  return {}
}

function persistSettings(settings: UserSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // ignore storage quota error
  }
}

export function useSettings() {
  const [systemSettings, setSystemSettings] = useState<SystemSettingsResponse | null>(null)
  const [userSettings, setUserSettings] = useState<UserSettings>(() => ({
    ...DEFAULT_USER_SETTINGS,
    ...loadStoredSettings(),
  }))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchSettings()
      setSystemSettings(data)
      setUserSettings((prev) => {
        const stored = loadStoredSettings()
        // If taskRewriteEnabled was not explicitly set in storage, sync with system default
        const taskRewriteEnabled =
          stored.taskRewriteEnabled !== undefined
            ? stored.taskRewriteEnabled
            : data.task_rewrite_enabled

        return {
          ...prev,
          taskRewriteEnabled,
        }
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refreshSettings()
    return () => controller.abort()
  }, [refreshSettings])

  const updateUserSettings = useCallback(
    (patch: Partial<UserSettings>) => {
      setUserSettings((prev) => {
        const next = { ...prev, ...patch }
        persistSettings(next)
        return next
      })
    },
    [],
  )

  return {
    systemSettings,
    userSettings,
    loading,
    error,
    updateUserSettings,
    refreshSettings,
  }
}

