import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, quizApi } from './quizApi'

afterEach(() => vi.unstubAllGlobals())

describe('quiz API client', () => {
  it('creates a session and parses the response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ session_id: 'session-1', total_questions: 10 }),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)

    await expect(quizApi.createSession('easy', 'horror')).resolves.toEqual({ session_id: 'session-1', total_questions: 10 })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/quiz/sessions',
      expect.objectContaining({ method: 'POST' }),
    )
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(init.body))).toEqual({ difficulty: 'easy', genre: 'horror' })
  })

  it('submits only the question id and selected answer', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ question_id: 'q1', is_correct: true, correct_answer: 'Movie', movie_year: 1999, score: 1, completed: false }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)

    await quizApi.submitAnswer('session-1', 'q1', 'Movie')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(init.body))).toEqual({ question_id: 'q1', answer: 'Movie' })
  })

  it('requests a hint with only the current question id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ question_id: 'q1', hint: 'Consider the tone.', fallback_used: false }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)

    await quizApi.getHint('session-1', 'q1')
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/quiz/sessions/session-1/hint')
    expect(JSON.parse(String(init.body))).toEqual({ question_id: 'q1' })
  })

  it('surfaces API details and network failures as typed errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Quiz session not found' }),
      { status: 404, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(quizApi.getQuestion('missing')).rejects.toEqual(new ApiError('Quiz session not found', 404))

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(quizApi.createSession('easy')).rejects.toMatchObject({ status: 0 })
  })
})

