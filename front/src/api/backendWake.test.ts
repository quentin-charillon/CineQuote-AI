import { afterEach, describe, expect, it, vi } from 'vitest'

import { BackendWakeError, WAKE_TOTAL_TIMEOUT_MS, waitForBackend } from './backendWake'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const options = (fetcher: typeof fetch, signal = new AbortController().signal) => ({
  fetcher,
  signal,
  requestTimeoutMs: 100,
  totalTimeoutMs: 1_000,
  delaysMs: [10, 20, 30],
})

describe('backend wake-up', () => {
  it('continues immediately when the backend is ready', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{"status":"ready"}', { status: 200 }))
    await expect(waitForBackend(options(fetcher))).resolves.toBeUndefined()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0][1]).toMatchObject({ method: 'GET', cache: 'no-store' })
  })

  it('retries temporary sleeping and gateway responses sequentially until recovery', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(null, { status: 502 }))
      .mockResolvedValueOnce(new Response(null, { status: 504 }))
      .mockResolvedValueOnce(new Response('{}', { status: 200 }))
    let active = 0
    let maxActive = 0
    const sequentialFetcher = vi.fn(async (...args: Parameters<typeof fetch>) => {
      active += 1
      maxActive = Math.max(maxActive, active)
      const response = await fetcher(...args)
      active -= 1
      return response
    }) as typeof fetch

    const waiting = waitForBackend(options(sequentialFetcher))
    await vi.runAllTimersAsync()
    await expect(waiting).resolves.toBeUndefined()
    expect(fetcher).toHaveBeenCalledTimes(4)
    expect(maxActive).toBe(1)
  })

  it('supports a slow cold start that recovers after more than two minutes', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(0)
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(null, { status: 502 }))
      .mockResolvedValueOnce(new Response(null, { status: 504 }))
    for (let index = 0; index < 22; index += 1) {
      fetcher.mockResolvedValueOnce(new Response(null, { status: 503 }))
    }
    fetcher.mockResolvedValueOnce(new Response('{}', { status: 200 }))

    const waiting = waitForBackend({ signal: new AbortController().signal, fetcher })
    await vi.runAllTimersAsync()

    await expect(waiting).resolves.toBeUndefined()
    expect(fetcher).toHaveBeenCalledTimes(26)
    expect(Date.now()).toBe(125_000)
  })

  it('uses the full 180-second window before reporting a timeout', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(0)
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 503 })) as typeof fetch
    const waiting = waitForBackend({ signal: new AbortController().signal, fetcher })
    let settled = false
    void waiting.then(() => { settled = true }, () => { settled = true })
    const rejection = expect(waiting).rejects.toMatchObject({ kind: 'timeout' })

    await vi.advanceTimersByTimeAsync(WAKE_TOTAL_TIMEOUT_MS - 1)
    expect(settled).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    await rejection
    expect(settled).toBe(true)
  })

  it('stops after the global timeout', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 503 })) as typeof fetch
    const waiting = waitForBackend({
      ...options(fetcher),
      totalTimeoutMs: 50,
      delaysMs: [20],
    })
    const rejection = expect(waiting).rejects.toMatchObject({ kind: 'timeout' })
    await vi.runAllTimersAsync()
    await rejection
    expect(fetcher).toHaveBeenCalled()
  })

  it('does not retry a definitive security error', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 403 })) as typeof fetch
    await expect(waitForBackend(options(fetcher))).rejects.toEqual(expect.objectContaining<Partial<BackendWakeError>>({
      kind: 'permanent',
      status: 403,
    }))
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('never repeats a POST operation while waking the backend', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    await waitForBackend(options(fetcher))
    expect(fetcher.mock.calls.every((call) => (call[1] as RequestInit | undefined)?.method === 'GET')).toBe(true)
  })

  it('cancels pending delays and leaves no timers behind on cleanup', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 503 })) as typeof fetch
    const waiting = waitForBackend(options(fetcher, controller.signal))
    await vi.advanceTimersByTimeAsync(0)
    controller.abort()
    await expect(waiting).rejects.toMatchObject({ kind: 'cancelled' })
    expect(vi.getTimerCount()).toBe(0)
  })
})
