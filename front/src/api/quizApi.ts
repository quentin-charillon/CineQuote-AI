import type { AnswerResult, CoachResponse, CustomSessionCreated, Difficulty, DifficultyAvailability, ExplanationResponse, Genre, HintResponse, PublicQuestion, QuizAvailability, QuizResults, RecommendationsResponse, SessionCreated, User, UserStats } from './types'

const API_URL = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('Could not reach the quiz server. Check that the backend is running.', 0)
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(body?.detail ?? 'The quiz server returned an unexpected error.', response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const quizApi = {
  getDifficulties: () => request<DifficultyAvailability[]>('/quiz/sessions/difficulties'),
  getAvailability: () => request<QuizAvailability[]>('/quiz/sessions/availability'),
  createSession: (difficulty: Difficulty, genre: Genre = 'all') => request<SessionCreated>('/quiz/sessions', {
    method: 'POST',
    body: JSON.stringify({ difficulty, genre }),
  }),
  createCustomSession: (prompt: string) => request<CustomSessionCreated>('/quiz/sessions/custom', { method: 'POST', body: JSON.stringify({ prompt }) }),
  getQuestion: (sessionId: string) => request<PublicQuestion>(`/quiz/sessions/${encodeURIComponent(sessionId)}/question`),
  getHint: (sessionId: string, questionId: string) =>
    request<HintResponse>(`/quiz/sessions/${encodeURIComponent(sessionId)}/hint`, {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId }),
    }),
  getExplanation: (sessionId: string, questionId: string) => request<ExplanationResponse>(`/quiz/sessions/${encodeURIComponent(sessionId)}/explanation`, {
    method: 'POST', body: JSON.stringify({ question_id: questionId }),
  }),
  submitAnswer: (sessionId: string, questionId: string, answer: string) =>
    request<AnswerResult>(`/quiz/sessions/${encodeURIComponent(sessionId)}/answers`, {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, answer }),
    }),
  getResults: (sessionId: string) => request<QuizResults>(`/quiz/sessions/${encodeURIComponent(sessionId)}/results`),
}

export const accountApi = {
  me: () => request<User>('/auth/me'),
  register: (email: string, username: string, password: string) => request<User>('/auth/register', { method: 'POST', body: JSON.stringify({ email, username, password }) }),
  login: (email: string, password: string) => request<User>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  stats: () => request<UserStats>('/stats/me'),
  coach: () => request<CoachResponse>('/ai/coach', { method: 'POST' }),
  recommendations: () => request<RecommendationsResponse>('/ai/recommendations', { method: 'POST' }),
}

