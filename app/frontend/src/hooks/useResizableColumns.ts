import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'harness.console.columnWidths'
const DESKTOP_QUERY = '(min-width: 1024px)'

export const DEFAULT_INSPECTOR_WIDTH = 280
export const DEFAULT_COMMAND_WIDTH = 268

const INSPECTOR_MIN = 180
const INSPECTOR_MAX = 480
const COMMAND_MIN = 200
const COMMAND_MAX = 420
const CENTER_MIN = 280

export type ColumnWidths = {
  inspector: number
  command: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function readStoredWidths(): ColumnWidths {
  if (typeof window === 'undefined') {
    return {
      inspector: DEFAULT_INSPECTOR_WIDTH,
      command: DEFAULT_COMMAND_WIDTH,
    }
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return {
        inspector: DEFAULT_INSPECTOR_WIDTH,
        command: DEFAULT_COMMAND_WIDTH,
      }
    }
    const parsed = JSON.parse(raw) as Partial<ColumnWidths>
    return {
      inspector: clamp(
        Number(parsed.inspector) || DEFAULT_INSPECTOR_WIDTH,
        INSPECTOR_MIN,
        INSPECTOR_MAX,
      ),
      command: clamp(
        Number(parsed.command) || DEFAULT_COMMAND_WIDTH,
        COMMAND_MIN,
        COMMAND_MAX,
      ),
    }
  } catch {
    return {
      inspector: DEFAULT_INSPECTOR_WIDTH,
      command: DEFAULT_COMMAND_WIDTH,
    }
  }
}

function persistWidths(widths: ColumnWidths): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(widths))
  } catch {
    // Ignore quota / private-mode failures.
  }
}

/**
 * Desktop column widths for inspector / command, with drag + keyboard resize.
 * Disabled below the three-column breakpoint (1024px).
 */
export function useResizableColumns(): {
  widths: ColumnWidths
  desktop: boolean
  setInspectorWidth: (width: number, mainWidth: number) => void
  setCommandWidth: (width: number, mainWidth: number) => void
  resetWidths: () => void
} {
  const [widths, setWidths] = useState<ColumnWidths>(readStoredWidths)
  const [desktop, setDesktop] = useState(() => {
    if (typeof window === 'undefined') {
      return true
    }
    return window.matchMedia(DESKTOP_QUERY).matches
  })

  useEffect(() => {
    const media = window.matchMedia(DESKTOP_QUERY)
    const onChange = () => {
      setDesktop(media.matches)
    }
    onChange()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    persistWidths(widths)
  }, [widths])

  const fitAgainstCenter = useCallback(
    (next: ColumnWidths, mainWidth: number): ColumnWidths => {
      const splitters = 12
      const available = mainWidth - splitters
      let inspector = clamp(next.inspector, INSPECTOR_MIN, INSPECTOR_MAX)
      let command = clamp(next.command, COMMAND_MIN, COMMAND_MAX)
      if (inspector + command + CENTER_MIN > available) {
        const overflow = inspector + command + CENTER_MIN - available
        // Shrink the side that grew last by preferring proportional trim.
        const totalSides = inspector + command
        inspector = clamp(
          inspector - (overflow * inspector) / totalSides,
          INSPECTOR_MIN,
          INSPECTOR_MAX,
        )
        command = clamp(
          available - CENTER_MIN - inspector,
          COMMAND_MIN,
          COMMAND_MAX,
        )
      }
      return { inspector: Math.round(inspector), command: Math.round(command) }
    },
    [],
  )

  const setInspectorWidth = useCallback(
    (width: number, mainWidth: number) => {
      setWidths((prev) =>
        fitAgainstCenter({ ...prev, inspector: width }, mainWidth),
      )
    },
    [fitAgainstCenter],
  )

  const setCommandWidth = useCallback(
    (width: number, mainWidth: number) => {
      setWidths((prev) =>
        fitAgainstCenter({ ...prev, command: width }, mainWidth),
      )
    },
    [fitAgainstCenter],
  )

  const resetWidths = useCallback(() => {
    setWidths({
      inspector: DEFAULT_INSPECTOR_WIDTH,
      command: DEFAULT_COMMAND_WIDTH,
    })
  }, [])

  return {
    widths,
    desktop,
    setInspectorWidth,
    setCommandWidth,
    resetWidths,
  }
}
