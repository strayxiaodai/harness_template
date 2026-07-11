import { useCallback, useEffect, useRef } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import './ColumnSplit.css'

type SplitSide = 'inspector' | 'command'

interface ColumnSplitProps {
  side: SplitSide
  disabled?: boolean
  onResize: (widthPx: number, mainWidthPx: number) => void
  onReset: () => void
  label: string
}

/**
 * Drag handle between console columns. Double-click resets both side widths.
 */
export function ColumnSplit({
  side,
  disabled = false,
  onResize,
  onReset,
  label,
}: ColumnSplitProps) {
  const dragging = useRef(false)

  const readCurrentWidth = useCallback((): number => {
    const main = document.getElementById('main-content')
    if (!main) {
      return side === 'inspector' ? 280 : 268
    }
    const prop = side === 'inspector' ? '--col-inspector' : '--col-command'
    return (
      Number.parseFloat(getComputedStyle(main).getPropertyValue(prop)) ||
      (side === 'inspector' ? 280 : 268)
    )
  }, [side])

  const widthFromPointer = useCallback(
    (clientX: number, mainEl: HTMLElement, main: DOMRect): number => {
      const styles = getComputedStyle(mainEl)
      const padLeft = Number.parseFloat(styles.paddingLeft) || 0
      const padRight = Number.parseFloat(styles.paddingRight) || 0
      if (side === 'inspector') {
        return clientX - main.left - padLeft
      }
      return main.right - clientX - padRight
    },
    [side],
  )

  useEffect(() => {
    if (disabled) {
      return
    }

    const onMove = (event: globalThis.PointerEvent) => {
      if (!dragging.current) {
        return
      }
      const mainEl = document.getElementById('main-content')
      const main = mainEl?.getBoundingClientRect()
      if (!mainEl || !main) {
        return
      }
      event.preventDefault()
      const contentWidth = main.width -
        (Number.parseFloat(getComputedStyle(mainEl).paddingLeft) || 0) -
        (Number.parseFloat(getComputedStyle(mainEl).paddingRight) || 0)
      onResize(widthFromPointer(event.clientX, mainEl, main), contentWidth)
    }

    const onUp = () => {
      if (!dragging.current) {
        return
      }
      dragging.current = false
      document.body.classList.remove('is-column-resizing')
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [disabled, onResize, widthFromPointer])

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (disabled || event.button !== 0) {
      return
    }
    dragging.current = true
    document.body.classList.add('is-column-resizing')
    event.currentTarget.setPointerCapture(event.pointerId)
    const mainEl = document.getElementById('main-content')
    const main = mainEl?.getBoundingClientRect()
    if (mainEl && main) {
      const contentWidth = main.width -
        (Number.parseFloat(getComputedStyle(mainEl).paddingLeft) || 0) -
        (Number.parseFloat(getComputedStyle(mainEl).paddingRight) || 0)
      onResize(widthFromPointer(event.clientX, mainEl, main), contentWidth)
    }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (disabled) {
      return
    }
    const mainEl = document.getElementById('main-content')
    const main = mainEl?.getBoundingClientRect()
    if (!mainEl || !main) {
      return
    }
    const contentWidth = main.width -
      (Number.parseFloat(getComputedStyle(mainEl).paddingLeft) || 0) -
      (Number.parseFloat(getComputedStyle(mainEl).paddingRight) || 0)
    const step = event.shiftKey ? 24 : 12
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      const current = readCurrentWidth()
      const delta =
        side === 'inspector'
          ? event.key === 'ArrowRight'
            ? step
            : -step
          : event.key === 'ArrowLeft'
            ? step
            : -step
      onResize(current + delta, contentWidth)
    }
    if (event.key === 'Home') {
      event.preventDefault()
      onReset()
    }
  }

  if (disabled) {
    return null
  }

  return (
    <div
      className={`col-split col-split--${side}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onDoubleClick={onReset}
      onKeyDown={onKeyDown}
    />
  )
}
