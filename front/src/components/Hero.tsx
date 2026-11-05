import { FilmMark } from './FilmMark'
import './Hero.css'
import './Account.css'
import type { User } from '../api/types'

interface HeroProps {
  onStart: () => void
  user: User | null
  onAccount: () => void
  onStats: () => void
  onLogout: () => void
}

export function Hero({ onStart, user, onAccount, onStats, onLogout }: HeroProps) {
  return (
    <section className="hero" aria-labelledby="page-title">
      <div className="hero__grain" aria-hidden="true" />
      <nav className="hero__nav" aria-label="Primary navigation">
        <a className="brand" href="/" aria-label="CineQuote home">
          <FilmMark />
          <span>CineQuote</span>
          <span className="brand__accent">PLAY</span>
        </a>
        <span className="edition">Volume 01 · Opening Night</span>
        <div className="hero-account">{user ? <><span>{user.username}</span><button className="account-primary" type="button" onClick={onStats}>My stats</button><button type="button" onClick={onLogout}>Sign out</button></> : <button className="account-primary" type="button" onClick={onAccount}>Sign in</button>}</div>
      </nav>

      <div className="hero__content">
        <p className="eyebrow"><span>Tonight's challenge</span> · 10 scenes · one score</p>
        <h1 id="page-title">
          Every great film<br />
          leaves a <em>line.</em>
        </h1>
        <p className="hero__intro">
          Recognize the line. Name the film. Build your score and prove your movie memory before the final cut.
        </p>
        <div className="hero__actions">
          <button type="button" className="start-button" onClick={onStart}>
            <span>Enter the game</span>
            <span aria-hidden="true">→</span>
          </button>
          <p className="status-note">
            Free to play · instant results
          </p>
        </div>
      </div>

      <footer className="hero__footer">
        <span>10 rounds</span>
        <span className="footer-rule" aria-hidden="true" />
        <span>4 choices</span>
        <span className="footer-rule" aria-hidden="true" />
        <span>1 final score</span>
      </footer>
    </section>
  )
}

