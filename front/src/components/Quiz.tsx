import { useCallback, useEffect, useState } from 'react'

import { accountApi, ApiError, quizApi } from '../api/quizApi'
import type { AnswerResult, CoachResponse, Difficulty, ExplanationResponse, Genre, HintResponse, PublicQuestion, QuizResults } from '../api/types'
import { FilmMark } from './FilmMark'
import './Quiz.css'

interface QuizProps { difficulty: Difficulty; genre: Genre; customPrompt?: string | null; onExit: () => void; isAuthenticated: boolean }
type RetryAction = { type: 'submit'; answer: string } | { type: 'hint' } | { type: 'next' } | null

export function Quiz({ difficulty, genre, customPrompt, onExit, isAuthenticated }: QuizProps) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [question, setQuestion] = useState<PublicQuestion | null>(null)
  const [feedback, setFeedback] = useState<AnswerResult | null>(null)
  const [results, setResults] = useState<QuizResults | null>(null)
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null)
  const [hint, setHint] = useState<HintResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isHintLoading, setIsHintLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retryAction, setRetryAction] = useState<RetryAction>(null)
  const [coach, setCoach] = useState<CoachResponse | null>(null)
  const [coachLoading, setCoachLoading] = useState(false)
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null)
  const [explanationLoading, setExplanationLoading] = useState(false)

  const startSession = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    setRetryAction(null)
    setQuestion(null)
    setFeedback(null)
    setResults(null)
    setSelectedAnswer(null)
    setHint(null)
    setCoach(null)
    setExplanation(null)
    try {
      const created = customPrompt ? await quizApi.createCustomSession(customPrompt) : await quizApi.createSession(difficulty, genre)
      const firstQuestion = await quizApi.getQuestion(created.session_id)
      setSessionId(created.session_id)
      setQuestion(firstQuestion)
    } catch (caught) {
      setError(getErrorMessage(caught))
    } finally {
      setIsLoading(false)
    }
  }, [difficulty, genre, customPrompt])

  useEffect(() => { void startSession() }, [startSession])

  const submitAnswer = async (answer: string) => {
    if (!sessionId || !question || isSubmitting || isHintLoading || feedback) return
    setSelectedAnswer(answer)
    setIsSubmitting(true)
    setError(null)
    setRetryAction(null)
    try {
      setFeedback(await quizApi.submitAnswer(sessionId, question.id, answer))
    } catch (caught) {
      setError(getErrorMessage(caught))
      setRetryAction({ type: 'submit', answer })
    } finally {
      setIsSubmitting(false)
    }
  }

  const requestHint = async () => {
    if (!sessionId || !question || feedback || hint || question.hint_used || isHintLoading) return
    setIsHintLoading(true)
    setError(null)
    setRetryAction(null)
    try {
      setHint(await quizApi.getHint(sessionId, question.id))
    } catch (caught) {
      setError(getErrorMessage(caught))
      setRetryAction({ type: 'hint' })
    } finally {
      setIsHintLoading(false)
    }
  }

  const advance = async () => {
    if (!sessionId || !feedback) return
    setIsSubmitting(true)
    setError(null)
    setRetryAction(null)
    try {
      if (feedback.completed) {
        setResults(await quizApi.getResults(sessionId))
      } else {
        setQuestion(await quizApi.getQuestion(sessionId))
        setFeedback(null)
        setSelectedAnswer(null)
        setHint(null)
        setExplanation(null)
      }
    } catch (caught) {
      setError(getErrorMessage(caught))
      setRetryAction({ type: 'next' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const retry = () => {
    if (retryAction?.type === 'submit') void submitAnswer(retryAction.answer)
    if (retryAction?.type === 'hint') void requestHint()
    if (retryAction?.type === 'next') void advance()
  }

  if (isLoading || (!question && !error)) {
    return <StatusScreen title="Preparing your screening…" detail="Shuffling scenes and setting the stage." onExit={onExit} />
  }
  if (!question && error) {
    return <StatusScreen title="The projector stopped" detail={error} actionLabel="Retry" onAction={() => void startSession()} onExit={onExit} />
  }
  if (results) {
    return (
      <section className="quiz-shell results" aria-labelledby="results-title">
        <div className="quiz-shell__grain" aria-hidden="true" />
        <BrandBar onExit={onExit} label="Final cut" />
        <div className="results__content">
          <p className="quiz-kicker">That’s a wrap</p>
          <h1 id="results-title">Your final score</h1>
          <div className="score-reel" aria-label={`${results.score} out of ${results.total_questions}`}>
            <strong>{results.percentage}<span>%</span></strong>
            <p>{results.score} correct answers out of {results.total_questions}</p>
          </div>
          <p className="results__message">{getResultMessage(results.percentage)}</p>
          {isAuthenticated ? (
            <div className="coach-card result-coach">
              <div><span>Your next challenge</span><h2>Turn this score into your next screening.</h2></div>
              <button className="primary-action" disabled={coachLoading} onClick={async () => {
                setCoachLoading(true); setError(null)
                try { setCoach(await accountApi.coach()) } catch (caught) { setError(getErrorMessage(caught)) } finally { setCoachLoading(false) }
              }}>{coachLoading ? 'Building…' : coach ? 'Refresh challenge' : 'Choose my next game'}</button>
              {coach && <div className="coach-note"><p>{coach.summary}</p><small>Next: {coach.recommended_genre} · {coach.recommended_difficulty}</small></div>}
            </div>
          ) : <p className="account-note">Sign in before starting a quiz to unlock personalized coaching and saved statistics.</p>}
          {error && <InlineError message={error} canRetry={false} onRetry={() => undefined} />}
          <div className="results__actions">
            <button className="primary-action" type="button" onClick={() => void startSession()}>Play again <span>↻</span></button>
            <button className="text-action" type="button" onClick={onExit}>Back to home</button>
          </div>
        </div>
      </section>
    )
  }

  if (!question) return null
  const score = feedback?.score ?? question.score

  return (
    <section className="quiz-shell" aria-labelledby="question-heading">
      <div className="quiz-shell__grain" aria-hidden="true" />
      <BrandBar onExit={onExit} label={`Score ${score.toString().padStart(2, '0')}`} />
      <div className="quiz-layout">
        <header className="quiz-progress">
          <div><p>Scene {String(question.question_number).padStart(2, '0')} / {String(question.total_questions).padStart(2, '0')} · {difficulty} · {genre.replace('_', ' ')}</p></div>
          <div className="progress-track" aria-hidden="true"><span style={{ width: `${(question.question_number / question.total_questions) * 100}%` }} /></div>
        </header>
        <div className="question-panel">
          <div className="quote-block">
            <span className="quote-mark" aria-hidden="true">“</span>
            <h1 id="question-heading">{question.quote}</h1>
            <p>Which film delivered this line?</p>
            <button
              className="hint-button"
              type="button"
              disabled={feedback !== null || hint !== null || question.hint_used || isHintLoading || isSubmitting}
              onClick={() => void requestHint()}
            >
              <span aria-hidden="true">✦</span>
              {isHintLoading ? 'Preparing your hint…' : hint || question.hint_used ? 'Hint used' : 'Unlock a hint'}
            </button>
            {hint && (
              <div className="hint-card" aria-live="polite">
                <span>Your clue</span>
                <p>{hint.hint}</p>
              </div>
            )}
          </div>
          <div className="answers" aria-label="Answer choices">
            {question.choices.map((choice, index) => {
              const showCorrect = feedback !== null && choice === feedback.correct_answer
              const showIncorrect = feedback !== null && selectedAnswer === choice && !feedback.is_correct
              const state = showCorrect ? 'correct' : showIncorrect ? 'incorrect' : 'idle'
              return (
                <button key={choice} className={`answer answer--${state}`} type="button" disabled={feedback !== null || isSubmitting || isHintLoading} onClick={() => void submitAnswer(choice)}>
                  <span className="answer__index">{String.fromCharCode(65 + index)}</span><span>{choice}</span>
                  {state !== 'idle' && <span className="answer__icon" aria-hidden="true">{state === 'correct' ? '✓' : '×'}</span>}
                </button>
              )
            })}
          </div>
          <div className="feedback" aria-live="polite">
            {feedback && (
              <>
                <div>
                  <strong className={feedback.is_correct ? 'feedback--correct' : 'feedback--incorrect'}>{feedback.is_correct ? 'Correct. Nice take.' : 'Not quite.'}</strong>
                  <p>The answer is <span>{feedback.correct_answer}</span>{feedback.movie_year ? ` (${feedback.movie_year})` : ''}.</p>
                  <button className="why-button" type="button" disabled={explanationLoading} onClick={async () => {
                    if (!sessionId || !question) return
                    setExplanationLoading(true); setError(null)
                    try { setExplanation(await quizApi.getExplanation(sessionId, question.id)) } catch (caught) { setError(getErrorMessage(caught)) } finally { setExplanationLoading(false) }
                  }}>{explanationLoading ? 'Explaining…' : explanation ? 'Explanation ready' : 'Why this film?'}</button>
                  {explanation && <div className="explanation-card"><span>Quote breakdown</span><p>{explanation.explanation}</p></div>}
                </div>
                <button className="primary-action" type="button" onClick={() => void advance()} disabled={isSubmitting}>{feedback.completed ? 'See results' : 'Next question'} <span>→</span></button>
              </>
            )}
            {isSubmitting && !feedback && <p className="request-status">Checking your answer…</p>}
          </div>
          {error && <InlineError message={error} canRetry={retryAction !== null} onRetry={retry} />}
        </div>
      </div>
    </section>
  )
}

function InlineError({ message, canRetry, onRetry }: { message: string; canRetry: boolean; onRetry: () => void }) {
  return <div className="inline-error" role="alert"><span>{message}</span>{canRetry && <button type="button" onClick={onRetry}>Retry</button>}</div>
}

function StatusScreen({ title, detail, actionLabel, onAction, onExit }: { title: string; detail: string; actionLabel?: string; onAction?: () => void; onExit: () => void }) {
  return <section className="quiz-shell status-screen"><div className="quiz-shell__grain" aria-hidden="true" /><BrandBar onExit={onExit} label="Now loading" /><div><p className="quiz-kicker">CineQuote</p><h1>{title}</h1><p>{detail}</p>{actionLabel && onAction && <button className="primary-action" type="button" onClick={onAction}>{actionLabel} <span>↻</span></button>}</div></section>
}

function BrandBar({ label, onExit }: { label: string; onExit: () => void }) {
  return <nav className="quiz-nav" aria-label="Quiz navigation"><button className="quiz-brand" type="button" onClick={onExit} aria-label="Return to game selection"><FilmMark /><span>Cine</span><span>Quote</span></button><div className="quiz-nav__actions"><span>{label}</span><button type="button" onClick={onExit}>Quit</button></div></nav>
}

function getErrorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'An unexpected error interrupted the quiz.'
}

function getResultMessage(percentage: number): string {
  if (percentage === 100) return 'A flawless performance. Every line, right on cue.'
  if (percentage >= 80) return 'Leading-role material. Your cinema memory runs deep.'
  if (percentage >= 60) return 'A strong showing. A few more screenings and you’ll own the scene.'
  return 'The credits aren’t rolling yet. Take another shot and beat your score.'
}
