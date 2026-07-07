import { useEffect, useState } from 'react'

const NARROW_QUERY = '(max-width: 767px)'

/** True when the viewport matches the mobile/tablet stack breakpoint. */
export function useNarrowViewport(): boolean {
  const [narrow, setNarrow] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }
    return window.matchMedia(NARROW_QUERY).matches
  })

  useEffect(() => {
    const media = window.matchMedia(NARROW_QUERY)
    const onChange = () => {
      setNarrow(media.matches)
    }
    onChange()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  return narrow
}
