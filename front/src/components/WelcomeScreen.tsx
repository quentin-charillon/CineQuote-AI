import { FilmMark } from './FilmMark'
import './WelcomeScreen.css'

interface Props {
  onSolo: () => void
  onMultiplayer: () => void
  multiplayer?: boolean
  onBack?: () => void
}

export function WelcomeScreen({ onSolo, onMultiplayer, multiplayer = false, onBack }: Props) {
  return <section className="welcome-shell">
    <div className="welcome-grain" aria-hidden="true" />
    <div className="welcome-glow" aria-hidden="true" />
    <header className="welcome-nav">
      <div className="welcome-brand"><FilmMark /><span>Cine</span><b>Quote</b></div>
      {multiplayer && <button className="welcome-back" type="button" onClick={onBack}>← Back</button>}
    </header>

    {multiplayer ? <div className="coming-soon">
      <p className="welcome-kicker">The next feature</p>
      <div className="coming-icon" aria-hidden="true"><span /><span /><span /></div>
      <h1>Multiplayer<br/><em>coming soon.</em></h1>
      <p>Challenge your friends, share the spotlight and race to name the film first.</p>
      <button className="welcome-primary" type="button" onClick={onSolo}>Play solo for now <span>→</span></button>
    </div> : <div className="welcome-stage">
      <div className="welcome-art" aria-hidden="true">
        <div className="reel"><i /><i /><i /><i /><i /></div>
        <div className="film-strip"><span /><span /><span /><span /><span /><span /></div>
        <div className="clapper"><div /><strong>CQ</strong><small>TAKE ONE</small></div>
      </div>

      <div className="welcome-copy">
        <p className="welcome-kicker">Lights down. Memory on.</p>
        <h1>One quote.<br/><em>Which film?</em></h1>
        <p className="welcome-lead">Step into the cinema, recognize the line and claim the scene.</p>
        <div className="play-mode-actions" aria-label="Choose a game mode">
          <button className="welcome-primary" type="button" onClick={onSolo}><small>01</small> Solo <span>→</span></button>
          <button className="welcome-secondary" type="button" onClick={onMultiplayer}><small>02</small> Multiplayer <span>Soon</span></button>
        </div>
      </div>
    </div>}

    <footer className="welcome-footer"><span>Dialogue</span><i /><span>Memory</span><i /><span>Cinema</span></footer>
  </section>
}
