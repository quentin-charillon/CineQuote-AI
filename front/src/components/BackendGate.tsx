import { useEffect, useState, type ReactNode } from 'react'

import { BackendWakeError, waitForBackend } from '../api/backendWake'
import { FilmMark } from './FilmMark'
import './BackendGate.css'

interface Props {
  children: ReactNode
  onReady?: () => void
}

type GateState =
  | { phase: 'waiting'; attempt: number }
  | { phase: 'ready'; attempt: number }
  | { phase: 'failed'; attempt: number; message: string }

export function BackendGate({ children, onReady }: Props) {
  const [generation, setGeneration] = useState(0)
  const [state, setState] = useState<GateState>({ phase: 'waiting', attempt: 1 })

  useEffect(() => {
    const controller = new AbortController()
    setState({ phase: 'waiting', attempt: 1 })

    void waitForBackend({
      signal: controller.signal,
      onProgress: progress => setState({ phase: 'waiting', attempt: progress.attempt + 1 }),
    }).then(() => {
      if (controller.signal.aborted) return
      setState(previous => ({ phase: 'ready', attempt: previous.attempt }))
      onReady?.()
    }).catch((error: unknown) => {
      if (controller.signal.aborted || (error instanceof BackendWakeError && error.kind === 'cancelled')) return
      setState(previous => ({
        phase: 'failed',
        attempt: previous.attempt,
        message: error instanceof Error ? error.message : 'The cinema server could not be reached.',
      }))
    })

    return () => controller.abort()
  }, [generation, onReady])

  if (state.phase === 'ready') return children

  return <section className="wake-shell" aria-labelledby="wake-title">
    <div className="wake-grain" aria-hidden="true" />
    <header className="wake-brand"><FilmMark /><span>Cine</span><b>Quote</b></header>
    <div className="wake-content">
      <div className="projector-reel" aria-hidden="true"><i /><i /><i /><i /><span /></div>
      <p className="wake-kicker">Preparing your screening</p>
      <h1 id="wake-title">The projector is<br/><em>warming up...</em></h1>
      <p>Our cinema server is waking up. Your screening will begin shortly.</p>
      {state.phase === 'waiting' ? <div className="wake-progress" role="status" aria-live="polite">
        <span className="wake-progress__bar"><i /></span>
        <small>The first loading may take a few moments. Attempt {state.attempt}.</small>
      </div> : <div className="wake-failure" role="alert">
        <small>{state.message}</small>
        <button type="button" onClick={() => setGeneration(value => value + 1)}>Retry <span>↻</span></button>
      </div>}
    </div>
  </section>
}
