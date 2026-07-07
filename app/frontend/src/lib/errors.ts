/** Parse FastAPI / fetch failures into user-facing messages. */

export function formatApiError(
  status: number,
  body: string,
  fallback: string,
): string {
  if (!body) {
    return `${fallback} (HTTP ${status})`
  }
  try {
    const parsed = JSON.parse(body) as { detail?: unknown }
    const detail = parsed.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') {
            return item
          }
          if (
            item &&
            typeof item === 'object' &&
            'msg' in item &&
            typeof (item as { msg: unknown }).msg === 'string'
          ) {
            return (item as { msg: string }).msg
          }
          return JSON.stringify(item)
        })
        .join('; ')
    }
  } catch {
    // body is plain text
  }
  return body.length > 280 ? `${body.slice(0, 280)}…` : body
}

export function formatFetchError(err: unknown, fallback: string): string {
  if (err instanceof DOMException && err.name === 'AbortError') {
    return 'Request cancelled.'
  }
  if (err instanceof TypeError) {
    return 'Network error — is the API running on port 8000?'
  }
  if (err instanceof Error) {
    return err.message || fallback
  }
  return fallback
}

export function clampRounds(value: number): number {
  if (Number.isNaN(value) || value < 1) {
    return 1
  }
  if (value > 20) {
    return 20
  }
  return Math.floor(value)
}
