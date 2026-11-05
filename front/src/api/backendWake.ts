const TEMPORARY_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504])

export type WakeProgress = {
  attempt: number
  elapsedMs: number
  nextDelayMs: number
}

export type WakeFailureKind = 'timeout' | 'permanent' | 'cancelled'

export class BackendWakeError extends Error {
  constructor(message: string, readonly kind: WakeFailureKind, readonly status = 0) {
    super(message)
    this.name = 'BackendWakeError'
  }
}

type WakeOptions = {
  signal: AbortSignal
  onProgress?: (progress: WakeProgress) => void
  fetcher?: typeof fetch
  totalTimeoutMs?: number
  requestTimeoutMs?: number
  delaysMs?: readonly number[]
  now?: () => number
}

const abortableDelay = (delayMs: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = globalThis.setTimeout(done, delayMs)
  signal.addEventListener('abort', cancel, { once: true })

  function done() {
    signal.removeEventListener('abort', cancel)
    resolve()
  }
  function cancel() {
    globalThis.clearTimeout(timer)
    reject(new BackendWakeError('Backend check cancelled.', 'cancelled'))
  }
})

export async function waitForBackend({
  signal,
  onProgress,
  fetcher = fetch,
  totalTimeoutMs = 105_000,
  requestTimeoutMs = 15_000,
  delaysMs = [1_500, 2_500, 4_000, 6_000, 8_000, 10_000],
  now = Date.now,
}: WakeOptions): Promise<void> {
  const startedAt = now()
  let attempt = 0

  while (!signal.aborted && now() - startedAt < totalTimeoutMs) {
    attempt += 1
    const requestController = new AbortController()
    const cancelRequest = () => requestController.abort()
    signal.addEventListener('abort', cancelRequest, { once: true })
    const requestTimer = globalThis.setTimeout(() => requestController.abort(), requestTimeoutMs)

    try {
      const response = await fetcher('/api/health/ready', {
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: requestController.signal,
      })
      if (response.ok) return
      if (!TEMPORARY_STATUSES.has(response.status)) {
        throw new BackendWakeError(
          response.status === 403
            ? 'The cinema server refused the secure connection.'
            : `The cinema server returned an unexpected response (${response.status}).`,
          'permanent',
          response.status,
        )
      }
    } catch (error) {
      if (error instanceof BackendWakeError) throw error
      if (signal.aborted) throw new BackendWakeError('Backend check cancelled.', 'cancelled')
      // Network failures and per-request timeouts are temporary during a cold start.
    } finally {
      globalThis.clearTimeout(requestTimer)
      signal.removeEventListener('abort', cancelRequest)
    }

    const elapsedMs = now() - startedAt
    const remainingMs = totalTimeoutMs - elapsedMs
    if (remainingMs <= 0) break
    const nextDelayMs = Math.min(delaysMs[Math.min(attempt - 1, delaysMs.length - 1)], remainingMs)
    onProgress?.({ attempt, elapsedMs, nextDelayMs })
    await abortableDelay(nextDelayMs, signal)
  }

  if (signal.aborted) throw new BackendWakeError('Backend check cancelled.', 'cancelled')
  throw new BackendWakeError('The cinema server is taking longer than expected to wake up.', 'timeout')
}
